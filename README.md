# 📘 NCERT VocabStudio Cloud

[![GitHub Actions Status](https://img.shields.io/badge/Workflow-Autonomous%20Generator-blue?logo=github-actions)](https://github.com/gigknkk-create/word/actions)
[![Live Web App](https://img.shields.io/badge/Live%20App-GitHub%20Pages-success?logo=github)](https://gigknkk-create.github.io/word/)
[![License](https://img.shields.io/badge/License-MIT-purple)]()

Autonomous, cloud-native NCERT English Vocabulary Dataset generator and interactive study web application. Powered by **Google Gemini API cluster (3-Key Round-Robin)** and **GitHub Actions**.

---

## 🌐 Live Interactive Web App
Study the generated vocabulary in an aesthetic, responsive table:
👉 **[https://gigknkk-create.github.io/word/](https://gigknkk-create.github.io/word/)**

* **Aesthetic Table View**: Word, Category (`Medium`/`Hard`), Pronunciation (IPA + Hindi), **`🔊 Listen`** audio button, Hindi Meaning, English Meaning, and Highlighted Contextual Examples.
* **Go to Page Navigation**: Instantly jump to any page number (`1 to 124`) or flip using Left/Right arrow keys.
* **Chapter Pill**: Automatically tracks textbook chapters.
* **Global Search**: Search any English word or Hindi meaning across all 1,200+ words.
* **JSON Export**: Copy page JSON or download the full dataset with 1 click.

---

## 🤖 For AI Agents & Developers: How to Add New Books

Adding a new textbook for vocabulary generation is **100% automated**. You only need to drop the PDF file into the `books/` folder.

### Step-by-Step Instructions:
1. **Place the PDF in the `books/` folder**:
   ```bash
   books/
   ├── Class_08_History_Our_Pasts_III.pdf              # (Completed: 121 pages)
   ├── Class_09_History_India_and_Contemporary_World_I.pdf   # (Add here)
   └── Class_10_History_India_and_Contemporary_World_II.pdf  # (Add here)
   ```
2. **Commit and Push to `main`**:
   ```bash
   git add books/Your_Book_Name.pdf
   git commit -m "add(book): upload Class 9 History textbook"
   git push origin main
   ```
3. **Automatic Cloud Execution**:
   * As soon as GitHub receives any `.pdf` file inside `books/`, the workflow [`.github/workflows/generate_vocab.yml`](.github/workflows/generate_vocab.yml) **automatically triggers**.
   * [`scripts/auto_runner.py`](scripts/auto_runner.py) detects the new book.
   * It skips already complete books (e.g. Class 8) and begins extracting vocabulary for the new textbook from Page 1 to the end.
   * Once finished, GitHub Actions commits and pushes the generated dataset to `datasets/` automatically with `[skip ci]`.

---

## ⚡ Architecture & Engine Details

### 1. 3-Key Round-Robin Cluster (`KeyManager`)
The generator uses a multi-key cluster in [`scripts/generate_vocab.py`](scripts/generate_vocab.py):
* **Rotation**: Requests rotate sequentially across 3 Google Gemini API keys (Key 1 $\rightarrow$ Key 2 $\rightarrow$ Key 3 $\rightarrow$ Key 1...).
* **Instant 429 Failover**: If any key encounters HTTP 429, it is placed on a 40s cooldown, and the engine **instantly switches to the next active key without stalling**.
* **High Throughput**: Pacing delay is optimized to **2.0 seconds**, generating a complete 130-page textbook in **~3 to 4 minutes**.
* **Daily Quota**: Combined capacity of **4,500 requests / day**.

### 2. Verified Active Models
* `gemini-3-flash-preview` (Primary fast endpoint)
* `gemini-3.1-flash-lite` (High throughput lightweight model)
* `gemini-3.5-flash` (Resilient fallback)

### 3. Output Schema (per word)
```json
{
  "word": "Planter",
  "category": "Medium",
  "pronunciation": "/ˈplæn.tər/",
  "pronunciation_hindi": "प्लैंटर",
  "pos": "Noun",
  "english_meaning": "The owner or manager of a plantation.",
  "hindi_meaning": "बगान का मालिक",
  "example": "The planter forced the workers to cultivate indigo on their fertile land.",
  "page_number": 50,
  "book": "Class_08_History_Our_Pasts_III",
  "class": 8
}
```

---

## 📊 How to Check Live Progress During Generation

You can track exactly how many pages have been completed in real-time using either of these methods:

### Method 1: GitHub Actions Live Streaming Log (Visual UI)
1. Open the repository on GitHub: [https://github.com/gigknkk-create/word/actions](https://github.com/gigknkk-create/word/actions).
2. Click on the running workflow: **"NCERT Vocab Auto-Generator on Upload"**.
3. Click on the job **`auto_generate`** $\rightarrow$ expand **`Run Auto Vocabulary Generator`**.
4. You will see real-time streaming output showing the exact progress:
   ```text
   [*] Page 42/128: Extracting 10 words via Gemini...
   [OK] Page 42/128: Saved 10 words. (New this run: 420 | Total stored: 420)
   [*] Page 43/128: Extracting 10 words via Gemini...
   [OK] Page 43/128: Saved 10 words. (New this run: 430 | Total stored: 430)
   ```
   The numbers update every ~2 seconds as pages finish!

### Method 2: One-Click Status Script (CLI)
Run the bundled status script from your terminal:
```bash
python scripts/check_status.py
```
This queries the GitHub Actions API and prints the current status, run ID, and direct streaming link.

---

## 📁 Repository Structure

```text
├── .github/
│   └── workflows/
│       └── generate_vocab.yml        # Auto-trigger on books/**.pdf push
├── books/
│   └── Class_08_History_Our_Pasts_III.pdf # (Upload new textbooks here)
├── datasets/
│   ├── class_08_data.js             # Fast web companion
│   └── class_08_history_our_pasts_iii.json # Full 1,210-word dataset
├── scripts/
│   ├── auto_runner.py               # Book detector & pipeline coordinator
│   ├── generate_vocab.py            # 3-Key cluster generator
│   └── check_status.py              # CLI progress checker
├── index.html                       # Aesthetic Interactive VocabStudio Web App
└── README.md                        # Project documentation
```

---

## 🔒 Secrets Configuration
The repository uses a single multi-key secret configured in **Settings ➔ Secrets and variables ➔ Actions**:
* `GEMINI_API_KEY`: Comma-separated list of Gemini API keys:
  `KEY_1,KEY_2,KEY_3`

---

*Crafted for Indian NCERT School Students & Educators.*
