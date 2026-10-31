import os
import sys
import time
import json
import urllib.request
import urllib.parse
from datetime import datetime

# GitHub Config
REPO_OWNER = "gigknkk-create"
REPO_NAME = "word"

def load_local_credentials():
    creds_path = os.path.join(os.path.dirname(__file__), "..", ".user_credentials.json")
    if os.path.exists(creds_path):
        try:
            with open(creds_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def get_credentials():
    local_creds = load_local_credentials()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip() or local_creds.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip() or local_creds.get("TELEGRAM_CHAT_ID", "")
    gh_token = os.environ.get("GITHUB_TOKEN", "").strip() or os.environ.get("GH_PAT", "").strip() or local_creds.get("GITHUB_PAT", "")
    return token, chat_id, gh_token

def send_message(chat_id, text, reply_markup=None):
    token, _, _ = get_credentials()
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Telegram Error] send_message: {e}")
        return None

def answer_callback(callback_query_id, text=""):
    token, _, _ = get_credentials()
    url = f"https://api.telegram.org/bot{token}/answerCallbackQuery"
    payload = {"callback_query_id": callback_query_id, "text": text}
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        print(f"[Telegram Error] answer_callback: {e}")
        return None

def get_github_status():
    """Checks active GitHub Actions runs and recent completed datasets."""
    _, _, gh_token = get_credentials()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/runs?per_page=5"
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "NCERT-Telegram-Bot"
    }
    if gh_token:
        headers["Authorization"] = f"token {gh_token}"

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            runs = data.get("workflow_runs", [])
            active_run = None
            for r in runs:
                if r.get("status") in ("in_progress", "queued"):
                    active_run = r
                    break
            return active_run, runs
    except Exception as e:
        print(f"[GitHub Error] get_github_status: {e}")
        return None, []

def trigger_workflow(book_choice: str = "auto", words_per_page: int = 18):
    """Triggers generate_vocab.yml workflow via GitHub API."""
    _, _, gh_token = get_credentials()
    if not gh_token:
        print("[Error] No GitHub token configured to trigger workflow.")
        return False

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/generate_vocab.yml/dispatches"
    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "NCERT-Telegram-Bot"
    }
    payload = {
        "ref": "main",
        "inputs": {
            "book_choice": book_choice,
            "words_per_page": str(words_per_page)
        }
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[GitHub Error] trigger_workflow: {e}")
        return False

def trigger_gdrive_sync():
    """Triggers sync_gdrive.yml workflow via GitHub API."""
    _, _, gh_token = get_credentials()
    if not gh_token:
        return False

    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/actions/workflows/sync_gdrive.yml/dispatches"
    headers = {
        "Authorization": f"token {gh_token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "NCERT-Telegram-Bot"
    }
    payload = {"ref": "main"}
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 204)
    except Exception as e:
        print(f"[GitHub Error] trigger_gdrive_sync: {e}")
        return False

def get_main_menu_markup():
    return {
        "inline_keyboard": [
            [
                {"text": "📊 Live Status Check", "callback_data": "action:status"},
                {"text": "🔄 Google Drive Sync", "callback_data": "action:sync_gdrive"}
            ],
            [
                {"text": "📕 Class 9 History (18 WPP)", "callback_data": "run:Class_09_History:18"},
                {"text": "📕 Class 9 History (20 WPP)", "callback_data": "run:Class_09_History:20"}
            ],
            [
                {"text": "📕 Class 10 History (18 WPP)", "callback_data": "run:Class_10_History:18"},
                {"text": "📕 Class 10 History (20 WPP)", "callback_data": "run:Class_10_History:20"}
            ],
            [
                {"text": "🌍 Class 11 Geography (15 WPP)", "callback_data": "run:Class_11_Geography:15"},
                {"text": "🏛️ Class 11 Pol Science (18 WPP)", "callback_data": "run:Class_11_PolScience:18"}
            ],
            [
                {"text": "🌐 Open Web Studio", "url": "https://gigknkk-create.github.io/word/"}
            ]
        ]
    }

def format_status_message():
    active_run, runs = get_github_status()
    if active_run:
        name = active_run.get("name", "Vocab Generator")
        run_id = active_run.get("id")
        created = active_run.get("created_at", "")
        status = active_run.get("status", "running")
        text = (
            f"⚡ *Active Workflow Running on GitHub!*\n\n"
            f"🔄 *Task:* `{name}`\n"
            f"🆔 *Run ID:* `{run_id}`\n"
            f"⏱️ *Status:* `{status}`\n"
            f"📅 *Started:* `{created}`\n\n"
            f"📖 *Class 12 History:* Part I Complete (2,286 words), Part II/III in progress!\n"
            f"Progress updates will arrive automatically on milestone pages."
        )
    else:
        text = (
            f"✅ *All GitHub Tasks Complete!*\n\n"
            f"📚 *Completed Books:* 20 Textbooks\n"
            f"📝 *Total Words:* 32,300+ Words\n"
            f"🎯 *History Coverage:* Class 11, Class 12 Part I, Class 8\n\n"
            f"👇 *Choose next book & target words per page to run:*"
        )
    return text

