import os
from datetime import datetime
import requests
from openai import OpenAI

# Configuration parameters
COUNTRY_CODE = "in"  # Change to your target country code if needed (e.g., 'us', 'gb')
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")       # From newsapi.org
CURRENTS_API_KEY = os.environ.get("CURRENTS_API_KEY", "") # From currentsapi.services

def fetch_from_both_apis():
    national_items = []
    international_items = []

    print("==================================================")
    print("           STARTING MULTI-API DEBUG LOGS          ")
    print("==================================================")

    # Check key configuration status (masking keys for security)
    print(f"-> GROQ_API_KEY provided? {bool(GROQ_API_KEY)}")
    print(f"-> NEWS_API_KEY provided? {bool(NEWS_API_KEY)}")
    print(f"-> CURRENTS_API_KEY provided? {bool(CURRENTS_API_KEY)}")

    # ----------------------------------------------------
    # 1. FETCH FROM NEWSAPI.ORG
    # ----------------------------------------------------
    if NEWS_API_KEY:
        try:
            # National Top Headlines
            newsapi_nat_url = f"https://newsapi.org/v2/top-headlines?country={COUNTRY_CODE}&apiKey={NEWS_API_KEY}"
            print(f"\n[NewsAPI] Fetching National headlines for country: {COUNTRY_CODE}...")
            res = requests.get(newsapi_nat_url, timeout=10)
            print(f"[NewsAPI] National Response Status Code: {res.status_code}")
            
            data = res.json()
            if res.status_code == 200 and data.get("status") == "ok":
                articles = data.get("articles", [])
                print(f"[NewsAPI] Successfully fetched {len(articles)} national articles.")
                for article in articles[:4]:
                    title = article.get('title')
                    url = article.get('url')
                    desc = article.get('description') or "No description available."
                    if title and title != "[Removed]":
                        national_items.append(f"Title: {title} | Link: {url} | Description: {desc}")
            else:
                print(f"[NewsAPI] National Error Message: {data.get('message', 'Unknown error')}")

            # International Top Headlines (General Category)
            newsapi_intl_url = f"https://newsapi.org/v2/top-headlines?category=general&language=en&pageSize=4&apiKey={NEWS_API_KEY}"
            print(f"\n[NewsAPI] Fetching International general headlines...")
            res_intl = requests.get(newsapi_intl_url, timeout=10)
            print(f"[NewsAPI] International Response Status Code: {res_intl.status_code}")
            
            data_intl = res_intl.json()
            if res_intl.status_code == 200 and data_intl.get("status") == "ok":
                articles_intl = data_intl.get("articles", [])
                print(f"[NewsAPI] Successfully fetched {len(articles_intl)} international articles.")
                for article in articles_intl[:4]:
                    title = article.get('title')
                    url = article.get('url')
                    desc = article.get('description') or "No description available."
                    if title and title != "[Removed]":
                        international_items.append(f"Title: {title} | Link: {url} | Description: {desc}")
            else:
                print(f"[NewsAPI] International Error Message: {data_intl.get('message', 'Unknown error')}")

        except Exception as e:
            print(f"❌ [NewsAPI Exception]: {e}")
    else:
        print("⚠️ [NewsAPI] Skipped because NEWS_API_KEY secret is missing.")

    # ----------------------------------------------------
    # 2. FETCH FROM CURRENTS API
    # ----------------------------------------------------
    if CURRENTS_API_KEY:
        try:
            headers = {"Authorization": CURRENTS_API_KEY}
            
            # National Search Filter
            cur_nat_url = f"https://api.currentsapi.services/v1/search?country={COUNTRY_CODE.upper()}&language=en&page_size=4"
            print(f"\n[Currents API] Fetching National search items for country: {COUNTRY_CODE.upper()}...")
            cur_res = requests.get(cur_nat_url, headers=headers, timeout=10)
            print(f"[Currents API] National Response Status Code: {cur_res.status_code}")
            
            cur_data = cur_res.json()
            if cur_res.status_code == 200 and cur_data.get("status") == "ok":
                cur_articles = cur_data.get("news", [])
                print(f"[Currents API] Successfully fetched {len(cur_articles)} national articles.")
                for article in cur_articles:
                    title = article.get('title')
                    url = article.get('url')
                    desc = article.get('description') or "No description available."
                    if title:
                        national_items.append(f"Title: {title} | Link: {url} | Description: {desc}")
            else:
                print(f"[Currents API] National Error Data: {cur_data}")

            # International Latest News Filter
            cur_intl_url = "https://api.currentsapi.services/v1/latest-news?language=en&page_size=4"
            print(f"\n[Currents API] Fetching International latest news...")
            cur_intl_res = requests.get(cur_intl_url, headers=headers, timeout=10)
            print(f"[Currents API] International Response Status Code: {cur_intl_res.status_code}")
            
            cur_intl_data = cur_intl_res.json()
            if cur_intl_res.status_code == 200 and cur_intl_data.get("status") == "ok":
                cur_intl_articles = cur_intl_data.get("news", [])
                print(f"[Currents API] Successfully fetched {len(cur_intl_articles)} international articles.")
                for article in cur_intl_articles:
                    title = article.get('title')
                    url = article.get('url')
                    desc = article.get('description') or "No description available."
                    if title:
                        international_items.append(f"Title: {title} | Link: {url} | Description: {desc}")
            else:
                print(f"[Currents API] International Error Data: {cur_intl_data}")

        except Exception as e:
            print(f"❌ [Currents API Exception]: {e}")
    else:
        print("⚠️ [Currents API] Skipped because CURRENTS_API_KEY secret is missing.")

    print("==================================================")
    print(f"Total Combined National Items: {len(national_items)}")
    print(f"Total Combined International Items: {len(international_items)}")
    print("==================================================")

    # Safe fallbacks if keys are unconfigured or APIs return nothing
    if not national_items:
        national_items.append("Title: Domestic Policy & Legislative Updates | Link: https://news.google.com | Description: Comprehensive overview of administrative shifts, national developments, and legislative frameworks.")
    if not international_items:
        international_items.append("Title: Global Trade & Diplomatic Reports | Link: https://www.reuters.com | Description: Worldwide geopolitical updates, economic conditions, and cross-border cooperation summaries.")

    return national_items, international_items

