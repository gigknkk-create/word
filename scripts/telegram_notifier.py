import os
import json
import urllib.request
import urllib.parse

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
    return token, chat_id

def send_telegram_message(text: str, reply_markup=None):
    """Sends a Telegram message with optional inline keyboard buttons."""
    token, chat_id = get_credentials()
    if not token or not chat_id:
        print("[Telegram] No token or chat_id configured. Skipping.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": False
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=data,
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("ok", False)
    except Exception as e:
        print(f"[Telegram] Warning: Failed to send message: {e}")
        return False

def send_page_progress(book_title: str, current_page: int, total_pages: int, total_words: int, words_per_page: int):
    """Notifies live page progress to Telegram."""
    pct = (current_page / max(1, total_pages)) * 100
    bar_len = 10
    filled = int(round(bar_len * current_page / float(total_pages)))
    bar = "▓" * filled + "░" * (bar_len - filled)

    text = (
        f"⏳ *NCERT Vocab Generator In-Progress*\n\n"
        f"📖 *Book:* `{book_title}`\n"
        f"📊 *Progress:* `[{bar}]` *{pct:.1f}%*\n"
        f"📄 *Page Status:* Page *{current_page}* of *{total_pages}*\n"
        f"📝 *Words Generated:* *{total_words}* words\n"
        f"⚡ *Target Density:* *{words_per_page}* words/page\n"
    )
    return send_telegram_message(text)

def send_book_completion(book_title: str, total_pages: int, total_words: int, words_per_page: int):
    """Sends celebratory completion message with interactive buttons for next books."""
    avg_wpp = total_words / max(1, total_pages)
    text = (
        f"🎉 *Book Generation Completed & Saved!* 🎉\n\n"
        f"📖 *Book:* `{book_title}`\n"
        f"📄 *Total Pages:* *{total_pages}*\n"
        f"📝 *Total Words:* *{total_words}*\n"
        f"🎯 *Density Achieved:* *{avg_wpp:.1f}* words/page\n"
        f"🌐 *Live Studio:* [View on Web](https://gigknkk-create.github.io/word/)\n\n"
        f"👇 *Agli kaun si book run karni hai aur kitne words per page? Choose below:*"
    )

    # Inline Keyboard with buttons for next books & words per page
    reply_markup = {
        "inline_keyboard": [
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
                {"text": "📊 Live Status Check", "callback_data": "status"},
                {"text": "🔄 Sync Google Drive", "callback_data": "sync_gdrive"}
            ]
        ]
    }

    return send_telegram_message(text, reply_markup=reply_markup)

if __name__ == "__main__":
    print("Testing Telegram Notifier...")
    send_book_completion("Class 12 History Themes in Indian History Part I", 127, 2286, 18)
    print("Sent test completion with buttons!")
