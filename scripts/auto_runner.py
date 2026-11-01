import os
import sys
import subprocess
import fitz
import json
import re

def main():
    books_dir = "books"
    datasets_dir = "datasets"
    words_per_page = int(os.environ.get("WORDS_PER_PAGE", "10"))
    specified_book = os.environ.get("SPECIFIC_BOOK", "auto").strip()

    if not os.path.exists(books_dir):
        print("No 'books' directory found.")
        sys.exit(0)

    pdf_files = [f for f in sorted(os.listdir(books_dir)) if f.lower().endswith(".pdf")]
    if not pdf_files:
        print("No PDF files found in 'books/'.")
        sys.exit(0)

    print(f">> Found {len(pdf_files)} PDF book(s) in 'books/': {pdf_files}")

    for pdf_name in pdf_files:
        safe_name = os.path.splitext(pdf_name)[0]
        safe_title = re.sub(r"[^a-zA-Z0-9_-]", "_", safe_name).lower()
        pdf_path = os.path.join(books_dir, pdf_name)
        dataset_json = os.path.join(datasets_dir, f"{safe_title}.json")

        # If a specific book was requested via workflow_dispatch, only run that one
        if specified_book != "auto" and specified_book != safe_name and specified_book not in pdf_name:
            print(f">> Skipping '{pdf_name}' (specific book '{specified_book}' requested)")
            continue

        doc = fitz.open(pdf_path)
        total_pages = doc.page_count
        doc.close()

        # Check if dataset already exists and is complete
        is_complete = False
        existing_pages = 0
        if os.path.exists(dataset_json):
            try:
                with open(dataset_json, "r", encoding="utf-8") as f:
                    d = json.load(f)
                existing_pages = len(d.get("pages", {}))
                # Consider complete if pages covered is close to total pages (accounting for blank/notes pages)
                if existing_pages >= max(1, total_pages - 6):
                    is_complete = True
            except Exception:
                is_complete = False

        if is_complete and specified_book == "auto":
            print(f"\n[SKIP] '{pdf_name}': Dataset already complete ({existing_pages}/{total_pages} pages). Skipping.")
            continue

                # Determine words per page:
        # Class 11 Rules: Geography (18 WPP), Economics (12 WPP), Political Science (15 WPP)
        # Class 12 Rules: Geography (20 WPP), Economics (15 WPP), Political Science (12 WPP)
        book_wpp = words_per_page
        low_name = pdf_name.lower()

        # Science Rule (Class 6 to 10): 15 words/page
        if any(kw in low_name for kw in ["science", "curiosity"]) and not any(kw in low_name for kw in ["political", "social"]):
            book_wpp = 15
            print(f">> [SPECIALIZED RULE] Science detected ({pdf_name}): Target set to {book_wpp} words/page!")
        is_c7 = "class_07" in low_name or "class 07" in low_name or "class07" in low_name or "class_7" in low_name or "class 7" in low_name or "class7" in low_name
        is_c8 = "class_08" in low_name or "class 08" in low_name or "class08" in low_name or "class_8" in low_name or "class 8" in low_name or "class8" in low_name
        is_c9 = "class_09" in low_name or "class 09" in low_name or "class09" in low_name or "class_9" in low_name or "class 9" in low_name or "class9" in low_name
        is_c10 = "class_10" in low_name or "class 10" in low_name or "class10" in low_name
        is_c11 = "class_11" in low_name or "class 11" in low_name or "class11" in low_name
        is_c12 = "class_12" in low_name or "class 12" in low_name or "class12" in low_name

        if is_c7:
            if any(kw in low_name for kw in ["geography", "bhugol", "environment"]):
                book_wpp = 15
                print(f">> [SPECIALIZED RULE] Class 7 Geography detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["civics", "political", "social_and_political_life"]):
                book_wpp = 10
                print(f">> [SPECIALIZED RULE] Class 7 Civics detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["history", "social", "itihas"]):
                book_wpp = 18
                print(f">> [SPECIALIZED RULE] Class 7 History detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["english", "poorvi"]):
                book_wpp = 10

        elif is_c8:
            if any(kw in low_name for kw in ["geography", "bhugol", "resources"]):
                book_wpp = 15
                print(f">> [SPECIALIZED RULE] Class 8 Geography detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["civics", "political", "social_and_political_life"]):
                book_wpp = 10
                print(f">> [SPECIALIZED RULE] Class 8 Civics detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["history", "social", "itihas"]):
                book_wpp = 18
                print(f">> [SPECIALIZED RULE] Class 8 History detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["english", "honeydew", "happened"]):
                book_wpp = 10

        elif is_c9:
            if any(kw in low_name for kw in ["geography", "bhugol", "contemporary_india"]):
                book_wpp = 15
                print(f">> [SPECIALIZED RULE] Class 9 Geography detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["civics", "political", "democratic_politics"]):
                book_wpp = 12
                print(f">> [SPECIALIZED RULE] Class 9 Civics detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["economic", "arthashastra"]):
                book_wpp = 10
                print(f">> [SPECIALIZED RULE] Class 9 Economics detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["history", "social", "itihas"]):
                book_wpp = 18
                print(f">> [SPECIALIZED RULE] Class 9 History detected: Target set to {book_wpp} words/page!")

        elif is_c10:
            if any(kw in low_name for kw in ["geography", "bhugol", "contemporary_india"]):
                book_wpp = 15
                print(f">> [SPECIALIZED RULE] Class 10 Geography detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["civics", "political", "democratic_politics"]):
                book_wpp = 12
                print(f">> [SPECIALIZED RULE] Class 10 Civics detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["economic", "arthashastra", "development"]):
                book_wpp = 10
                print(f">> [SPECIALIZED RULE] Class 10 Economics detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["history", "social", "itihas"]):
                book_wpp = 18
                print(f">> [SPECIALIZED RULE] Class 10 History detected: Target set to {book_wpp} words/page!")

        elif is_c11:
            if any(kw in low_name for kw in ["geography", "bhugol"]):
                book_wpp = 18
                print(f">> [SPECIALIZED RULE] Class 11 Geography detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["economic", "arthashastra"]):
                book_wpp = 12
                print(f">> [SPECIALIZED RULE] Class 11 Economics detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["political", "civics", "rajniti"]):
                book_wpp = 15
                print(f">> [SPECIALIZED RULE] Class 11 Political Science detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["history", "social", "itihas"]):
                book_wpp = 18
                print(f">> [SPECIALIZED RULE] Class 11 History detected: Target set to {book_wpp} words/page!")
        elif is_c12:
            if any(kw in low_name for kw in ["geography", "bhugol"]):
                book_wpp = 20
                print(f">> [SPECIALIZED RULE] Class 12 Geography detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["economic", "arthashastra"]):
                book_wpp = 15
                print(f">> [SPECIALIZED RULE] Class 12 Economics detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["political", "civics", "rajniti"]):
                book_wpp = 12
                print(f">> [SPECIALIZED RULE] Class 12 Political Science detected: Target set to {book_wpp} words/page!")
            elif any(kw in low_name for kw in ["history", "social", "itihas"]):
                book_wpp = 18
                print(f">> [SPECIALIZED RULE] Class 12 History detected: Target set to {book_wpp} words/page!")
        else:
            if any(kw in low_name for kw in ["geography", "bhugol"]):
                book_wpp = 18
            elif any(kw in low_name for kw in ["economic", "arthashastra"]):
                book_wpp = 12
            elif any(kw in low_name for kw in ["political", "civics", "rajniti"]):
                book_wpp = 15
            elif any(kw in low_name for kw in ["history", "social", "itihas"]):
                book_wpp = 18

        print(f"\n{'='*70}")
        print(f">> [TRIGGERED] Auto-generating vocabulary for: {pdf_name}")
        print(f">> Total Textbook Pages: {total_pages} | Target Words/Page: {book_wpp}")
        print(f"{'='*70}")

        cmd = [
            "python", "scripts/generate_vocab.py",
            "--pdf", pdf_path,
            "--book-title", safe_name,
            "--words-per-page", str(book_wpp),
            "--start-page", "1",
            "--end-page", "0",
            "--delay", "2.0",
            "--skip-existing",
            "--output-dir", datasets_dir
        ]

        res = subprocess.run(cmd)
        if res.returncode != 0:
            print(f"[ERROR] Failed generation for {pdf_name} with code {res.returncode}")
        else:
            print(f"[SUCCESS] Finished generation for {pdf_name}")

            # Also generate .js bundle if json exists
            if os.path.exists(dataset_json):
                js_file = os.path.join(datasets_dir, f"{safe_title}_data.js")
                try:
                    with open(dataset_json, "r", encoding="utf-8") as f:
                        jdata = json.load(f)
                    clean_id = re.sub(r"[^a-zA-Z0-9]", "_", safe_title).upper()
                    clean_id = re.sub(r"_+", "_", clean_id).strip("_")
                    var_name = f"CLASS_{clean_id}_DATA"
                    with open(js_file, "w", encoding="utf-8") as f:
                        f.write(f"window.{var_name} = " + json.dumps(jdata, ensure_ascii=False) + ";\n")
                    print(f"Generated web companion: {js_file}")
                except Exception as ex:
                    print(f"Warning: could not create JS bundle: {ex}")

            # If running in GitHub Actions, commit and push incrementally after each completed book!
            if os.environ.get("GITHUB_ACTIONS") == "true":
                try:
                    print(f">> Incrementally committing dataset for '{pdf_name}' to git...")
                    subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=False)
                    subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
                    subprocess.run(["git", "add", "datasets/"], check=False)
                    diff_check = subprocess.run(["git", "diff", "--staged", "--quiet"])
                    if diff_check.returncode != 0:
                        subprocess.run(["git", "commit", "-m", f"feat(vocab): add {safe_name} vocabulary dataset [skip ci]"], check=False)
                        subprocess.run(["git", "rebase", "--abort"], capture_output=True, check=False)
                        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)
                        push_res = subprocess.run(["git", "push", "origin", "HEAD:main"])
                        if push_res.returncode == 0:
                            print(f">> [INCREMENTAL SYNC] Successfully pushed dataset for {pdf_name} to main!")
                        else:
                            print(f">> [INCREMENTAL SYNC] Push returned {push_res.returncode}, will sync at workflow end.")
                except Exception as push_err:
                    print(f">> [INCREMENTAL SYNC] Warning during auto-push: {push_err}")

            # Send celebratory completion notification to Telegram with buttons for next books!
            try:
                sys.path.append(os.path.dirname(__file__))
                from telegram_notifier import send_book_completion
                if os.path.exists(dataset_json):
                    with open(dataset_json, "r", encoding="utf-8") as f:
                        d = json.load(f)
                    tot_pages = len(d.get("pages", {}))
                    tot_words = sum(len(p) for p in d.get("pages", {}).values())
                    send_book_completion(safe_name, tot_pages, tot_words, book_wpp)
                    print(f">> [TELEGRAM] Sent completion notification for {safe_name}")
            except Exception as tg_err:
                print(f">> [TELEGRAM] Warning: {tg_err}")

if __name__ == "__main__":
    main()
