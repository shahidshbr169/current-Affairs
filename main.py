import os
from datetime import datetime
import feedparser
from openai import OpenAI

# 1. Broadened Free RSS Sources for Reliable National & International News
RSS_SOURCES = {
    "International": [
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.nytimes.com/services/xml/rss/nyt/World.xml"
    ],
    "National": [
        "http://feeds.bbci.co.uk/news/rss.xml", # General/National home feed fallback
        "https://rss.nytimes.com/services/xml/rss/nyt/US.xml" # Use US or change to your target region (e.g., India/UK feed)
    ]
}

aggregated_news = []
for category, urls in RSS_SOURCES.items():
    aggregated_news.append(f"SECTION: {category}")
    for url in urls:
        try:
            feed = feedparser.parse(url)
            # Take up to 6 items per feed to ensure rich options
            for entry in feed.entries[:6]:
                title = getattr(entry, 'title', 'No Title')
                link = getattr(entry, 'link', '#')
                # Fallback to description if summary is missing
                summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')
                aggregated_news.append(f"- Title: {title} | Link: {link} | Summary: {summary}")
        except Exception as e:
            print(f"Error parsing {url}: {e}")

raw_news_text = "\n".join(aggregated_news)

# 2. Configure Groq Client for openai/gpt-oss-120b
client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=os.environ["GROQ_API_KEY"],
)

prompt = f"""
You are an expert news editor. Review the following raw news feeds carefully. 
Synthesize them into a clean, comprehensive daily current affairs briefing. 

CRITICAL INSTRUCTIONS:
1. You MUST populate both "International News" and "National News" sections. Do not leave any section empty. If an item fits national or regional affairs, place it under National News.
2. Output the result STRICTLY as valid HTML elements (such as <h2>, <ul>, <li>, <strong>, and <a> tags). 
3. DO NOT use Markdown tables, markdown code blocks, or raw markdown syntax. 
4. Every news item must have a clear headline, a brief context summary, and an active hyperlink back to its source URL.

Raw News Feeds:
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

# Clean up any accidental markdown code-block wrappers if the model outputs them
ai_content = ai_content.replace("```html", "").replace("```", "").strip()

# 3. Setup Archive and Today's Dates
current_date_iso = datetime.now().strftime("%Y-%m-%d")
current_date_formatted = datetime.now().strftime("%B %d, %Y")

os.makedirs("public/archive", exist_ok=True)

# 4. Generate the Daily Page HTML
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

# 5. Generate the Main Index / Archive Page Listing All Past Days
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