# Execute data fetching
nat_news, intl_news = fetch_from_both_apis()

raw_news_text = "### National News Inputs:\n" + "\n".join(nat_news) + "\n\n### International News Inputs:\n" + "\n".join(intl_news)

# Configure Groq Client for openai/gpt-oss-120b
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

prompt = f"""
You are an elite executive news editor. Review the following raw multi-source news data carefully. 
Synthesize them into a professional daily current affairs briefing. 

CRITICAL INSTRUCTIONS (NO HALLUCINATION):
1. Thoroughly populate both "National News" and "International News" sections using ONLY the facts provided in the raw inputs. Do not invent or extrapolate details.
2. For each news entry, write a comprehensive paragraph containing strictly between 50 to 100 words based directly on the provided description.
3. Output the result STRICTLY as valid HTML elements (such as <h2>, <ul>, <li>, <strong>, and <a href="URL" target="_blank"> tags). 
4. DO NOT use Markdown formatting, markdown tables, or code blocks.
5. Every list item MUST incorporate the actual source link provided in the input as an active hyperlink anchor text (e.g., wrap the headline or add a direct clickable link) so users can easily click "Read more" or click the headline itself.

Raw News Inputs:
{raw_news_text}
"""

print("Sending prompt to Groq API (openai/gpt-oss-120b)...")
response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a professional news editor who outputs clean HTML content only with strict adherence to truth and no hallucinated facts."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.7
)

ai_content = response.choices[0].message.content
ai_content = ai_content.replace("```html", "").replace("```", "").strip()
print("Successfully generated HTML content from LLM.")

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
        li {{ margin-bottom: 18px; }}
        a {{ color: #0066cc; text-decoration: none; font-weight: 500; }}
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
print("Build script completed successfully and index generated.")
