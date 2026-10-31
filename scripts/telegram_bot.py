import os
import sys
import time
import json
import re
import shutil
import subprocess
import urllib.request
import urllib.parse

# Repositories & Paths
REPO_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASETS_DIR = os.path.join(REPO_DIR, "datasets")
BOOKS_DIR = os.path.join(REPO_DIR, "books")
MASTER_BOOKS_DIR = "D:\\NCERT_Books_Class_1_to_12"

REPO_OWNER = "gigknkk-create"
REPO_NAME = "word"

# Credentials (loaded from environment or git-ignored .user_credentials.json)
DEFAULT_BOT_TOKEN = ""
DEFAULT_CHAT_ID = ""
DEFAULT_GH_PAT = ""

def load_local_credentials():
    creds_path = os.path.join(REPO_DIR, ".user_credentials.json")
    if os.path.exists(creds_path):
        try:
            with open(creds_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def get_credentials():
    local_creds = load_local_credentials()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or local_creds.get("TELEGRAM_BOT_TOKEN", "") or DEFAULT_BOT_TOKEN
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or local_creds.get("TELEGRAM_CHAT_ID", "") or DEFAULT_CHAT_ID
    gh_token = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GH_PAT", "").strip() or local_creds.get("GITHUB_PAT", "") or DEFAULT_GH_PAT
    gemini_keys_str = os.environ.get("GEMINI_API_KEYS", "").strip() or local_creds.get("GEMINI_API_KEYS", "")
    gemini_keys = [k.strip() for k in gemini_keys_str.split(",") if k.strip()]
    return token, chat_id, gh_token, gemini_keys

def escape_html(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def send_message(chat_id, text, reply_markup=None):
    token, _, _, _ = get_credentials()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as he:
        err_msg = he.read().decode("utf-8", errors="ignore")
        print(f"[Telegram HTTP Error {he.code}] {err_msg}")
        return None
    except Exception as e:
        print(f"[Telegram Error] send_message: {e}")
        return None

def answer_callback(callback_query_id, text=""):
    token, _, _, _ = get_credentials()
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": str(callback_query_id), "text": text}
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Telegram Warning] answer_callback: {e}")
        return None

def normalize_title(name: str) -> str:
    s = name.lower()
    s = re.sub(r"class[_\s]*([0-9])(?![0-9])", r"class0\1", s)
    s = re.sub(r"class[_\s]*([0-9]{2,})", r"class\1", s)
    s = re.sub(r"[^a-z0-9]", "", s)
    return s

def get_catalog():
    """Scans datasets and local master directory to determine completed vs pending books."""
    completed_norm = set()
    completed_details = []

    if os.path.exists(DATASETS_DIR):
        for f in os.listdir(DATASETS_DIR):
            if f.endswith(".json"):
                stem = os.path.splitext(f)[0]
                completed_norm.add(normalize_title(stem))
                try:
                    with open(os.path.join(DATASETS_DIR, f), "r", encoding="utf-8") as jf:
                        jd = json.load(jf)
                    pages_cnt = len(jd.get("pages", {}))
                    words_cnt = sum(len(p) for p in jd.get("pages", {}).values())
                    completed_details.append({
                        "filename": f,
                        "title": jd.get("book_title", stem),
                        "pages": pages_cnt,
                        "words": words_cnt
                    })
                except Exception:
                    completed_details.append({"filename": f, "title": stem, "pages": 0, "words": 0})

    pending_books = []
    if os.path.exists(MASTER_BOOKS_DIR):
        for root, dirs, files in os.walk(MASTER_BOOKS_DIR):
            for f in sorted(files):
                if f.lower().endswith(".pdf"):
                    clean_stem = f.replace(".pdf", "")
                    norm = normalize_title(clean_stem)
                    is_done = any(norm in c or c in norm for c in completed_norm)
                    if not is_done:
                        category = "Other"
                        low = f.lower()
                        if "history" in low:
                            category = "History"
                        elif "geography" in low:
                            category = "Geography"
                        elif "political" in low or "civics" in low:
                            category = "Political Science"
                        elif "economic" in low:
                            category = "Economics"

                        key = re.sub(r"[^a-zA-Z0-9_]", "_", clean_stem).lower()
                        key = re.sub(r"_+", "_", key).strip("_")

                        pending_books.append({
                            "key": key,
                            "filename": f,
                            "filepath": os.path.join(root, f),
                            "category": category,
                            "size_mb": round(os.path.getsize(os.path.join(root, f)) / (1024 * 1024), 1)
                        })

    cat_order = {"History": 1, "Geography": 2, "Political Science": 3, "Economics": 4, "Other": 5}
    pending_books.sort(key=lambda x: (cat_order.get(x["category"], 99), x["filename"]))

    # Assign a compact integer index 0..N
    for idx, b in enumerate(pending_books):
        b["idx"] = idx

    return completed_details, pending_books

def get_dynamic_menu():
    """Builds inline keyboard options strictly for pending books with short callback_data."""
    _, pending = get_catalog()

    keyboard = []

    # History Books Buttons (Top Priority)
    history_pending = [b for b in pending if b["category"] == "History"]
    for b in history_pending:
        # e.g. Class 9 History, Class 10 History
        short_name = b["filename"].replace(" - India and the Contemporary World", "").replace(".pdf", "").replace("Social Science - ", "").replace(" (History)", "")
        # Compact callback_data <= 64 bytes: p:<idx>:<wpp>
        keyboard.append([
            {"text": f"📕 {short_name} (18 WPP)", "callback_data": f"p:{b['idx']}:18"},
            {"text": f"📕 {short_name} (20 WPP)", "callback_data": f"p:{b['idx']}:20"}
        ])

    # Geography / Pol Sci / Economics pending samples
    other_pending = [b for b in pending if b["category"] != "History"]
    row = []
    for b in other_pending[:4]:
        short_label = b["filename"][:20].replace(".pdf", "")
        row.append({"text": f"📘 {short_label}", "callback_data": f"p:{b['idx']}:18"})
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    # General Action Buttons (callback_data <= 15 bytes)
    keyboard.append([
        {"text": "📊 Live Studio Status", "callback_data": "act:status"},
        {"text": "📚 View All Remaining", "callback_data": "act:rem"}
    ])
    keyboard.append([
        {"text": "🌐 Open Web Vocabulary Studio", "url": "https://gigknkk-create.github.io/word/"}
    ])

    return {"inline_keyboard": keyboard}

def push_book_to_github(target_book: dict, words_per_page: int = 18):
    """Pushes the selected book PDF to GitHub books/ folder to auto-trigger the workflow."""
    os.makedirs(BOOKS_DIR, exist_ok=True)
    dest_name = re.sub(r"[^a-zA-Z0-9_.-]", "_", target_book["filename"])
    dest_path = os.path.join(BOOKS_DIR, dest_name)

    print(f">> Copying '{target_book['filepath']}' to '{dest_path}'...")
    try:
        shutil.copy2(target_book["filepath"], dest_path)
    except Exception as e:
        return False, f"Failed to copy PDF file: {e}"

    try:
        subprocess.run(["git", "rebase", "--abort"], cwd=REPO_DIR, capture_output=True, check=False)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], cwd=REPO_DIR, capture_output=True, check=False)
        subprocess.run(["git", "add", f"books/{dest_name}"], cwd=REPO_DIR, check=True)
        commit_msg = f"feat(books): upload {dest_name} for auto vocabulary generation [target: {words_per_page} wpp]"
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=REPO_DIR, check=True)
        push_res = subprocess.run(["git", "push", "origin", "HEAD:main"], cwd=REPO_DIR, capture_output=True, text=True)
        if push_res.returncode != 0:
            return False, f"Git push failed: {push_res.stderr[:200]}"
    except Exception as e:
        return False, f"Git execution error: {e}"

    return True, f"Successfully pushed <b>{escape_html(target_book['filename'])}</b> to GitHub! The auto vocabulary workflow has triggered automatically."

