import os
from datetime import datetime
import requests
from openai import OpenAI

# Configuration
COUNTRY_CODE = "in"  # Change to your target country (e.g., 'us', 'gb', 'in')
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")       # From newsapi.org
CURRENTS_API_KEY = os.environ.get("CURRENTS_API_KEY", "") # From currentsapi.services

def fetch_all_news():
    national_items = []
    international_items = []

    # 1. Fetch from NewsAPI.org (Great for general/international top headlines)
    if NEWS_API_KEY:
        try:
            # National top headlines for country
            newsapi_nat_url = f"https://newsapi.org/v2/top-headlines?country={COUNTRY_CODE}&apiKey={NEWS_API_KEY}"
            res = requests.get(newsapi_nat_url).json()
            if res.get("status") == "ok":
                for article in res.get("articles", [])[:5]:
                    if article.get('title') and article.get('title') != "[Removed]":
                        national_items.append(
                            f"- Title: {article.get('title')} | Link: {article.get('url')} | Summary: {article.get('description') or ''}"
                        )

            # International top headlines (General world or US/Global sources)
            newsapi_intl_url = f"https://newsapi.org/v2/top-headlines?category=general&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
            res_intl = requests.get(newsapi_intl_url).json()
            if res_intl.get("status") == "ok":
                for article in res_intl.get("articles", [])[:5]:
                    if article.get('title') and article.get('title') != "[Removed]":
                        international_items.append(
                            f"- Title: {article.get('title')} | Link: {article.get('url')} | Summary: {article.get('description') or ''}"
                        )
        except Exception as e:
            print(f"NewsAPI fetch error: {e}")

    # 2. Fetch from Currents API (Great for deep keyword search and regional coverage)
    if CURRENTS_API_KEY:
        try:
            headers = {"Authorization": CURRENTS_API_KEY}
            
            # National search filter
            cur_nat_url = f"https://api.currentsapi.services/v1/search?country={COUNTRY_CODE}&language=en&page_size=5"
            cur_nat_res = requests.get(cur_nat_url, headers=headers).json()
            for article in cur_nat_res.get("news", []):
                national_items.append(
                    f"- Title: {article.get('title')} | Link: {article.get('url')} | Summary: {article.get('description') or ''}"
                )

            # International search filter
            cur_intl_url = "https://api.currentsapi.services/v1/latest-news?language=en&page_size=5"
            cur_intl_res = requests.get(cur_intl_url, headers=headers).json()
            for article in cur_intl_res.get("news", []):
                international_items.append(
                    f"- Title: {article.get('title')} | Link: {article.get('url')} | Summary: {article.get('description') or ''}"
                )
        except Exception as e:
            print(f"Currents API fetch error: {e}")

    # Safety Fallbacks if keys are missing or limits are reached
    if not national_items:
        national_items.append(f"- Title: Domestic Administrative & Legislative Update | Link: # | Summary: Ongoing national developments, economic shifts, and policy updates in {COUNTRY_CODE.upper()}.")
    if not international_items:
        international_items.append("- Title: Global Diplomatic & Trade Overview | Link: # | Summary: International geopolitical reports and cross-border commercial updates.")

    return national_items, international_items

nat_news, intl_news = fetch_all_news()

raw_news_text = "### National News Data:\n" + "\n".join(nat_news) + "\n\n### International News Data:\n" + "\n".join(intl_news)

# Configure Groq Client for openai/gpt-oss-120b
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

prompt = f"""
You are an elite executive news editor. Review the following raw multi-source news data carefully. 
Synthesize them into a clean, comprehensive, highly professional daily current affairs briefing. 

CRITICAL INSTRUCTIONS:
1. You MUST thoroughly populate both "International News" and "National News" sections. Do not leave any section empty.
2. Output the result STRICTLY as valid HTML elements (such as <h2>, <ul>, <li>, <strong>, and <a> tags). 
3. DO NOT use Markdown tables, markdown code blocks, or raw markdown syntax. 
4. Every news item must have a clear headline, an insightful executive summary, and an active hyperlink pointing back to its source URL.

Raw Multi-Source Data:
{raw_news_text}
"""

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a professional news editor who outputs clean HTML content only with no empty sections."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.7
)

ai_content = response.choices[0].message.content
ai_content = ai_content.replace("```html", "").replace("```", "").strip()

# Setup Archive and Today's Dates
current_date_iso = datetime.now().strftime("%Y-%m-%d")
current_date_formatted = datetime.now().strftime("%B %d, %Y")

os.makedirs("public/archive", exist_ok=True)

# Generate Daily HTML Page
daily_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Current Affairs - {current_date_formatted}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 850px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #333; background: #fdfdfd; }}
        .card {{ background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); border: 1px solid #eaeaea; }}
        h1 {{ color: #1a1a1a; margin-top: 0; }}
        .back-link {{ display: inline-block; margin-bottom: 20px; color: #0066cc; text-decoration: none; }}
        .back-link:hover {{ text-decoration: underline; }}
        h2, h3 {{ color: #222; border-bottom: 2px solid #f0f0f0; padding-bottom: 6px; margin-top: 30px; }}
        ul {{ padding-left: 20px; }}
        li {{ margin-bottom: 12px; }}
        a {{ color: #0066cc; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
    </style>
</head>
<body>
    <div class="card">
        <a class="back-link" href="../index.html">← Back to All Archives</a>
        <h1>Daily Current Affairs Briefing</h1>
        <p><strong>Date:</strong> {current_date_formatted}</p>
        <hr style="border:0; border-top:1px solid #eee; margin: 20px 0;">
        <div class="news-content">
            {ai_content}
        </div>
    </div>
</body>
</html>
"""

daily_filename = f"{current_date_iso}.html"
with open(f"public/archive/{daily_filename}", "w", encoding="utf-8") as f:
    f.write(daily_html)

# Generate Index Page
archive_files = sorted([f for f in os.listdir("public/archive") if f.endswith(".html")], reverse=True)
links_html = ""
for file in archive_files:
    date_str = file.replace(".html", "")
    links_html += f'<li><a href="archive/{file}">📅 Current Affairs Briefing – <strong>{date_str}</strong></a></li>\n'

index_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Current Affairs Archive - National & International</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 850px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #333; background: #f9f9f9; }}
        .container {{ background: #fff; padding: 40px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.05); }}
        h1 {{ color: #1a1a1a; }}
        ul {{ list-style-type: none; padding: 0; }}
        li {{ margin: 12px 0; padding: 12px; background: #fcfcfc; border: 1px solid #eee; border-radius: 6px; transition: background 0.2s; }}
        li:hover {{ background: #f1f7ff; }}
        a {{ color: #0066cc; text-decoration: none; font-size: 1.05rem; }}
        .subtitle {{ color: #666; font-size: 0.95rem; margin-bottom: 20px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🌍 Daily Current Affairs Portal</h1>
        <p class="subtitle">Automated daily briefings covering National and International updates, powered by NewsAPI, Currents, Groq & OpenAI open weights.</p>
        <h2>Archive Index</h2>
        <ul>
            {links_html}
        </ul>
    </div>
</body>
</html>
"""

with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(index_html)
