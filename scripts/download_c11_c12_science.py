#!/usr/bin/env python3
"""
Downloads and compiles Class 11 and Class 12 Science textbooks (Physics, Chemistry, Biology)
from official NCERT servers, optimizes them under 90MB, and places them into books/ folder.
"""

import os
import sys
import zipfile
import tempfile
import requests
import urllib3
import fitz
import re
from PIL import Image
import io

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
sys.stdout.reconfigure(encoding='utf-8')

REPO_BOOKS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "books"))
MASTER_DIR = r"D:\NCERT_Books_Class_1_to_12"

session = requests.Session()
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://ncert.nic.in/textbook.php'
})

SCIENCE_BOOKS = [
    # Class 11
    {"class": 11, "code": "keph1", "title": "Class_11_Physics_Part_I", "clean_title": "Class 11 Physics Part I.pdf"},
    {"class": 11, "code": "keph2", "title": "Class_11_Physics_Part_II", "clean_title": "Class 11 Physics Part II.pdf"},
    {"class": 11, "code": "kech1", "title": "Class_11_Chemistry_Part_I", "clean_title": "Class 11 Chemistry Part I.pdf"},
    {"class": 11, "code": "kech2", "title": "Class_11_Chemistry_Part_II", "clean_title": "Class 11 Chemistry Part II.pdf"},
    {"class": 11, "code": "kebo1", "title": "Class_11_Biology", "clean_title": "Class 11 Biology.pdf"},
    # Class 12
    {"class": 12, "code": "leph1", "title": "Class_12_Physics_Part_I", "clean_title": "Class 12 Physics Part I.pdf"},
    {"class": 12, "code": "leph2", "title": "Class_12_Physics_Part_II", "clean_title": "Class 12 Physics Part II.pdf"},
    {"class": 12, "code": "lech1", "title": "Class_12_Chemistry_Part_I", "clean_title": "Class 12 Chemistry Part I.pdf"},
    {"class": 12, "code": "lech2", "title": "Class_12_Chemistry_Part_II", "clean_title": "Class 12 Chemistry Part II.pdf"},
    {"class": 12, "code": "lebo1", "title": "Class_12_Biology", "clean_title": "Class 12 Biology.pdf"},
]

def compress_pdf_if_needed(doc: fitz.Document, max_mb: float = 90.0) -> fitz.Document:
    buf = io.BytesIO()
    doc.save(buf, deflate=True, garbage=4)
    size_mb = buf.tell() / (1024 * 1024)
    if size_mb <= max_mb:
        print(f"      Size is {size_mb:.2f} MB (within {max_mb} MB limit).", flush=True)
        return doc

    print(f"      [OPTIMIZING] Size is {size_mb:.2f} MB > {max_mb} MB. Downsampling images...", flush=True)
    for p_idx in range(doc.page_count):
        page = doc[p_idx]
        images = page.get_images(full=True)
        for img in images:
            xref = img[0]
            try:
                base_img = doc.extract_image(xref)
                if not base_img:
                    continue
                pil_img = Image.open(io.BytesIO(base_img["image"]))
                if pil_img.width > 800 or pil_img.height > 800:
                    pil_img.thumbnail((800, 800), Image.Resampling.LANCZOS)
                out_io = io.BytesIO()
                pil_img.convert("RGB").save(out_io, format="JPEG", quality=75, optimize=True)
                doc.update_stream(xref, out_io.getvalue())
            except Exception:
                continue
    return doc

def download_book(b):
    code = b["code"]
    title = b["title"]
    c_pad = f"Class_{b['class']:02d}"
    out_master_dir = os.path.join(MASTER_DIR, c_pad)
    os.makedirs(out_master_dir, exist_ok=True)
    out_repo_file = os.path.join(REPO_BOOKS_DIR, f"{title}.pdf")
    out_master_file = os.path.join(out_master_dir, b["clean_title"])

    if os.path.exists(out_repo_file) and os.path.getsize(out_repo_file) > 1024 * 1024:
        print(f">> [EXISTS] {title}.pdf already downloaded ({os.path.getsize(out_repo_file)/(1024*1024):.1f} MB). Skipping.", flush=True)
        return

    url = f"https://ncert.nic.in/textbook/pdf/{code}dd.zip"
    print(f"\n{'='*70}", flush=True)
    print(f"📥 Downloading: {title} ({url})", flush=True)
    print(f"{'='*70}", flush=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, f"{code}.zip")
        resp = session.get(url, verify=False, stream=True, timeout=90)
        resp.raise_for_status()
        with open(zip_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=131072):
                if chunk:
                    f.write(chunk)
        print(f"  Archive downloaded: {os.path.getsize(zip_path)/(1024*1024):.2f} MB", flush=True)

        extract_dir = os.path.join(tmpdir, "extract")
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        all_pdfs = []
        for root, _, files in os.walk(extract_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    all_pdfs.append(os.path.join(root, f))

        def sort_key(p):
            fn = os.path.basename(p).lower()
            if 'ps' in fn or 'preface' in fn:
                return (0, 0, fn)
            m = re.search(r'([0-9]+)', fn)
            if m:
                return (1, int(m.group(1)), fn)
            if 'an' in fn or 'ans' in fn or 'appendix' in fn:
                return (2, 0, fn)
            return (3, 0, fn)

        all_pdfs = sorted(all_pdfs, key=sort_key)
        print(f"  Found {len(all_pdfs)} chapters/parts. Merging into single volume...", flush=True)

        merged = fitz.open()
        for pdf_p in all_pdfs:
            try:
                ch = fitz.open(pdf_p)
                merged.insert_pdf(ch)
                ch.close()
            except Exception as e:
                print(f"    [WARN] Failed to merge {os.path.basename(pdf_p)}: {e}", flush=True)

        merged = compress_pdf_if_needed(merged, max_mb=90.0)

        merged.save(out_repo_file, deflate=True, garbage=4)
        if os.path.exists(out_master_dir):
            try:
                merged.save(out_master_file, deflate=True, garbage=4)
            except Exception:
                pass
        merged.close()

        final_mb = os.path.getsize(out_repo_file) / (1024 * 1024)
        print(f"✅ Successfully compiled: {title}.pdf ({final_mb:.2f} MB)", flush=True)

def main():
    print(f">> Starting Class 11 & 12 Science Downloader ({len(SCIENCE_BOOKS)} books)...", flush=True)
    for b in SCIENCE_BOOKS:
        try:
            download_book(b)
        except Exception as err:
            print(f"❌ Error downloading {b['title']}: {err}", flush=True)
    print("\n🎉 All Class 11 & 12 Science downloads completed!", flush=True)

if __name__ == "__main__":
    main()
