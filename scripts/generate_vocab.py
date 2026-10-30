import os
import sys
import re
import json
import time
import argparse
import requests
import fitz  # PyMuPDF

# Verified active models on Google Generative Language API
MODELS = [
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash"
]

class KeyManager:
    """Manages multiple Gemini API keys with Round-Robin rotation and cooldown on 429."""
    def __init__(self, raw_keys: str):
        self.keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        self.cooldowns = {k: 0 for k in self.keys}
        self.index = 0
        if not self.keys:
            raise ValueError("No valid API keys provided!")
        print(f">> KeyManager initialized with {len(self.keys)} active API key(s).")

    def get_key(self) -> str:
        now = time.time()
        # Find an available key not in cooldown
        for _ in range(len(self.keys)):
            k = self.keys[self.index % len(self.keys)]
            self.index += 1
            if now >= self.cooldowns[k]:
                return k

        # If all keys in cooldown, pick the one that resets earliest
        earliest_key = min(self.keys, key=lambda k: self.cooldowns[k])
        wait_seconds = max(1.0, self.cooldowns[earliest_key] - now)
        print(f"    [All Keys in Cooldown] Pausing {wait_seconds:.1f}s for key to reset...")
        time.sleep(wait_seconds)
        return earliest_key

    def mark_rate_limited(self, key: str, cooldown_seconds: int = 40):
        self.cooldowns[key] = time.time() + cooldown_seconds
        short_k = key[:12] + "..." + key[-4:]
        print(f"    [Key Rotator] Key {short_k} hit 429. Placed on {cooldown_seconds}s cooldown. Switching to next key!")


def extract_page_vocabulary(text: str, key_manager: KeyManager, words_count: int = 10, max_retries: int = 25) -> list:
    """Extracts vocabulary words using multi-key rotation and multi-model fallback."""
    
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

    model_idx = 0
    attempt = 0

    while attempt < max_retries:
        attempt += 1
        api_key = key_manager.get_key()
        m = MODELS[model_idx % len(MODELS)]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.8
            }
        }

        try:
            resp = requests.post(url, json=payload, timeout=22)

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
                    if isinstance(items, list) and len(items) > 0:
                        return items

            elif resp.status_code == 429:
                key_manager.mark_rate_limited(api_key, cooldown_seconds=40)
                # Next loop iteration immediately tries the next key
                continue

            elif resp.status_code in (500, 502, 503, 504):
                print(f"    [Server Error {resp.status_code}] Model {m}. Trying fallback model...")
                model_idx += 1
                time.sleep(1.5)
                continue

            else:
                print(f"    [HTTP {resp.status_code}] Model {m}: {resp.text[:80]}")
                model_idx += 1
                time.sleep(2.0)

        except requests.exceptions.Timeout:
            print(f"    [Timeout] Model {m} timed out after 22s. Trying fallback model...")
            model_idx += 1
            time.sleep(1.0)
        except Exception as ex:
            print(f"    [Network Exception] {str(ex)[:80]}")
            time.sleep(2.0)

    print(f"    [Warning] All retries exhausted for this page.")
    return []


def main():
    parser = argparse.ArgumentParser(description="NCERT Cloud Vocabulary Generator")
    parser.add_argument("--pdf", required=True, help="Path to textbook PDF file")
    parser.add_argument("--book-title", default="NCERT History Textbook", help="Title of the book")
    parser.add_argument("--class-level", type=int, default=8, help="Class grade level (1-12)")
    parser.add_argument("--words-per-page", type=int, default=10, help="Target words count per page")
    parser.add_argument("--start-page", type=int, default=1, help="Start page (1-indexed)")
    parser.add_argument("--end-page", type=int, default=0, help="End page (0 for all pages)")
    parser.add_argument("--delay", type=float, default=2.0, help="Delay between pages (1.5-2.0s with multi-key rotation)")
    parser.add_argument("--output-dir", default="datasets", help="Output directory for JSON")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip pages already present in dataset")

    args = parser.parse_args()

    api_key_str = os.environ.get("GEMINI_API_KEY")
    if not api_key_str:
        print("ERROR: GEMINI_API_KEY environment variable is not set!")
        sys.exit(1)

    key_manager = KeyManager(api_key_str)

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
                    if "pages" not in dataset:
                        dataset["pages"] = {}
        except Exception:
            pass

    print(f">> Starting vocabulary generation for '{args.book_title}'")
    print(f">> Processing pages {start_p} to {end_p} (Total in range: {end_p - start_p + 1} | Book total: {total_doc_pages} pages)")
    print(f">> Target: {args.words_per_page} words/page | Category: Medium/Hard | Skip Existing: {args.skip_existing}")
    print(f">> Delay between requests: {args.delay}s (Optimized for {len(key_manager.keys)} keys)")

    words_added = 0
    pages_processed = 0

    for p in range(start_p, end_p + 1):
        if args.skip_existing and str(p) in dataset["pages"] and len(dataset["pages"][str(p)]) > 0:
            print(f"[SKIP] Page {p}/{end_p}: Already extracted ({len(dataset['pages'][str(p)])} words). Skipping...")
            continue

        page_idx = p - 1
        page = doc.load_page(page_idx)
        text = page.get_text("text").strip()

        if len(text) < 40:
            print(f"[-] Page {p}/{end_p}: Skipped (minimal or no text layer)")
            continue

        print(f"[*] Page {p}/{end_p}: Extracting {args.words_per_page} words via Gemini...")
        words = extract_page_vocabulary(text, key_manager, words_count=args.words_per_page)

        if words:
            for w in words:
                w["page_number"] = p
                w["book"] = args.book_title
                w["class"] = args.class_level
                if "category" not in w:
                    w["category"] = w.get("difficulty", "Medium")

            dataset["pages"][str(p)] = words
            dataset["last_updated"] = time.strftime("%Y-%m-%d %H:%M:%S")

            # Save incrementally after every successful page
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(dataset, f, indent=2, ensure_ascii=False)

            words_added += len(words)
            pages_processed += 1
            print(f"[OK] Page {p}/{end_p}: Saved {len(words)} words. (New this run: {words_added} | Total stored: {sum(len(v) for v in dataset['pages'].values())})")
        else:
            print(f"[!] Page {p}/{end_p}: 0 words extracted. NOT saving empty page so it can be re-run.")

        time.sleep(args.delay)

    doc.close()
    print("=" * 60)
    print(f"[DONE] Completed! Total {words_added} new words generated across {pages_processed} pages.")
    print(f"[DONE] Total saved pages in dataset: {len(dataset['pages'])} pages at {out_file}")
    print("=" * 60)


if __name__ == "__main__":
    main()
