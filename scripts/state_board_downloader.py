#!/usr/bin/env python3
"""
State Board Textbook Downloader & Optimizer
Specialized for Bihar School Examination Board (BSEB / BSTBPC) and State Boards.
Fetches official chapter PDFs from BSTBPC API, merges them, ensures <90 MB size limit,
and places them into 'books/state_board/' for vocabulary generation.
"""

import os
import sys
import json
import re
import argparse
import requests
import urllib3
import fitz  # PyMuPDF
from PIL import Image
import io

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DEFAULT_OUT_DIR = os.path.join(REPO_ROOT, "books", "state_board")
BSTBPC_BASE_URL = "https://bstbpc.bihar.gov.in"

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
})

def safe_name(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_\s-]", "", str(text))
    s = re.sub(r"[\s-]+", "_", s).strip("_")
    return s

def fetch_json(url: str, timeout: int = 15):
    resp = SESSION.get(url, verify=False, timeout=timeout)
    resp.raise_for_status()
    return resp.json()

def fetch_binary(url: str, timeout: int = 30, retries: int = 3) -> bytes:
    for attempt in range(1, retries + 1):
        try:
            resp = SESSION.get(url, verify=False, timeout=timeout, stream=True)
            resp.raise_for_status()
            content = bytearray()
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    content.extend(chunk)
            return bytes(content)
        except Exception as e:
            if attempt == retries:
                raise e
            print(f"      [Retry {attempt}/{retries}] Download warning: {e}", flush=True)

def list_books(class_id=None, subject=None, search=None):
    """Queries BSTBPC API and filters books."""
    url = f"{BSTBPC_BASE_URL}/api/books?limit=1000"
    print(f">> Fetching BSTBPC catalog from {url}...", flush=True)
    try:
        data = fetch_json(url)
    except Exception as e:
        print(f"[ERROR] Failed to query BSTBPC API: {e}", flush=True)
        return []

    books = data.get("data", [])
    filtered = []

    for b in books:
        c_id = b.get("classId")
        if class_id is not None and str(c_id) != str(class_id):
            continue
        
        b_sub = (b.get("subject") or "").lower()
        if subject and subject.lower() not in b_sub:
            continue

        b_title = (b.get("title") or "").lower()
        if search and search.lower() not in b_title and search.lower() not in b_sub:
            continue

        filtered.append(b)

    return filtered

def compress_pdf_if_needed(doc: fitz.Document, max_mb: float = 90.0) -> fitz.Document:
    """Downsamples images if document exceeds max_mb limit."""
    temp_buf = io.BytesIO()
    doc.save(temp_buf, deflate=True, garbage=4)
    size_mb = temp_buf.tell() / (1024 * 1024)
    
    if size_mb <= max_mb:
        print(f">> Document size is {size_mb:.2f} MB (within {max_mb} MB limit). No recompression needed.", flush=True)
        temp_buf.seek(0)
        return doc

    print(f">> [COMPRESSION NEEDED] Document size is {size_mb:.2f} MB (> {max_mb} MB). Downsampling images...", flush=True)
    for page_idx in range(doc.page_count):
        page = doc[page_idx]
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            try:
                base_img = doc.extract_image(xref)
                if not base_img:
                    continue
                image_bytes = base_img["image"]
                pil_img = Image.open(io.BytesIO(image_bytes))
                
                # Resize if high resolution
                if pil_img.width > 800 or pil_img.height > 800:
                    pil_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                
                out_img_io = io.BytesIO()
                pil_img.convert("RGB").save(out_img_io, format="JPEG", quality=75, optimize=True)
                doc.update_stream(xref, out_img_io.getvalue())
            except Exception:
                continue

    return doc

