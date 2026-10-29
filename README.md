# NCERT Vocab Cloud (Autonomous GitHub Actions Generator)

Autonomous, cloud-native NCERT English Vocabulary Dataset generator powered by Google Gemini and GitHub Actions.

## Features
- **10 Words Per Page**: Deep vocabulary enrichment per page.
- **Category Tagging**: Explicit `"Medium"` and `"Hard"` categories for every word.
- **Complete Schema**: Word, IPA pronunciation, Hindi pronunciation, Part of Speech, English meaning, Hindi meaning (शुद्ध हिंदी), example sentence.
- **100% Autonomous**: Runs on GitHub's cloud infrastructure. No laptop or internet required after triggering.
- **Auto-Commit**: Automatically pushes the generated dataset to `datasets/` in this repository.

## Setup Instructions

1. **Add Gemini Secret**:
   - Go to your repository on GitHub: **Settings ➔ Secrets and variables ➔ Actions**.
   - Click **New repository secret**.
   - Name: `GEMINI_API_KEY`
   - Value: `YOUR_GEMINI_API_KEY` (paste your API key here).

2. **Triggering from Phone or PC**:
   - In GitHub, go to the **Actions** tab.
   - Click on **NCERT Cloud Vocab Generator**.
   - Click **Run workflow**, choose your page range, and hit start!
   - You can close your browser/phone — GitHub Actions will finish the job and commit the JSON!