def call_gemini(user_prompt: str):
    """Processes user input using Gemini 3.5 Flash-Lite with multi-key pool rotation."""
    _, _, _, gemini_keys = get_credentials()
    if not gemini_keys:
        return None

    completed, pending = get_catalog()
    completed_summary = f"{len(completed)} books completed, {sum(c['words'] for c in completed):,} words total (including Class 1 to 12 English, Class 8 History, Class 11 History, Class 12 History Parts I, II, III)."

    pending_list_str = "\n".join([f"- idx: {b['idx']} | key: {b['key']} | title: {b['filename']}" for b in pending[:15]])

    system_instruction = f"""You are the Antigravity NCERT Studio Bot on Telegram for user Nitish Yadav.
You are smart, fast, polite, and converse naturally in friendly Hinglish / Hindi / English.

CURRENT STATUS:
- Completed Books: {completed_summary}
- Remaining Pending Books:
{pending_list_str}

YOUR CAPABILITIES & INTENTS:
1. If the user wants to push, upload, start, or generate a book (e.g. "class 9 history push karo", "class 10 history daal do 20 words ke sath", "upload class 9"):
   Identify the matching book idx from the pending list and the target words per page (default 18 for history/social, or as specified).
   Include this EXACT tag anywhere in your reply:
   [ACTION:PUSH:<idx>:<words_per_page>]
   Example: [ACTION:PUSH:0:18]

2. If the user asks for status ("status kya hai", "kya chal raha hai", "kitna hua"):
   Include this EXACT tag:
   [ACTION:STATUS]

3. If the user asks what books are left ("kaun si book bachi hai", "list btao"):
   Include this EXACT tag:
   [ACTION:REMAINING]

4. Otherwise, answer questions helpfully and politely in Hinglish!
Keep responses concise, clear, and action-oriented. Use simple clean text or standard HTML.
"""

    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": system_instruction + "\n\nUser message: " + user_prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 300
        }
    }
    data = json.dumps(payload).encode("utf-8")

    for k in gemini_keys:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent?key={k}"
        try:
            req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=12) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
        except Exception as e:
            print(f"[Gemini Key Fallback] {e}")
            continue
    return None