def download_book_by_id(book_id: int, out_dir: str = DEFAULT_OUT_DIR, push: bool = False):
    """Downloads all chapters for a given BSTBPC book ID, merges them, and saves to out_dir."""
    os.makedirs(out_dir, exist_ok=True)
    detail_url = f"{BSTBPC_BASE_URL}/api/books/{book_id}"
    print(f"\n=======================================================", flush=True)
    print(f">> Querying Book details for ID: {book_id}...", flush=True)
    print(f"=======================================================", flush=True)
    
    try:
        data = fetch_json(detail_url)
    except Exception as e:
        print(f"[ERROR] Could not fetch details for book ID {book_id}: {e}", flush=True)
        return None

    book_info = data.get("data", {})
    if not book_info:
        print(f"[ERROR] No data found for book ID {book_id}", flush=True)
        return None

    class_id = book_info.get("classId", "0")
    title = book_info.get("title", f"Book_{book_id}")
    subject = book_info.get("subject", "General")
    chapters = sorted(book_info.get("chapters", []), key=lambda x: x.get("chapterNumber", 0))

    class_pad = f"{int(class_id):02d}" if str(class_id).isdigit() else str(class_id)
    clean_title = safe_name(title)
    filename = f"Class_{class_pad}_BSEB_{clean_title}.pdf"
    out_path = os.path.join(out_dir, filename)

    print(f">> Book: {title} (Class {class_id} | Subject: {subject})", flush=True)
    print(f">> Total Chapters Available: {len(chapters)}", flush=True)
    print(f">> Target Destination: {out_path}", flush=True)

    if not chapters:
        print(f"[ERROR] Book ID {book_id} has no uploaded chapters on BSTBPC.", flush=True)
        return None

    merged_doc = fitz.open()

    for idx, ch in enumerate(chapters, 1):
        ch_title = ch.get("title", f"Chapter {idx}")
        ch_pdf_path = ch.get("pdfUrl")
        if not ch_pdf_path:
            print(f"  [{idx}/{len(chapters)}] Skipping '{ch_title}' (no PDF path)", flush=True)
            continue

        ch_url = f"{BSTBPC_BASE_URL}{ch_pdf_path}" if ch_pdf_path.startswith("/") else ch_pdf_path
        print(f"  [{idx}/{len(chapters)}] Downloading: {ch_title}...", flush=True)

        try:
            pdf_bytes = fetch_binary(ch_url, timeout=30, retries=3)
            ch_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
            merged_doc.insert_pdf(ch_doc)
            print(f"      + Added {ch_doc.page_count} pages (running total: {merged_doc.page_count} pages)", flush=True)
            ch_doc.close()
        except Exception as err:
            print(f"      [WARNING] Error on '{ch_title}': {err}. Skipping chapter.", flush=True)

    if merged_doc.page_count == 0:
        print(f"[ERROR] Failed to compile any pages for {title}", flush=True)
        merged_doc.close()
        return None

    # Compress if > 90 MB
    merged_doc = compress_pdf_if_needed(merged_doc, max_mb=90.0)

    # Save finalized PDF
    merged_doc.save(out_path, deflate=True, garbage=4)
    merged_doc.close()

    final_size_mb = os.path.getsize(out_path) / (1024 * 1024)
    print(f"\n[SUCCESS] Compiled complete textbook: {filename}", flush=True)
    print(f"Total Pages: {fitz.open(out_path).page_count} | Size: {final_size_mb:.2f} MB", flush=True)

    if push:
        try:
            import subprocess
            print(f">> Auto-pushing '{filename}' to GitHub repository...", flush=True)
            subprocess.run(["git", "rebase", "--abort"], cwd=REPO_ROOT, capture_output=True, check=False)
            subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=REPO_ROOT, check=False)
            subprocess.run(["git", "add", out_path], cwd=REPO_ROOT, check=True)
            commit_msg = f"feat(state_board): add {filename} [skip ci]"
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_ROOT, check=True)
            push_res = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=REPO_ROOT, capture_output=True, text=True)
            if push_res.returncode == 0:
                print(f">> [GIT PUSH SUCCESS] {filename} is live on GitHub!", flush=True)
            else:
                print(f">> [GIT PUSH WARNING] {push_res.stderr[:200]}", flush=True)
        except Exception as e:
            print(f">> [GIT PUSH ERROR] {e}", flush=True)

    return out_path

