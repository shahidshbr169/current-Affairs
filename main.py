import os
from datetime import datetime
import requests
import feedparser
from openai import OpenAI

# Configuration parameters
COUNTRY_CODE = "in"
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
CURRENTS_API_KEY = os.environ.get("CURRENTS_API_KEY", "")

# Dedicated RSS Sources split cleanly
RSS_SOURCES = {
    "National": [
        "https://www.thehindu.com/news/national/feeder/default.rss"
    ],
    "International": [
        "https://www.thehindu.com/news/international/feeder/default.rss",
        "http://feeds.bbci.co.uk/news/world/rss.xml"
    ]
}

def fetch_all_sources():
    national_items = []
    international_items = []

    print("==================================================")
    print("      FETCHING DATA FOR SPLIT API REQUESTS        ")
    print("==================================================")

    # 1. FETCH FROM NEWSAPI.ORG
    if NEWS_API_KEY and len(NEWS_API_KEY) > 5:
        try:
            newsapi_nat_url = f"https://newsapi.org/v2/top-headlines?country={COUNTRY_CODE}&pageSize=5&apiKey={NEWS_API_KEY}"
            res = requests.get(newsapi_nat_url, timeout=10)
            data = res.json()
            if res.status_code == 200 and data.get("status") == "ok":
                for article in data.get("articles", []):
                    if article.get('title') and article.get('title') != "[Removed]":
                        national_items.append(f"Title: {article.get('title')} | Link: {article.get('url')} | Details: {article.get('description') or ''}")

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
    if CURRENTS_API_KEY and len(CURRENTS_API_KEY) > 5:
        try:
            headers = {"Authorization": CURRENTS_API_KEY}
            cur_nat_url = f"https://api.currentsapi.services/v1/search?country={COUNTRY_CODE.upper()}&language=en&page_size=5"
            cur_res = requests.get(cur_nat_url, headers=headers, timeout=10)
            cur_data = cur_res.json()
            if cur_res.status_code == 200 and cur_data.get("status") == "ok":
                for article in cur_data.get("news", []):
                    if article.get('title'):
                        national_items.append(f"Title: {article.get('title')} | Link: {article.get('url')} | Details: {article.get('description') or ''}")

            cur_intl_url = "https://api.currentsapi.services/v1/latest-news?language=en&page_size=5"
            cur_intl_res = requests.get(cur_intl_url, headers=headers, timeout=10)
            cur_intl_data = cur_intl_res.json()
            if cur_intl_res.status_code == 200 and cur_intl_data.get("status") == "ok":
                for article in cur_intl_data.get("news", []):
                    if article.get('title'):
                        international_items.append(f"Title: {article.get('title')} | Link: {article.get('url')} | Details: {article.get('description') or ''}")
        except Exception as e:
            print(f"❌ [Currents API Exception]: {e}")

    # 3. FETCH FROM TRUSTED RSS FEEDS
    for category, urls in RSS_SOURCES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:8]:
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

    if not national_items:
        national_items.append("Title: Polity, Governance & National Policy Updates | Link: https://www.thehindu.com | Details: Core legislative developments and domestic administrative affairs.")
    if not international_items:
        international_items.append("Title: International Relations & Global Geopolitics | Link: https://www.bbc.com/news/world | Details: Transnational agreements, global economic shifts, and diplomatic summits.")

    return national_items, international_items

nat_news, intl_news = fetch_all_sources()

nat_raw_text = "\n".join(nat_news)
intl_raw_text = "\n".join(intl_news)

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