def format_status_report():
    completed, pending = get_catalog()
    tot_words = sum(c["words"] for c in completed)

    msg = (
        f"<b>📊 NCERT Vocabulary Studio - Live Status</b>\n\n"
        f"✅ <b>Completed Textbooks:</b> {len(completed)} Books\n"
        f"📝 <b>Total Generated Words:</b> {tot_words:,} Words\n"
        f"🎯 <b>History Coverage:</b> Class 11 (3,546 w), Class 12 Parts I, II, III (6,894 w), Class 8 (1,210 w)\n\n"
        f"⏳ <b>Pending Books in Queue:</b> {len(pending)} Books\n"
        f"• Class 9 History (India & Contemporary World I)\n"
        f"• Class 10 History (India & Contemporary World II)\n"
        f"• Geography, Pol Science, Economics (Classes 9-12)\n\n"
        f"👇 <i>Neeche diye button se kisi bhi book ko GitHub par push karke generation shuru karein:</i>"
    )
    return msg

def format_remaining_report():
    _, pending = get_catalog()
    lines = [f"<b>📚 Remaining NCERT Books ({len(pending)} Pending):</b>\n"]

    hist = [b for b in pending if b["category"] == "History"]
    if hist:
        lines.append("<b>📕 History Books:</b>")
        for b in hist:
            lines.append(f"  • {escape_html(b['filename'])} ({b['size_mb']} MB)")

    geo = [b for b in pending if b["category"] == "Geography"]
    if geo:
        lines.append("\n<b>🌍 Geography Books:</b>")
        for b in geo[:5]:
            lines.append(f"  • {escape_html(b['filename'])}")

    pol = [b for b in pending if b["category"] == "Political Science"]
    if pol:
        lines.append("\n<b>🏛️ Political Science:</b>")
        for b in pol[:5]:
            lines.append(f"  • {escape_html(b['filename'])}")

    lines.append("\n👇 <i>Chuniye kaun si book pehle shuru karni hai:</i>")
    return "\n".join(lines)