POPULAR_BSEB_BOOKS = [
    # Class 10
    {"id": 53, "name": "Panorama 2 (English Reader)", "class": 10},
    {"id": 51, "name": "Godhuli 2 (Hindi)", "class": 10},
    {"id": 52, "name": "Warnika 2 (Hindi Supplement)", "class": 10},
    {"id": 55, "name": "Piyusham (Sanskrit)", "class": 10},
    {"id": 42, "name": "Vigyan (Science)", "class": 10},
    # Class 9
    {"id": 13, "name": "Panorama English Reader", "class": 9},
    {"id": 16, "name": "Godhuli 1 (Hindi)", "class": 9},
    {"id": 37, "name": "Varnika 1 (Hindi Supplement)", "class": 9},
    {"id": 25, "name": "Piyusham (Sanskrit)", "class": 9},
    {"id": 11, "name": "Vigyan (Science)", "class": 9},
    # Class 8
    {"id": 185, "name": "Radiance (English)", "class": 8},
    {"id": 184, "name": "Kislay (Hindi)", "class": 8},
    {"id": 188, "name": "Amrita (Sanskrit)", "class": 8},
    # Class 7
    {"id": 168, "name": "Radiance (English)", "class": 7},
    {"id": 169, "name": "Amrita (Sanskrit)", "class": 7},
    # Class 6
    {"id": 149, "name": "Radiance (English)", "class": 6},
    {"id": 153, "name": "Amrita (Sanskrit)", "class": 6},
    {"id": 156, "name": "Kislay (Hindi)", "class": 6},
]

def main():
    parser = argparse.ArgumentParser(description="State Board Textbook Downloader (BSTBPC / BSEB)")
    parser.add_argument("--book-id", type=int, help="BSTBPC book ID to download directly")
    parser.add_argument("--class-num", type=int, help="Class number (1 to 12)")
    parser.add_argument("--subject", type=str, help="Subject filter (e.g. English, Hindi, Science, Sanskrit)")
    parser.add_argument("--search", type=str, help="Search text in title or subject")
    parser.add_argument("--list", action="store_true", help="List matching books without downloading")
    parser.add_argument("--auto-popular", action="store_true", help="Download core popular Bihar Board textbooks")
    parser.add_argument("--output-dir", type=str, default=DEFAULT_OUT_DIR, help="Destination folder for PDF")
    parser.add_argument("--push", action="store_true", help="Auto git add, commit, and push to GitHub")

    args = parser.parse_args()

    if args.list:
        results = list_books(class_id=args.class_num, subject=args.subject, search=args.search)
        print(f"\nFound {len(results)} matching books on BSTBPC:")
        for b in results:
            print(f"  [ID: {b.get('id'):3d}] Class {b.get('classId'):2d} | {b.get('title')} ({b.get('subject')})")
        return

    if args.book_id:
        download_book_by_id(args.book_id, out_dir=args.output_dir, push=args.push)
        return

    if args.auto_popular:
        print(f">> Starting Auto-Popular BSTBPC Download Queue ({len(POPULAR_BSEB_BOOKS)} books)...", flush=True)
        for item in POPULAR_BSEB_BOOKS:
            print(f"\n>>> Processing: {item['name']} (ID {item['id']} | Class {item['class']})", flush=True)
            download_book_by_id(item["id"], out_dir=args.output_dir, push=args.push)
        return

    # If search or class provided without list, find matching and download first match
    if args.search or args.class_num or args.subject:
        results = list_books(class_id=args.class_num, subject=args.subject, search=args.search)
        if not results:
            print(f"No books matched your criteria (class={args.class_num}, subject={args.subject}, search={args.search})")
            return
        target = results[0]
        print(f">> Selected matching book: [ID {target.get('id')}] {target.get('title')} (Class {target.get('classId')})")
        download_book_by_id(target.get("id"), out_dir=args.output_dir, push=args.push)
        return

    parser.print_help()

if __name__ == "__main__":
    main()
