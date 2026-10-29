import os
import sys
import re
import json
import time
import argparse
import requests
import fitz  # PyMuPDF

def extract_page_vocabulary(text: str, api_key: str, words_count: int = 10, max_retries: int = 3) -> list:
    """Calls Google Gemini API to extract rich vocabulary with categories (Medium/Hard) and robust retries."""
    
    prompt = f"""You are an elite lexicographer creating a vocabulary dataset for Indian NCERT school students.
Analyze the following textbook page text and extract exactly the top {words_count} most important or challenging vocabulary words.

For every word, return a JSON object with these EXACT keys:
- "word": "Title Case Word"
- "category": "Medium" or "Hard" (categorize every word based on student level)
- "pronunciation": "Accurate IPA phonetic transcription e.g. /ˈkrɪŋ.kli/"
- "pronunciation_hindi": "Pronunciation written in Hindi e.g. क्रिंकली"
- "pos": "Part of speech (Noun, Verb, Adjective, Adverb, etc.)"
- "english_meaning": "Clear, accessible English definition"
- "hindi_meaning": "Accurate, standard Hindi translation (शुद्ध एवं सरल हिंदी अर्थ)"
- "example": "A natural, high-quality example sentence using the word properly"

TEXT OF THIS PAGE:
\"\"\"
{text[:4500]}
\"\"\"

RESPONSE FORMAT RULES:
- Output strictly a valid JSON array of objects.
- Enclose the array in ```json ... ``` code fences.
- No other text, introduction, or commentary.
"""

    models = ["gemini-3.5-flash", "gemini-3.8-flash", "gemini-flash-latest", "gemma-4-26b-a4b-it"]
    
    for attempt in range(1, max_retries + 1):
        for m in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.8
                }
            }

            try:
                resp = requests.post(url, json=payload, timeout=60)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates", [])
                    if candidates and "content" in candidates[0] and "parts" in candidates[0]["content"]:
                        raw_text = candidates[0]["content"]["parts"][0]["text"]

                        match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw_text)
                        clean_json = match.group(1).strip() if match else raw_text.strip()

                        s = clean_json.find("[")
                        e = clean_json.rfind("]")
                        if s != -1 and e != -1:
                            clean_json = clean_json[s:e+1]

                        items = json.loads(clean_json)
                        if isinstance(items, list):
                            return items
                elif resp.status_code in (429, 503):
                    print(f"    [Retryable {resp.status_code}] Model {m}: {resp.status_code}. Sleeping 8s...")
                    time.sleep(8.0)
                else:
                    print(f"    [Error {resp.status_code}] Model {m}: {resp.text[:120]}")
            except Exception as ex:
                print(f"    [Network/Timeout] Model {m}: {str(ex)[:100]}")

            time.sleep(2.0)

        if attempt < max_retries:
            backoff = attempt * 10
            print(f"  Attempt {attempt}/{max_retries} failed. Backing off {backoff}s before retry...")
            time.sleep(backoff)

    print("Warning: All retries exhausted for this page.")
    return []

def main():
    parser = argparse.ArgumentParser(description="NCERT Cloud Vocabulary Generator")
    parser.add_argument("--pdf", required=True, help="Path to textbook PDF file")
    parser.add_argument("--book-title", default="NCERT History Textbook", help="Title of the book")
    parser.add_argument("--class-level", type=int, default=8, help="Class grade level (1-12)")
    parser.add_argument("--words-per-page", type=int, default=10, help="Target words count per page")
    parser.add_argument("--start-page", type=int, default=1, help="Start page (1-indexed)")
    parser.add_argument("--end-page", type=int, default=0, help="End page (0 for all pages)")
    parser.add_argument("--delay", type=float, default=4.0, help="Polite delay between pages in seconds")
    parser.add_argument("--output-dir", default="datasets", help="Output directory for JSON")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip pages already present in dataset")

    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: GEMINI_API_KEY environment variable is not set!")
        sys.exit(1)

    if not os.path.exists(args.pdf):
        print(f"ERROR: PDF file not found at {args.pdf}")
        sys.exit(1)

    doc = fitz.open(args.pdf)
    total_doc_pages = doc.page_count
    start_p = max(1, args.start_page)
    end_p = total_doc_pages if args.end_page <= 0 else min(args.end_page, total_doc_pages)

    os.makedirs(args.output_dir, exist_ok=True)
    safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", args.book_title).lower()
    out_file = os.path.join(args.output_dir, f"{safe_title}.json")

    # Load existing dataset if resuming
    dataset = {
        "book_title": args.book_title,
        "class_level": args.class_level,
        "total_pages": total_doc_pages,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "pages": {}
    }
    if os.path.exists(out_file):
        try:
            with open(out_file, "r", encoding="utf-8") as f:
                loaded = json.load(f)
                if isinstance(loaded, dict):
                    dataset.update(loaded)
                    dataset["total_pages"] = total_doc_pages
        except Exception:
            pass

    print(f">> Starting vocabulary generation for '{args.book_title}'")
    print(f">> Processing pages {start_p} to {end_p} (Total in range: {end_p - start_p + 1} | Book total: {total_doc_pages} pages)")
    print(f">> Target: {args.words_per_page} words/page | Category: Medium/Hard | Skip Existing: {args.skip_existing}")

    words_added = 0
    for p in range(start_p, end_p + 1):
        # Skip if already exists in dataset
        if args.skip_existing and str(p) in dataset.get("pages", {}) and len(dataset["pages"][str(p)]) > 0:
            print(f"[SKIP] Page {p}/{end_p}: Already extracted ({len(dataset['pages'][str(p)])} words). Skipping...")
            continue

        page_idx = p - 1
        page = doc.load_page(page_idx)
        text = page.get_text("text").strip()

        if len(text) < 40:
            print(f"[-] Page {p}/{end_p}: Skipped (minimal or no text layer)")
            continue

        print(f"[*] Page {p}/{end_p}: Extracting {args.words_per_page} words via Gemini...")
        words = extract_page_vocabulary(text, api_key, words_count=args.words_per_page)

        if words:
            for w in words:
                w["page_number"] = p
                w["book"] = args.book_title
                w["class"] = args.class_level
                # Ensure category exists
                if "category" not in w:
                    w["category"] = w.get("difficulty", "Medium")

            dataset["pages"][str(p)] = words
            dataset["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Save incrementally after every page
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(dataset, f, indent=2, ensure_ascii=False)

            words_added += len(words)
            print(f"[OK] Page {p}/{end_p}: Saved {len(words)} words. (New this run: {words_added} | Total stored: {sum(len(v) for v in dataset['pages'].values())})")
        else:
            print(f"[!] Page {p}/{end_p}: 0 words extracted.")

        # Respect Google Gemini Free Tier 15 RPM limit
        time.sleep(args.delay)

    doc.close()
    print("=" * 60)
    print(f"[DONE] Completed! Total {words_added} new words generated. Dataset has {len(dataset['pages'])} pages saved at {out_file}")
    print("=" * 60)

if __name__ == "__main__":
    main()