# ----------------------------------------------------
# REQUEST 1: NATIONAL NEWS & GOVERNANCE
# ----------------------------------------------------
print("Sending dedicated National News request to Groq...")
nat_prompt = f"""
You are an expert UPSC Civil Services faculty mentor. Review the following raw national news data carefully. 
Synthesize them into a thorough, rigorous current affairs section focused strictly on National News & Governance (Polity, Economy, Environment, Internal Security).

CRITICAL INSTRUCTIONS (NO HALLUCINATION):
1. For each entry, compose a comprehensive, analytical paragraph strictly between 70 to 120 words focusing on context and UPSC syllabus relevance based SOLELY on the provided inputs. Never invent unverified facts.
2. Output the result STRICTLY as a valid HTML unordered list (<ul><li>...</li></ul>) containing strong headlines and active source links (<a href="URL" target="_blank">Read full article</a>).
3. DO NOT include <h2> tags or markdown formatting.

Raw National Inputs:
{nat_raw_text}
"""

nat_response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a professional UPSC news editor outputting clean HTML list elements only."},
        {"role": "user", "content": nat_prompt}
    ],
    temperature=0.7
)
national_html_content = nat_response.choices[0].message.content.replace("```html", "").replace("```", "").strip()

# ----------------------------------------------------
# REQUEST 2: INTERNATIONAL RELATIONS & GLOBAL AFFAIRS
# ----------------------------------------------------
print("Sending dedicated International Relations request to Groq...")
intl_prompt = f"""
You are an expert UPSC Civil Services faculty mentor. Review the following raw international news data carefully. 
Synthesize them into a thorough, rigorous current affairs section focused strictly on International Relations & Global Affairs (Bilateral ties, Global Summits, Treaties, Geopolitics).

CRITICAL INSTRUCTIONS (NO HALLUCINATION):
1. For each entry, compose a comprehensive, analytical paragraph strictly between 70 to 120 words focusing on context and UPSC GS-2 relevance based SOLELY on the provided inputs. Never invent unverified facts.
2. Output the result STRICTLY as a valid HTML unordered list (<ul><li>...</li></ul>) containing strong headlines and active source links (<a href="URL" target="_blank">Read full article</a>).
3. DO NOT include <h2> tags or markdown formatting.

Raw International Inputs:
{intl_raw_text}
"""

intl_response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a professional UPSC news editor outputting clean HTML list elements only."},
        {"role": "user", "content": intl_prompt}
    ],
    temperature=0.7
)
international_html_content = intl_response.choices[0].message.content.replace("```html", "").replace("```", "").strip()

print("Successfully received both separate API responses from Groq.")

# Combine both results into the final layout structure
combined_ai_content = f"""
<div class="category-banner">🇮🇳 National News & Governance</div>
{national_html_content}

<div class="category-banner">🌍 International Relations & Global Affairs</div>
{international_html_content}
"""

# Setup Archive and Today's Dates
current_date_iso = datetime.now().strftime("%Y-%m-%d")
current_date_formatted = datetime.now().strftime("%B %d, %Y")

os.makedirs("public/archive", exist_ok=True)

