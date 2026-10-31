import os
import sys
import re
import shutil
import tempfile
import subprocess
import json

def extract_folder_id(raw_input: str) -> str:
    """Extracts a clean Google Drive folder ID from a URL or raw ID string."""
    raw_input = raw_input.strip()
    match = re.search(r"folders/([a-zA-Z0-9_-]+)", raw_input)
    if match:
        return match.group(1)
    # Check if raw_input is just the alphanumeric ID
    clean = re.sub(r"[^a-zA-Z0-9_-]", "", raw_input)
    return clean

def compress_pdf_if_large(input_path: str, max_mb: float = 60.0) -> str:
    """If PDF is larger than max_mb, downsample images using PyMuPDF."""
    file_size_mb = os.path.getsize(input_path) / (1024 * 1024)
    if file_size_mb <= max_mb:
        return input_path

    print(f">> PDF is {file_size_mb:.1f} MB (exceeds {max_mb} MB). Compressing before commit...")
    try:
        import fitz
        from PIL import Image
        import io

        doc = fitz.open(input_path)
        new_doc = fitz.open()

        for page_idx in range(len(doc)):
            page = doc[page_idx]
            # Render page at 120 DPI
            pix = page.get_pixmap(dpi=120)
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            img_buf = io.BytesIO()
            img.save(img_buf, format="JPEG", quality=65, optimize=True)
            img_bytes = img_buf.getvalue()

            new_page = new_doc.new_page(width=page.rect.width, height=page.rect.height)
            new_page.insert_image(new_page.rect, stream=img_bytes)

        compressed_path = input_path.replace(".pdf", "_compressed.pdf")
        new_doc.save(compressed_path, garbage=4, deflate=True)
        new_doc.close()
        doc.close()

        comp_size_mb = os.path.getsize(compressed_path) / (1024 * 1024)
        print(f">> Compressed {file_size_mb:.1f} MB -> {comp_size_mb:.1f} MB")
        os.remove(input_path)
        shutil.move(compressed_path, input_path)
        return input_path
    except Exception as e:
        print(f">> Warning: PDF compression failed ({e}), using original.")
        return input_path

def download_via_service_account(folder_id: str, sa_json_str: str, dest_dir: str):
    """Download PDFs using official Google Drive API with Service Account credentials."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseDownload
    import io

    print(">> Authenticating with Google Drive API via Service Account...")
    sa_info = json.loads(sa_json_str)
    scopes = ["https://www.googleapis.com/auth/drive.readonly"]
    creds = service_account.Credentials.from_service_account_info(sa_info, scopes=scopes)
    service = build("drive", "v3", credentials=creds)

    query = f"'{folder_id}' in parents and mimeType = 'application/pdf' and trashed = false"
    results = service.files().list(q=query, fields="files(id, name, size)").execute()
    files = results.get("files", [])

    print(f">> Found {len(files)} PDF file(s) in Drive folder.")
    downloaded_files = []

    for file_meta in files:
        file_id = file_meta["id"]
        file_name = file_meta["name"]
        local_path = os.path.join(dest_dir, file_name)

        print(f">> Downloading '{file_name}' ({int(file_meta.get('size', 0)) / 1024 / 1024:.1f} MB)...")
        request = service.files().get_media(fileId=file_id)
        with open(local_path, "wb") as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                if status:
                    print(f"   Downloading: {int(status.progress() * 100)}%", end="\r")
        print(f"   Downloaded '{file_name}' successfully.")
        downloaded_files.append(local_path)

    return downloaded_files

def download_via_gdown(folder_id: str, dest_dir: str):
    """Download public Google Drive folder using gdown."""
    import gdown
    folder_url = f"https://drive.google.com/drive/folders/{folder_id}"
    print(f">> Downloading public Drive folder via gdown: {folder_url}")
    try:
        downloaded = gdown.download_folder(url=folder_url, output=dest_dir, quiet=False, use_cookies=False)
        pdf_files = []
        for root, _, files in os.walk(dest_dir):
            for f in files:
                if f.lower().endswith(".pdf"):
                    pdf_files.append(os.path.join(root, f))
        return pdf_files
    except Exception as e:
        print(f">> Error downloading folder with gdown: {e}")
        return []

def main():
    folder_input = os.environ.get("GDRIVE_FOLDER_ID", "").strip()
    sa_key = os.environ.get("GDRIVE_SERVICE_ACCOUNT_KEY", "").strip()
    target_books_dir = os.path.abspath("books")
    os.makedirs(target_books_dir, exist_ok=True)

    if not folder_input:
        print("[ERROR] No GDRIVE_FOLDER_ID specified. Set it in repository secrets or workflow inputs.")
        sys.exit(1)

    folder_id = extract_folder_id(folder_input)
    print(f">> Target Google Drive Folder ID: {folder_id}")

    temp_dir = tempfile.mkdtemp(prefix="gdrive_sync_")
    try:
        downloaded_pdfs = []
        if sa_key:
            try:
                downloaded_pdfs = download_via_service_account(folder_id, sa_key, temp_dir)
            except Exception as ex:
                print(f">> Service Account download failed ({ex}). Trying public gdown fallback...")
                downloaded_pdfs = download_via_gdown(folder_id, temp_dir)
        else:
            print(">> No Service Account key provided. Using public folder mode (gdown)...")
            downloaded_pdfs = download_via_gdown(folder_id, temp_dir)

        if not downloaded_pdfs:
            print(">> No PDF files downloaded from Google Drive.")
            return

        existing_books = set(f.lower() for f in os.listdir(target_books_dir) if f.lower().endswith(".pdf"))
        newly_synced_books = []

        for src_path in downloaded_pdfs:
            file_name = os.path.basename(src_path)
            clean_name = re.sub(r"[^\w\s\.-]", "_", file_name).strip()

            if clean_name.lower() in existing_books:
                print(f">> [SKIP] '{clean_name}' already exists in repo books/ folder.")
                continue

            # Compress if needed
            processed_src = compress_pdf_if_large(src_path, max_mb=60.0)
            target_dest = os.path.join(target_books_dir, clean_name)
            shutil.copy2(processed_src, target_dest)
            print(f">> [ADDED] Copied '{clean_name}' to {target_books_dir}/")
            newly_synced_books.append(clean_name)

        if not newly_synced_books:
            print(">> All books in Google Drive already exist in the repository. Nothing new to sync.")
            return

        print(f"\n>> {len(newly_synced_books)} new book(s) synced from Google Drive:")
        for b in newly_synced_books:
            print(f"   + {b}")

        # If running in GitHub Actions, commit each book individually
        if os.environ.get("GITHUB_ACTIONS") == "true":
            subprocess.run(["git", "config", "--global", "user.name", "github-actions[bot]"], check=False)
            subprocess.run(["git", "config", "--global", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)

            for b in newly_synced_books:
                b_path = os.path.join("books", b)
                subprocess.run(["git", "add", b_path], check=False)
                c_res = subprocess.run(["git", "commit", "-m", f"feat(books): add {b} from Google Drive"], capture_output=True, text=True)
                if c_res.returncode == 0:
                    subprocess.run(["git", "rebase", "--abort"], capture_output=True, check=False)
                    subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)
                    p_res = subprocess.run(["git", "push", "origin", "HEAD:main"])
                    if p_res.returncode == 0:
                        print(f">> [PUSHED] Successfully pushed '{b}' to main!")
                    else:
                        print(f">> [PUSH ERROR] Failed to push '{b}'")
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
