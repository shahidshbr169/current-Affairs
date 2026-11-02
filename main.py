import os
from datetime import datetime
import requests
import feedparser
from openai import OpenAI

# Configuration parameters
COUNTRY_CODE = "in"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")       # From newsapi.org
CURRENTS_API_KEY = os.environ.get("CURRENTS_API_KEY", "") # From currentsapi.services

# Dedicated RSS Sources split cleanly into National/Governance and International/World
RSS_SOURCES = {
    "National": [
        "https://www.thehindu.com/news/national/feeder/default.rss" # The Hindu National Feed
    ],
    "International": [
        "https://www.thehindu.com/news/international/feeder/default.rss", # The Hindu International Feed
        "http://feeds.bbci.co.uk/news/world/rss.xml"                     # BBC World News
    ]
}

def fetch_all_sources():
    national_items = []
    international_items = []

    print("==================================================")
    print("      FETCHING BALANCED HYBRID DATA SOURCES       ")
    print("==================================================")

    # 1. FETCH FROM NEWSAPI.ORG
    if NEWS_API_KEY:
        try:
            # National Headlines
            newsapi_nat_url = f"https://newsapi.org/v2/top-headlines?country={COUNTRY_CODE}&pageSize=5&apiKey={NEWS_API_KEY}"
            res = requests.get(newsapi_nat_url, timeout=10)
            data = res.json()
            if res.status_code == 200 and data.get("status") == "ok":
                for article in data.get("articles", []):
                    if article.get('title') and article.get('title') != "[Removed]":
                        national_items.append(f"Title: {article.get('title')} | Link: {article.get('url')} | Details: {article.get('description') or ''}")

            # International Headlines
            newsapi_intl_url = f"https://newsapi.org/v2/top-headlines?category=general&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
            res_intl = requests.get(newsapi_intl_url, timeout=10)
            data_intl = res_intl.json()
            if res_intl.status_code == 200 and data_intl.get("status") == "ok":
                for article in data_intl.get("articles", []):
                    if article.get('title') and article.get('title') != "[Removed]":
                        international_items.append(f"Title: {article.get('title')} | Link: {article.get('url')} | Details: {article.get('description') or ''}")
        except Exception as e:
            print(f"❌ [NewsAPI Exception]: {e}")

    # 2. FETCH FROM CURRENTS API
    if CURRENTS_API_KEY:
        try:
            headers = {"Authorization": CURRENTS_API_KEY}
            
            # National Search
            cur_nat_url = f"https://api.currentsapi.services/v1/search?country={COUNTRY_CODE.upper()}&language=en&page_size=5"
            cur_res = requests.get(cur_nat_url, headers=headers, timeout=10)
            cur_data = cur_res.json()
            if cur_res.status_code == 200 and cur_data.get("status") == "ok":
                for article in cur_data.get("news", []):
                    if article.get('title'):
                        national_items.append(f"Title: {article.get('title')} | Link: {article.get('url')} | Details: {article.get('description') or ''}")

            # International News
            cur_intl_url = "https://api.currentsapi.services/v1/latest-news?language=en&page_size=5"
            cur_intl_res = requests.get(cur_intl_url, headers=headers, timeout=10)
            cur_intl_data = cur_intl_res.json()
            if cur_intl_res.status_code == 200 and cur_intl_data.get("status") == "ok":
                for article in cur_intl_data.get("news", []):
                    if article.get('title'):
                        international_items.append(f"Title: {article.get('title')} | Link: {article.get('url')} | Details: {article.get('description') or ''}")
        except Exception as e:
            print(f"❌ [Currents API Exception]: {e}")

    # 3. FETCH FROM TRUSTED RSS FEEDS (Cleanly Separated)
    print("\n[RSS Feeds] Fetching from structured RSS streams...")
    for category, urls in RSS_SOURCES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                print(f"-> Parsed {len(feed.entries)} entries for [{category}] from {url}")
                for entry in feed.entries[:8]: # Limit per RSS source to maintain balance
                    title = getattr(entry, 'title', 'No Title')
                    link = getattr(entry, 'link', '#')
                    summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    
                    item_text = f"Title: {title} | Link: {link} | Details: {summary}"
                    
                    if category == "National":
                        national_items.append(item_text)
                    else:
                        international_items.append(item_text)
            except Exception as e:
                print(f"❌ Error parsing RSS {url}: {e}")

    print("==================================================")
    print(f"Total Balanced National Items: {len(national_items)}")
    print(f"Total Balanced International Items: {len(international_items)}")
    print("==================================================")

    # Safe fallbacks if lists are empty
    if not national_items:
        national_items.append("Title: Polity, Governance & National Policy Updates | Link: https://www.thehindu.com | Details: Core legislative developments and domestic administrative affairs.")
    if not international_items:
        international_items.append("Title: International Relations & Global Geopolitics | Link: https://www.bbc.com/news/world | Details: Transnational agreements, global economic shifts, and diplomatic summits.")

    return national_items, international_items

nat_news, intl_news = fetch_all_sources()

