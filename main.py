import os
from datetime import datetime
import feedparser
from openai import OpenAI

# 1. Zero-Limit Reliable RSS Feeds (Guarantees entries populate even without paid API keys)
RSS_SOURCES = {
    "National": [
        "http://feeds.bbci.co.uk/news/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/US.xml"
    ],
    "International": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    ]
}

def fetch_rss_news():
    national_items = []
    international_items = []

    for category, urls in RSS_SOURCES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:4]: # Grab top entries per feed
                    title = getattr(entry, 'title', 'No Title')
                    link = getattr(entry, 'link', '#')
                    summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                    
                    item_text = f"Title: {title} | Source Link: {link} | Details: {summary}"
                    
                    if category == "National":
                        national_items.append(item_text)
                    else:
                        international_items.append(item_text)
            except Exception as e:
                print(f"Error parsing {url}: {e}")

    return national_items, international_items

nat_news, intl_news = fetch_rss_news()

raw_news_text = "### National News Inputs:\n" + "\n".join(nat_news) + "\n\n### International News Inputs:\n" + "\n".join(intl_news)

# 2. Configure Groq Client for openai/gpt-oss-120b
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

prompt = f"""
You are an elite executive news editor. Review the following raw news inputs carefully. 
Synthesize them into a professional daily current affairs briefing. 

CRITICAL INSTRUCTIONS (NO HALLUCINATION):
1. Populate both "National News" and "International News" sections thoroughly using ONLY the facts provided in the raw inputs. Do not invent details.
2. For each news entry, write a comprehensive paragraph containing strictly between 50 to 100 words.
3. Output the result STRICTLY as valid HTML elements (such as <h2>, <ul>, <li>, <strong>, and <a href="URL"> tags). 
4. DO NOT use Markdown formatting, markdown tables, or code blocks.
5. Every list item MUST incorporate the actual source link provided in the input as an active hyperlink anchor text (e.g., wrap the headline or add a direct <a href="LINK">Read full article</a> link) so it is fully clickable.

Raw News Inputs:
{raw_news_text}
"""

response = client.chat.completions.create(
    model="openai/gpt-oss-120b",
    messages=[
        {"role": "system", "content": "You are a professional news editor who outputs clean HTML content only with no hallucinated facts."},
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
