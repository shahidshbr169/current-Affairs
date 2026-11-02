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

# Trusted Open RSS Feeds (PIB for authentic national policy, The Hindu for editorials)
RSS_SOURCES = {
    "National-Gov": [
        "https://pib.gov.in/RssMain.aspx?ModId=6&Lang=1&Regid=3" # Official Press Information Bureau (PIB)
    ],
    "Editorials-News": [
        "https://www.thehindu.com/news/national/feeder/default.rss" # The Hindu National Feed
    ]
}

def fetch_all_sources():
    national_items = []
    international_items = []

    print("==================================================")
    print("      FETCHING HYBRID DATA (APIs + RSS FEEDS)     ")
    print("==================================================")

    # 1. FETCH FROM NEWSAPI.ORG
    if NEWS_API_KEY:
        try:
            newsapi_nat_url = f"https://newsapi.org/v2/top-headlines?country={COUNTRY_CODE}&pageSize=8&apiKey={NEWS_API_KEY}"
            res = requests.get(newsapi_nat_url, timeout=10)
            data = res.json()
            if res.status_code == 200 and data.get("status") == "ok":
                articles = data.get("articles", [])
                print(f"[NewsAPI] Fetched {len(articles)} national articles.")
                for article in articles:
                    title = article.get('title')
                    url = article.get('url')
                    desc = article.get('description') or ""
                    if title and title != "[Removed]":
                        national_items.append(f"Title: {title} | Link: {url} | Details: {desc}")

            newsapi_intl_url = f"https://newsapi.org/v2/top-headlines?category=general&language=en&pageSize=8&apiKey={NEWS_API_KEY}"
            res_intl = requests.get(newsapi_intl_url, timeout=10)
            data_intl = res_intl.json()
            if res_intl.status_code == 200 and data_intl.get("status") == "ok":
                articles_intl = data_intl.get("articles", [])
                print(f"[NewsAPI] Fetched {len(articles_intl)} international articles.")
                for article in articles_intl:
                    title = article.get('title')
                    url = article.get('url')
                    desc = article.get('description') or ""
                    if title and title != "[Removed]":
                        international_items.append(f"Title: {title} | Link: {url} | Details: {desc}")
        except Exception as e:
            print(f"❌ [NewsAPI Exception]: {e}")

    # 2. FETCH FROM CURRENTS API
    if CURRENTS_API_KEY:
        try:
            headers = {"Authorization": CURRENTS_API_KEY}
            cur_nat_url = f"https://api.currentsapi.services/v1/search?country={COUNTRY_CODE.upper()}&language=en&page_size=8"
            cur_res = requests.get(cur_nat_url, headers=headers, timeout=10)
            cur_data = cur_res.json()
            if cur_res.status_code == 200 and cur_data.get("status") == "ok":
                cur_articles = cur_data.get("news", [])
                print(f"[Currents API] Fetched {len(cur_articles)} national articles.")
                for article in cur_articles:
                    title = article.get('title')
                    url = article.get('url')
                    desc = article.get('description') or ""
                    if title:
                        national_items.append(f"Title: {title} | Link: {url} | Details: {desc}")

            cur_intl_url = "https://api.currentsapi.services/v1/latest-news?language=en&page_size=8"
            cur_intl_res = requests.get(cur_intl_url, headers=headers, timeout=10)
            cur_intl_data = cur_intl_res.json()
            if cur_intl_res.status_code == 200 and cur_intl_data.get("status") == "ok":
                cur_intl_articles = cur_intl_data.get("news", [])
                print(f"[Currents API] Fetched {len(cur_intl_articles)} international articles.")
                for article in cur_intl_articles:
                    title = article.get('title')
                    url = article.get('url')
                    desc = article.get('description') or ""
                    if title:
                        international_items.append(f"Title: {title} | Link: {url} | Details: {desc}")
        except Exception as e:
            print(f"❌ [Currents API Exception]: {e}")

    # 3. FETCH FROM TRUSTED RSS FEEDS (PIB & The Hindu)
    print("\n[RSS Feeds] Fetching from official RSS streams...")
    for category, urls in RSS_SOURCES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                print(f"-> Parsed {len(feed.entries)} entries from {url}")
                for entry in feed.entries[:6]:
                    title = getattr(entry, 'title', 'No Title')
                    link = getattr(entry, 'link', '#')
                    summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    
                    item_text = f"Title: {title} | Link: {link} | Details: {summary}"
                    
                    if category == "National-Gov":
                        national_items.append(item_text)
                    else:
                        national_items.append(item_text) # Feeds into national/editorial pool
            except Exception as e:
                print(f"❌ Error parsing RSS {url}: {e}")

    print("==================================================")
    print(f"Total National/Editorial Pool Items: {len(national_items)}")
    print(f"Total International Pool Items: {len(international_items)}")
    print("==================================================")

    # Fallbacks if pools are empty
    if not national_items:
        national_items.append("Title: Polity, Governance & PIB Releases | Link: https://pib.gov.in | Details: Core government policy updates and administrative developments.")
    if not international_items:
        international_items.append("Title: International Relations & Global Affairs | Link: https://www.un.org | Details: Transnational updates and diplomatic events.")

    return national_items, international_items

nat_news, intl_news = fetch_all_sources()

raw_news_text = "### National News & Editorial Inputs (UPSC GS Focus):\n" + "\n".join(nat_news) + "\n\n### International News Inputs (UPSC IR Focus):\n" + "\n".join(intl_news)

# Configure Groq Client for openai/gpt-oss-120b
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

prompt = f"""
You are an expert UPSC Civil Services faculty mentor and senior current affairs analyst. Review the following multi-source raw news data carefully. 
Synthesize them into a rich, thorough, and highly structured daily current affairs briefing tailored for IAS aspirants.

CRITICAL INSTRUCTIONS (NO HALLUCINATION & HIGH UPSC DEPTH):
1. Systematically incorporate updates across both "National News & Governance" and "International Relations". Group or categorize them matching standard UPSC syllabus criteria (e.g., Polity, Economy, Environment, Sci-Tech, International Relations).
2. For each entry, compose a rigorous, analytical paragraph strictly between 70 to 120 words focusing on context, structural significance, and exam relevance based SOLELY on the provided inputs. Never invent unverified facts.
3. Output the result STRICTLY as valid HTML elements (such as <h2>, <h3>, <ul>, <li>, <strong>, and <a href="URL" target="_blank"> tags). 
4. DO NOT use Markdown formatting, markdown tables, or code blocks.
5. Every list item MUST incorporate the actual source link provided in the input as an active hyperlink anchor text so aspirants can click through to read the full source article.

Raw Multi-Source Inputs:
{raw_news_text}
"""

print("Sending multi-source prompt to Groq API (openai/gpt-oss-120b)...")
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a professional UPSC news editor who outputs clean HTML content only with zero hallucination."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.7
)

ai_content = response.choices[0].message.content
ai_content = ai_content.replace("```html", "").replace("```", "").strip()
print("Successfully generated high-grade UPSC HTML briefing.")

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
        <div class="meta-date"><strong>Date:</strong> {current_date_formatted} | Hybrid Feed Synthesis (APIs + PIB & Editorials)</div>
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
    links_html += f'<li><a href="archive/{file}">📚 UPSC Hybrid Briefing – <strong>{date_str}</strong></a></li>\n'

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
        <p class="subtitle">Multi-source hybrid intelligence (NewsAPI + Currents API + PIB + Editorials) tuned for civil services exam preparation.</p>
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
print("Hybrid UPSC build script completed successfully.")
