# 🏛️ Automated UPSC / IAS Current Affairs Portal

An automated, high-performance, and modern daily Current Affairs portal engineered specifically for **UPSC Civil Services Examination (IAS)** preparation. 

The system operates autonomously via **GitHub Actions**, harvesting multi-source data from premier APIs and RSS feeds, synthesizing rigorous analytical briefs and full-fledged deep-dive explanations using **Groq (`openai/gpt-oss-120b`)**, and deploying a fully structured static web portal directly to **GitHub Pages**.

---

## ✨ Key Features

- **Hybrid Data Ingestion**: Combines **NewsAPI**, **Currents API**, and trusted RSS streams (*The Hindu*, *BBC*) to ensure a comprehensive daily news pool.
- **Dual-Model Groq Orchestration**: Sends separate, targeted requests to Groq to guarantee robust, unbiased, and fully populated sections for both **National News & Governance** and **International Relations & Global Affairs**.
- **Pre-Built Deep-Dive Analysis Sub-Pages**: Generates dedicated academic analysis pages for every news item during the build process, complete with extended explanations and key UPSC syllabus takeaways.
- **Visual Concentration Badges**: Automatically color-codes critical exam data (such as numeric statistics, percentages, and dates) into soft visual badges for effortless scanning and active recall.
- **Zero-Cost Automated Deployment**: Runs daily via scheduled cron jobs on GitHub Actions and publishes instantly via GitHub Pages.

---

## 🛠️ Tech Stack

- **Orchestration**: GitHub Actions (Cron & Workflow Dispatch)
- **Language**: Python 3.10+ (`requests`, `feedparser`)
- **AI Synthesis**: Groq API (`openai/gpt-oss-120b`)
- **Hosting**: GitHub Pages (Static HTML/CSS)

---

## 🚀 Quick Setup & Installation

### 1. Repository Secrets Configuration
To enable live news fetching and AI synthesis, add the following secrets to your GitHub Repository under **Settings > Secrets and variables > Actions**:

| Secret Name | Description | Source |
| :--- | :--- | :--- |
| `GROQ_API_KEY` | API Key for Groq model inference | [Groq Console](https://console.groq.com/) |
| `NEWS_API_KEY` | Developer key for top headlines | [NewsAPI.org](https://newsapi.org/) |
| `CURRENTS_API_KEY` | Developer key for global search & news | [Currents API](https://currentsapi.services/) |

### 2. Required Files Structure
Ensure your repository contains:
- `main.py` — The core automation and AI synthesis script.
- `requirements.txt` — Python dependencies (`openai>=1.0.0`, `requests>=2.31.0`, `feedparser>=6.0.10`).
- `.github/workflows/deploy.yml` — The GitHub Actions workflow file.

### 3. Local Testing
To run the generator locally on your machine:
```bash
pip install -r requirements.txt
export GROQ_API_KEY="your_groq_key"
export NEWS_API_KEY="your_newsapi_key"
export CURRENTS_API_KEY="your_currents_key"
python main.py
```

---

## ⚙️ GitHub Actions Workflow (`.github/workflows/deploy.yml`)

The automated pipeline triggers daily at 06:00 UTC (or manually via the Actions tab):

```yaml
name: Build and Deploy Current Affairs

on:
  schedule:
    - cron: '0 6 * * *'
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'

      - name: Install Dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt

      - name: Run Current Affairs Generator
        env:
          GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
          NEWS_API_KEY: ${{ secrets.NEWS_API_KEY }}
          CURRENTS_API_KEY: ${{ secrets.CURRENTS_API_KEY }}
        run: |
          python main.py

      - name: Upload Artifact for GitHub Pages
        uses: actions/upload-pages-artifact@v3
        with:
          path: 'public'

      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

---

## 📄 License
This project is open-source and intended for educational and competitive examination preparation.