raw_news_text = "### National News Inputs (UPSC GS-2 & GS-3 Focus):\n" + "\n".join(nat_news) + "\n\n### International News Inputs (UPSC IR Focus):\n" + "\n".join(intl_news)

# Configure Groq Client for openai/gpt-oss-120b
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

prompt = f"""
You are an expert UPSC Civil Services faculty mentor and senior current affairs analyst. Review the following multi-source raw news data carefully. 
Synthesize them into a rich, thorough, and highly structured daily current affairs briefing tailored for IAS aspirants.

CRITICAL INSTRUCTIONS (NO HALLUCINATION & STRICT SECTION BALANCING):
1. You MUST generate TWO distinct, fully populated main sections:
   - <h2>National News & Governance</h2> (Containing multiple detailed bullet points mapping to polity, economy, environment, and internal security).
   - <h2>International Relations & Global Affairs</h2> (Containing multiple detailed bullet points mapping to bilateral ties, global summits, and international organizations).
2. Do NOT omit either section. Both sections must be comprehensively populated.
3. For each entry, compose a rigorous, analytical paragraph strictly between 70 to 120 words focusing on context, structural significance, and UPSC syllabus relevance based SOLELY on the provided inputs. Never invent unverified facts.
4. Output the result STRICTLY as valid HTML elements (such as <h2>, <h3>, <ul>, <li>, <strong>, and <a href="URL" target="_blank"> tags). 
5. DO NOT use Markdown formatting, markdown tables, or code blocks.
6. Every list item MUST incorporate the actual source link provided in the input as an active hyperlink anchor text so aspirants can click through to read the full source article.

Raw Multi-Source Inputs:
{raw_news_text}
"""

print("Sending balanced prompt to Groq API (openai/gpt-oss-120b)...")
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a professional UPSC news editor who outputs clean HTML content only with balanced sections and zero hallucination."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.7
)

ai_content = response.choices[0].message.content
ai_content = ai_content.replace("```html", "").replace("```", "").strip()
print("Successfully generated balanced UPSC HTML briefing.")

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
    <title>UPSC Current Affairs - {current_date_formatted}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.7; color: #2c3e50; background: #f8f9fa; }}
        .card {{ background: #fff; padding: 45px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.06); border: 1px solid #e1e8ed; }}
        h1 {{ color: #1a252f; margin-top: 0; font-size: 2rem; border-bottom: 3px solid #3498db; padding-bottom: 12px; }}
        .back-link {{ display: inline-block; margin-bottom: 20px; color: #2980b9; text-decoration: none; font-weight: 600; }}
        .back-link:hover {{ text-decoration: underline; }}
        h2, h3 {{ color: #2c3e50; margin-top: 35px; border-bottom: 2px solid #eaeaea; padding-bottom: 8px; }}
        ul {{ padding-left: 20px; }}
        li {{ margin-bottom: 20px; text-align: justify; }}
        a {{ color: #2980b9; text-decoration: none; font-weight: 600; }}
        a:hover {{ text-decoration: underline; }}
        .meta-date {{ color: #7f8c8d; font-size: 0.95rem; margin-bottom: 25px; }}
    </style>
</head>
<body>
    <div class="card">
        <a class="back-link" href="../index.html">← Back to UPSC Archive Index</a>
        <h1>UPSC Daily Current Affairs Briefing</h1>
        <div class="meta-date"><strong>Date:</strong> {current_date_formatted} | Balanced Hybrid Synthesis (National & International Sections)</div>
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
    links_html += f'<li><a href="archive/{file}">📚 UPSC Balanced Briefing – <strong>{date_str}</strong></a></li>\n'

index_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UPSC Civil Services - Current Affairs Portal</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 0 20px; line-height: 1.6; color: #2c3e50; background: #f8f9fa; }}
        .container {{ background: #fff; padding: 45px; border-radius: 10px; box-shadow: 0 4px 15px rgba(0,0,0,0.06); border: 1px solid #e1e8ed; }}
        h1 {{ color: #1a252f; border-bottom: 3px solid #3498db; padding-bottom: 12px; }}
        ul {{ list-style-type: none; padding: 0; }}
        li {{ margin: 15px 0; padding: 15px; background: #ffffff; border: 1px solid #e1e8ed; border-left: 5px solid #3498db; border-radius: 6px; transition: transform 0.2s; }}
        li:hover {{ transform: translateY(-2px); box-shadow: 0 4px 10px rgba(0,0,0,0.04); }}
        a {{ color: #2980b9; text-decoration: none; font-size: 1.1rem; font-weight: 600; }}
        .subtitle {{ color: #7f8c8d; font-size: 1rem; margin-bottom: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏛️ UPSC / IAS Current Affairs Portal</h1>
        <p class="subtitle">Multi-source hybrid intelligence tuned for comprehensive National and International civil services exam preparation.</p>
        <h2>Comprehensive Archive Index</h2>
        <ul>
            {links_html}
        </ul>
    </div>
</body>
</html>
"""

with open("public/index.html", "w", encoding="utf-8") as f:
    f.write(index_html)
print("Balanced UPSC build script completed successfully.")