def process_updates():
    token, owner_chat_id, _, _ = get_credentials()
    last_offset = 0
    print(f">> Starting Advanced Telegram Studio Controller (Chat ID: {owner_chat_id})...")

    while True:
        url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_offset}&timeout=25"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for update in data.get("result", []):
                    last_offset = update["update_id"] + 1

                    # 1. Handle Callback Query (Button Clicks)
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        cb_data = cb.get("data", "")
                        from_user = cb.get("from", {}).get("first_name", "User")
                        chat_id = cb.get("message", {}).get("chat", {}).get("id", owner_chat_id)

                        print(f"[Button Clicked] by {from_user}: {cb_data}")
                        answer_callback(cb_id, "Processing...")

                        if cb_data in ("act:status", "status"):
                            status_msg = format_status_report()
                            send_message(chat_id, status_msg, reply_markup=get_dynamic_menu())

                        elif cb_data in ("act:rem", "remaining"):
                            rem_msg = format_remaining_report()
                            send_message(chat_id, rem_msg, reply_markup=get_dynamic_menu())

                        elif cb_data.startswith("p:"):
                            parts = cb_data.split(":")
                            b_idx = int(parts[1])
                            wpp = int(parts[2]) if len(parts) > 2 else 18

                            _, pending = get_catalog()
                            target = None
                            for b in pending:
                                if b["idx"] == b_idx:
                                    target = b
                                    break

                            if target:
                                send_message(chat_id, f"⏳ <i>Pushing <b>{escape_html(target['filename'])}</b> to GitHub repository...</i>")
                                success, result_msg = push_book_to_github(target, words_per_page=wpp)
                                if success:
                                    response_text = (
                                        f"🚀 <b>Book Uploaded & Generation Started!</b>\n\n"
                                        f"{result_msg}\n\n"
                                        f"⚡ <b>Target Density:</b> {wpp} words/page\n"
                                        f"📊 Live page progress alerts will arrive here as pages are generated."
                                    )
                                    send_message(chat_id, response_text, reply_markup=get_dynamic_menu())
                                else:
                                    send_message(chat_id, f"⚠️ Error: {escape_html(result_msg)}", reply_markup=get_dynamic_menu())
                            else:
                                send_message(chat_id, "⚠️ Book not found in pending queue.", reply_markup=get_dynamic_menu())

                    # 2. Handle Text Messages (Powered by Gemini 3.5 Flash-Lite)
                    elif "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        text = msg["text"].strip()
                        chat_id = msg["chat"]["id"]

                        print(f"[User Message] {text}")

                        if text in ("/start", "/help"):
                            welcome = (
                                f"👋 <b>Namaste Nitish!</b>\n\n"
                                f"Antigravity NCERT Vocab AI Controller me aapka swagat hai.\n\n"
                                f"✨ <b>Features:</b>\n"
                                f"• <b>Gemini 3.5 Flash-Lite AI:</b> Aap Hinglish/Hindi me jaisa bhi likhenge, ye samajh kar book upload kar dega!\n"
                                f"• <b>Dynamic Buttons:</b> Neeche sirf wahi books dikhengi jinka data abhi nikalna baki hai.\n"
                                f"• <b>One-Click Auto Push:</b> Button dabate hi book GitHub par push ho jayegi aur generator chalu ho jayega!\n\n"
                                f"👇 <i>Neeche buttons se choose karein ya direct chat karein:</i>"
                            )
                            send_message(chat_id, welcome, reply_markup=get_dynamic_menu())

                        elif text == "/status":
                            status_msg = format_status_report()
                            send_message(chat_id, status_msg, reply_markup=get_dynamic_menu())

                        else:
                            # Process with Gemini 3.5 Flash-Lite
                            gemini_reply = call_gemini(text)
                            if gemini_reply:
                                push_match = re.search(r"\[ACTION:PUSH:(\d+):?(\d+)?\]", gemini_reply)
                                if push_match:
                                    target_idx = int(push_match.group(1))
                                    target_wpp = int(push_match.group(2)) if push_match.group(2) else 18
                                    clean_reply = re.sub(r"\[ACTION:PUSH:.*?\]", "", gemini_reply).strip()

                                    _, pending = get_catalog()
                                    target_book = None
                                    for b in pending:
                                        if b["idx"] == target_idx:
                                            target_book = b
                                            break

                                    if target_book:
                                        send_message(chat_id, f"{escape_html(clean_reply)}\n\n⏳ <i>Pushing book to GitHub...</i>")
                                        success, res_msg = push_book_to_github(target_book, words_per_page=target_wpp)
                                        if success:
                                            send_message(chat_id, f"🚀 {res_msg}", reply_markup=get_dynamic_menu())
                                        else:
                                            send_message(chat_id, f"⚠️ {escape_html(res_msg)}", reply_markup=get_dynamic_menu())
                                    else:
                                        send_message(chat_id, f"{escape_html(clean_reply)}\n\n⚠️ Could not find book index in pending list.", reply_markup=get_dynamic_menu())

                                elif "[ACTION:STATUS]" in gemini_reply:
                                    clean_reply = gemini_reply.replace("[ACTION:STATUS]", "").strip()
                                    send_message(chat_id, f"{escape_html(clean_reply)}\n\n" + format_status_report(), reply_markup=get_dynamic_menu())

                                elif "[ACTION:REMAINING]" in gemini_reply:
                                    clean_reply = gemini_reply.replace("[ACTION:REMAINING]", "").strip()
                                    send_message(chat_id, f"{escape_html(clean_reply)}\n\n" + format_remaining_report(), reply_markup=get_dynamic_menu())

                                else:
                                    send_message(chat_id, escape_html(gemini_reply), reply_markup=get_dynamic_menu())
                            else:
                                send_message(chat_id, f"Aapka sandesh mila: <i>{escape_html(text)}</i>. Neeche buttons se book select karein:", reply_markup=get_dynamic_menu())

        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    process_updates()