# Generate Daily HTML Page with modern modern styling and highlight rules
daily_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UPSC Current Affairs - {current_date_formatted}</title>
    <style>
        :root {{
            --primary: #2563eb;
            --primary-light: #eff6ff;
            --secondary: #0f172a;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #334155;
            --border-color: #e2e8f0;
        }}
        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 950px;
            margin: 0 auto;
            padding: 20px;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.7;
        }}
        .header-bar {{
            background: linear-gradient(135deg, #1e293b, #0f172a);
            color: white;
            padding: 30px;
            border-radius: 12px;
            margin-bottom: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.08);
        }}
        .header-bar h1 {{
            margin: 0 0 10px 0;
            font-size: 2rem;
            letter-spacing: -0.5px;
        }}
        .meta-tag {{
            display: inline-block;
            background: rgba(255,255,255,0.15);
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.85rem;
            font-weight: 500;
        }}
        .back-link {{
            display: inline-block;
            margin-bottom: 20px;
            color: var(--primary);
            text-decoration: none;
            font-weight: 600;
            transition: color 0.2s;
        }}
        .back-link:hover {{
            color: #1d4ed8;
            text-decoration: underline;
        }}
        .card {{
            background: var(--card-bg);
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 4px 25px rgba(0,0,0,0.04);
            border: 1px solid var(--border-color);
        }}
        .category-banner {{
            background: var(--primary-light);
            color: var(--primary);
            font-size: 1.25rem;
            font-weight: 700;
            padding: 12px 20px;
            border-radius: 8px;
            margin-top: 40px;
            margin-bottom: 20px;
            border-left: 5px solid var(--primary);
        }}
        ul {{
            padding-left: 0;
            list-style: none;
        }}
        li {{
            background: #ffffff;
            border: 1px solid var(--border-color);
            padding: 24px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.01);
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        li:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(0,0,0,0.05);
            border-color: #cbd5e1;
        }}
        strong {{
            color: var(--secondary);
            font-size: 1.1rem;
            display: block;
            margin-bottom: 8px;
        }}
        a.source-link {{
            display: inline-block;
            margin-top: 12px;
            background: var(--primary-light);
            color: var(--primary);
            padding: 6px 14px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 600;
            transition: background 0.2s;
        }}
        a.source-link:hover {{
            background: #dbeafe;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="card">
        <a class="back-link" href="../index.html">← Back to UPSC Archive Index</a>
        
        <div class="header-bar">
            <h1>UPSC Daily Current Affairs Briefing</h1>
            <div class="meta-tag">📅 {current_date_formatted} &nbsp;|&nbsp; 🏛️ Civil Services Examination Prep</div>
        </div>

        <div class="news-content">
            {combined_ai_content}
        </div>
    </div>
</body>
</html>
"""

daily_filename = f"{current_date_iso}.html"
with open(f"public/archive/{daily_filename}", "w", encoding="utf-8") as f:
    f.write(daily_html)

# Generate Index Page with modern clean styles
archive_files = sorted([f for f in os.listdir("public/archive") if f.endswith(".html")], reverse=True)
links_html = ""
for file in archive_files:
    date_str = file.replace(".html", "")
    links_html += f'<li><a href="archive/{file}">📚 UPSC Briefing – <strong>{date_str}</strong> <span style="float:right; color:#64748b; font-size:0.9rem; font-weight:normal;">View Edition →</span></a></li>\n'

index_html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UPSC Civil Services - Current Affairs Portal</title>
    <style>
        :root {{
            --primary: #2563eb;
            --primary-light: #eff6ff;
            --secondary: #0f172a;
            --bg-color: #f8fafc;
            --card-bg: #ffffff;
            --text-main: #334155;
            --border-color: #e2e8f0;
        }}
        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            max-width: 900px;
            margin: 40px auto;
            padding: 0 20px;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.6;
        }}
        .container {{
            background: var(--card-bg);
            padding: 45px;
            border-radius: 12px;
            box-shadow: 0 4px 25px rgba(0,0,0,0.04);
            border: 1px solid var(--border-color);
        }}
        h1 {{
            color: var(--secondary);
            border-bottom: 3px solid var(--primary);
            padding-bottom: 12px;
            margin-top: 0;
        }}
        ul {{
            list-style-type: none;
            padding: 0;
        }}
        li {{
            margin: 15px 0;
            padding: 18px 20px;
            background: #ffffff;
            border: 1px solid var(--border-color);
            border-left: 5px solid var(--primary);
            border-radius: 8px;
            transition: all 0.2s ease;
        }}
        li:hover {{
            transform: translateY(-2px);
            box-shadow: 0 6px 15px rgba(0,0,0,0.05);
            border-color: #cbd5e1;
        }}
        a {{
            color: var(--primary);
            text-decoration: none;
            font-size: 1.05rem;
            font-weight: 600;
            display: block;
        }}
        a:hover {{
            text-decoration: underline;
        }}
        .subtitle {{
            color: #64748b;
            font-size: 1.05rem;
            margin-bottom: 30px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏛️ UPSC / IAS Current Affairs Portal</h1>
        <p class="subtitle">Structured multi-source intelligence engineered for rigorous civil services preparation.</p>
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
print("Modernized UPSC portal build script completed successfully.")
