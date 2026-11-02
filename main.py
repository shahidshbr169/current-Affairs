import os
from datetime import datetime
import requests
from openai import OpenAI

# Configuration (Change 'in' to your preferred country code if needed, e.g., 'us', 'gb', etc.)
COUNTRY_CODE = "in" 
GROQ_API_KEY = os.environ["GROQ_API_KEY"]
# Optional: If using a free news provider like mediastack or similar API key, store it in GitHub Secrets as NEWS_API_KEY
# For zero-key backup, we can also use public API endpoints or fallback to multi-region RSS.
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")

def fetch_structured_news():
    national_items = []
    international_items = []

    # If you sign up for a free key on mediastack.com or similar, this pulls real-time JSON safely:
    if NEWS_API_KEY:
        try:
            # Fetch National News for specific country
            nat_url = f"http://api.mediastack.com/v1/news?access_key={NEWS_API_KEY}&countries={COUNTRY_CODE}&limit=5"
            nat_res = requests.get(nat_url).json()
            for article in nat_res.get("data", []):
                national_items.append(f"- Title: {article.get('title')} | Link: {article.get('url')} | Description: {article.get('description')}")

            # Fetch International News
            intl_url = f"http://api.mediastack.com/v1/news?access_key={NEWS_API_KEY}&sources=bbc,cnn,reuters&limit=5"
            intl_res = requests.get(intl_url).json()
            for article in intl_res.get("data", []):
                international_items.append(f"- Title: {article.get('title')} | Link: {article.get('url')} | Description: {article.get('description')}")
        except Exception as e:
            print(f"API Fetch error: {e}")

    # Fallback/Robust Direct Public JSON endpoints if no separate news key is provided
    if not national_items or not international_items:
        print("Using reliable public fallback endpoints...")
        try:
            # Using HackerNews / Reddit public JSON or stable public feeds as reliable backup
            hn_res = requests.get("https://hacker-news.firebaseio.com/v0/topstories.json").json()[:10]
            for story_id in hn_res:
                item = requests.get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json").json()
                if item and 'title' in item:
                    international_items.append(f"- Title: {item.get('title')} | Link: {item.get('url', '#')} | Description: Tech / Global update")
        except Exception as e:
            print(f"Fallback error: {e}")

        # Add mock/placeholder safety fallback if empty so fields never collapse
        if not national_items:
            national_items.append(f"- Title: National Government Policy & Economic Updates | Link: # | Description: Routine administrative developments, legislative updates, and domestic market overviews tracked for {COUNTRY_CODE.upper()}.")

    return national_items, international_items

nat_news, intl_news = fetch_structured_news()

raw_news_text = "### National News Items:\n" + "\n".join(nat_news) + "\n\n### International News Items:\n" + "\n".join(intl_news)

# 2. Configure Groq Client for openai/gpt-oss-120b
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

prompt = f"""
You are an expert news editor. Review the following raw news data carefully. 
Synthesize them into a clean, comprehensive daily current affairs briefing. 

CRITICAL INSTRUCTIONS:
1. You MUST populate both "International News" and "National News" sections thoroughly. Do not leave any section empty.
2. Output the result STRICTLY as valid HTML elements (such as <h2>, <ul>, <li>, <strong>, and <a> tags). 
3. DO NOT use Markdown tables, markdown code blocks, or raw markdown syntax. 
4. Every news item must have a clear headline, a brief context summary, and an active hyperlink back to its source URL if available.

Raw Data:
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

# 3. Setup Archive and Today's Dates
current_date_iso = datetime.now().strftime("%Y-%m-%d")
current_date_formatted = datetime.now().strftime("%B %d, %Y")

os.makedirs("public/archive", exist_ok=True)

# 4. Generate Daily HTML Page
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

# 5. Generate Index Page
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
        <p class="subtitle">Automated daily briefings covering National and International updates, powered by Groq & OpenAI open weights.</p>
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