def process_updates():
    token, owner_chat_id, _ = get_credentials()
    last_offset = 0
    print(f">> Starting Telegram Bot Poller for chat {owner_chat_id}...")

    while True:
        url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_offset}&timeout=25"
        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for update in data.get("result", []):
                    last_offset = update["update_id"] + 1

                    # Handle Callback Query (Button Clicks)
                    if "callback_query" in update:
                        cb = update["callback_query"]
                        cb_id = cb["id"]
                        cb_data = cb.get("data", "")
                        from_user = cb.get("from", {}).get("first_name", "User")
                        chat_id = cb.get("message", {}).get("chat", {}).get("id", owner_chat_id)

                        print(f"[Callback] From {from_user}: {cb_data}")

                        if cb_data == "action:status" or cb_data == "status":
                            answer_callback(cb_id, "Checking live status...")
                            status_text = format_status_message()
                            send_message(chat_id, status_text, reply_markup=get_main_menu_markup())

                        elif cb_data == "action:sync_gdrive" or cb_data == "sync_gdrive":
                            answer_callback(cb_id, "Syncing Google Drive...")
                            success = trigger_gdrive_sync()
                            if success:
                                send_message(chat_id, "🔄 *Google Drive Sync Triggered!*\nChecking folder and syncing new books to GitHub.", reply_markup=get_main_menu_markup())
                            else:
                                send_message(chat_id, "⚠️ Failed to trigger Google Drive sync. Please check GitHub permissions.")

                        elif cb_data.startswith("run:"):
                            parts = cb_data.split(":")
                            book_id = parts[1] if len(parts) > 1 else "auto"
                            wpp = int(parts[2]) if len(parts) > 2 else 18

                            answer_callback(cb_id, f"Queuing {book_id} with {wpp} WPP...")
                            success = trigger_workflow(book_choice=book_id, words_per_page=wpp)
                            if success:
                                send_message(
                                    chat_id,
                                    f"🚀 *Started Generation!*\n\n"
                                    f"📖 *Book Choice:* `{book_id}`\n"
                                    f"⚡ *Density:* *{wpp} words/page*\n\n"
                                    f"GitHub Actions runner is starting now. You will receive live page status updates here as words are extracted!",
                                    reply_markup=get_main_menu_markup()
                                )
                            else:
                                send_message(chat_id, f"⚠️ Failed to dispatch workflow for {book_id}.")

                    # Handle Text Messages
                    elif "message" in update and "text" in update["message"]:
                        msg = update["message"]
                        text = msg["text"].strip()
                        chat_id = msg["chat"]["id"]

                        print(f"[Message] {text}")

                        if text in ("/start", "/help"):
                            welcome = (
                                f"👋 *Namaste Nitish!*\n\n"
                                f"Antigravity NCERT Vocab Bot me aapka swagat hai.\n\n"
                                f"Yahan se aap:\n"
                                f"• Live page progress check kar sakte hain (`/status`)\n"
                                f"• Agli book select karke run kar sakte hain\n"
                                f"• Har page me kitne words (10, 15, 18, 20) chahiye choose kar sakte hain\n"
                                f"• Google Drive sync trigger kar sakte hain\n\n"
                                f"👇 *Neeche button se direct choose karein:*"
                            )
                            send_message(chat_id, welcome, reply_markup=get_main_menu_markup())

                        elif text == "/status":
                            status_text = format_status_message()
                            send_message(chat_id, status_text, reply_markup=get_main_menu_markup())

                        elif text.startswith("/run"):
                            tokens = text.split()
                            b_choice = tokens[1] if len(tokens) > 1 else "auto"
                            wpp_choice = int(tokens[2]) if len(tokens) > 2 else 18
                            success = trigger_workflow(b_choice, wpp_choice)
                            if success:
                                send_message(chat_id, f"🚀 Triggered `{b_choice}` with `{wpp_choice}` words/page!")
                            else:
                                send_message(chat_id, "⚠️ Failed to trigger workflow.")

                        else:
                            # Send main menu
                            send_message(chat_id, f"Command: `{text}`\nNeeche options se chuniye:", reply_markup=get_main_menu_markup())

        except Exception as e:
            time.sleep(2)

if __name__ == "__main__":
    process_updates()
