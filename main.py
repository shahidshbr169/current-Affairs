import os
import re
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

# ---------------------------------------------------------------------------
# PROMPTS
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """
# Role and Objective
You are an expert Chief Editor and UPSC Civil Services Examination (CSE) Content Architect. You transform raw news items (The Hindu, BBC, and API feeds) into rigorous, high-yield, exam-oriented Current Affairs content for aspirants of the UPSC CSE and other premier Indian exams (State PSCs, RBI Grade B, Bank PO).

# Operational Directives
1. National News & Governance Pillar:
   - Focus strictly on policy implications, constitutional articles, Supreme Court judgments, statutory bodies, government schemes, socio-economic reports, and administrative reforms.
   - Strip away political rhetoric; focus solely on governance, federal structure, and policy outcomes.
2. International Relations & Global Affairs Pillar:
   - Focus on bilateral/multilateral groupings (Quad, BRICS, UN, G20), treaties, geopolitical shifts, India's strategic diaspora, and economic diplomacy.
   - Analyze events through the lens of India's strategic autonomy and national interest.
3. Deep-Dive Generation:
   - Explicitly map the item to specific UPSC Syllabus components (e.g., GS Paper II: Statutory, regulatory and various quasi-judicial bodies).
   - Provide "Prelims Pointers" (facts, data, articles) and "Mains Perspectives" (pros, cons, way forward).
4. Visual Concentration & Data Highlighting:
   - Wrap critical quantitative metrics, percentages, timelines, constitutional articles, and statutory figures in <span class="badge">...</span>.

# Accuracy Guardrail
- Facts about THIS event must come only from the provided title/details. Never invent figures, quotes, names, or dates.
- Background, constitutional provisions, committees (ARC, Sarkaria, etc.), and way-forward points may use well-established general knowledge, but only when you are confident and they are directly relevant.
- If the provided details are too thin for a field, write a brief, general, clearly non-event-specific statement rather than fabricating.
- Output clean HTML only. No markdown, no code fences.
"""

NATIONAL_SCHEMA = """
Output STRICTLY this HTML structure:
<div class="explanation-body">
    <p><strong>Core Summary:</strong> 2-3 concise sentences on what happened and why it matters.</p>
    <p><strong>UPSC Syllabus Mapping:</strong> e.g., GS Paper II - Governance, Constitution, Polity</p>
    <p><strong>Key Data &amp; Stats:</strong> <span class="badge">statistic / percentage / date / article</span> (add more badges if available)</p>
    <h4>Deep-Dive Analysis</h4>
    <ul>
        <li><em>Background:</em> context leading to this news</li>
        <li><em>Significance:</em> why it matters for administration/society</li>
        <li><em>Challenges / Critical Analysis:</em> bottlenecks, legal/ethical issues</li>
        <li><em>Way Forward:</em> expert recommendations / committee suggestions (ARC, Sarkaria, etc.)</li>
    </ul>
    <h4>Prelims Pointers</h4>
    <ul><li>2-4 factual pointers (terms, articles, bodies, data)</li></ul>
</div>
"""

INTERNATIONAL_SCHEMA = """
Output STRICTLY this HTML structure:
<div class="explanation-body">
    <p><strong>Core Summary:</strong> 2-3 concise sentences on the international event.</p>
    <p><strong>UPSC Syllabus Mapping:</strong> e.g., GS Paper II - Bilateral, regional and global groupings involving India</p>
    <p><strong>Key Data &amp; Agreements:</strong> <span class="badge">treaty / timeline / economic figure</span></p>
    <h4>Deep-Dive Analysis</h4>
    <ul>
        <li><em>Context &amp; Geopolitical Impact:</em> strategic implications for the global order</li>
        <li><em>Impact on India:</em> direct/indirect strategic, economic, or security consequences</li>
        <li><em>Way Forward:</em> policy options for India</li>
    </ul>
    <h4>Prelims Pointers</h4>
    <ul><li>2-4 factual pointers (groupings, treaties, locations, data)</li></ul>
</div>
"""

PILLAR_SCHEMAS = {"National": NATIONAL_SCHEMA, "International": INTERNATIONAL_SCHEMA}


def fetch_all_sources():
    national_items = []
    international_items = []

    print("==================================================")
    print("      FETCHING DATA FOR ADVANCED UPSC PORTAL      ")
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
                        national_items.append({
                            "title": article.get('title'),
                            "url": article.get('url'),
                            "desc": article.get('description') or ''
                        })

            newsapi_intl_url = f"https://newsapi.org/v2/top-headlines?category=general&language=en&pageSize=5&apiKey={NEWS_API_KEY}"
            res_intl = requests.get(newsapi_intl_url, timeout=10)
            data_intl = res_intl.json()
            if res_intl.status_code == 200 and data_intl.get("status") == "ok":
                for article in data_intl.get("articles", []):
                    if article.get('title') and article.get('title') != "[Removed]":
                        international_items.append({
                            "title": article.get('title'),
                            "url": article.get('url'),
                            "desc": article.get('description') or ''
                        })
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
                        national_items.append({
                            "title": article.get('title'),
                            "url": article.get('url'),
                            "desc": article.get('description') or ''
                        })

            cur_intl_url = "https://api.currentsapi.services/v1/latest-news?language=en&page_size=5"
            cur_intl_res = requests.get(cur_intl_url, headers=headers, timeout=10)
            cur_intl_data = cur_intl_res.json()
            if cur_intl_res.status_code == 200 and cur_intl_data.get("status") == "ok":
                for article in cur_intl_data.get("news", []):
                    if article.get('title'):
                        international_items.append({
                            "title": article.get('title'),
                            "url": article.get('url'),
                            "desc": article.get('description') or ''
                        })
        except Exception as e:
            print(f"❌ [Currents API Exception]: {e}")

    # 3. FETCH FROM TRUSTED RSS FEEDS
    for category, urls in RSS_SOURCES.items():
        for url in urls:
            try:
                feed = feedparser.parse(url)
                for entry in feed.entries[:6]:
                    title = getattr(entry, 'title', 'No Title')
                    link = getattr(entry, 'link', '#')
                    summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')

                    item_obj = {"title": title, "url": link, "desc": summary}
                    if category == "National":
                        national_items.append(item_obj)
                    else:
                        international_items.append(item_obj)
            except Exception as e:
                print(f"❌ Error parsing RSS {url}: {e}")

    if not national_items:
        national_items.append({"title": "Polity, Governance & National Policy Updates", "url": "https://www.thehindu.com", "desc": "Core legislative developments and domestic administrative affairs."})
    if not international_items:
        international_items.append({"title": "International Relations & Global Geopolitics", "url": "https://www.bbc.com/news/world", "desc": "Transnational agreements, global economic shifts, and diplomatic summits."})

    return national_items[:5], international_items[:5]  # Capped at 5 each for optimal generation speed


nat_news, intl_news = fetch_all_sources()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

# Dates first, then numbers/statistics (one pass so matches never overlap)
BADGE_PATTERN = re.compile(
    r'\b(20\d{2}|January|February|March|April|May|June|July|August|September|October|November|December)\b'
    r'|\b(\d+(?:\.\d+)?(?:%|rd|th|st|nd| crore| lakh| billion| million)?)\b'
)


def colorize_text(text):
    """Wrap dates/numbers in badges, leaving HTML tags and existing .badge spans untouched."""
    parts = re.split(r'(<[^>]+>)', text)
    out, in_badge = [], 0
    for part in parts:
        if part.startswith('<') and part.endswith('>'):
            if re.match(r'<span[^>]*class="badge"', part):
                in_badge += 1
            elif part == '</span>' and in_badge:
                in_badge -= 1
            out.append(part)
        elif in_badge:
            out.append(part)
        else:
            out.append(BADGE_PATTERN.sub(
                lambda m: f'<span class="badge-date">{m.group(1)}</span>' if m.group(1)
                else f'<span class="badge-num">{m.group(2)}</span>', part))
    return "".join(out)


def process_items_with_deep_dives(items, category_name, date_iso_str):
    html_cards = ""

    os.makedirs(f"public/archive/{date_iso_str}", exist_ok=True)

    for idx, item in enumerate(items):
        safe_title = item['title']
        safe_url = item['url']
        safe_desc = item['desc']

        print(f"Generating full-fledged explanation for [{category_name}] item {idx+1}: {safe_title[:40]}...")

        prompt = f"""
Process the following raw news item for the {category_name} pillar.

News Title: {safe_title}
News Details: {safe_desc}

{PILLAR_SCHEMAS[category_name]}
"""

        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # lower = fewer invented facts
            )
            explanation_html = response.choices[0].message.content.replace("```html", "").replace("```", "").strip()
        except Exception as e:
            print(f"Error calling Groq for deep dive: {e}")
            explanation_html = f"<div class='explanation-body'><p>{safe_desc}</p></div>"

        # Colorize summary and explanation (safe: skips tags and .badge spans)
        colored_desc = colorize_text(safe_desc)
        explanation_html = colorize_text(explanation_html)

        subpage_filename = f"{category_name.lower()}_{idx}.html"
        subpage_path = f"public/archive/{date_iso_str}/{subpage_filename}"
        relative_link_to_subpage = f"{date_iso_str}/{subpage_filename}"

        # Build Card HTML for the main daily page
        html_cards += f"""
        <li>
            <strong>{safe_title}</strong>
            <p>{colored_desc}</p>
            <div style="margin-top: 15px;">
                <a class="btn-readmore" href="{relative_link_to_subpage}">📖 Read Full UPSC Analysis →</a>
                <a class="source-link" href="{safe_url}" target="_blank">🔗 Original Source</a>
            </div>
        </li>
        """

        # Build Subpage HTML
        subpage_html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{safe_title} - UPSC Analysis</title>
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
                    margin: 0 auto;
                    padding: 20px;
                    background-color: var(--bg-color);
                    color: var(--text-main);
                    line-height: 1.8;
                }}
                .card {{
                    background: var(--card-bg);
                    padding: 45px;
                    border-radius: 12px;
                    box-shadow: 0 4px 25px rgba(0,0,0,0.04);
                    border: 1px solid var(--border-color);
                }}
                h1 {{ color: var(--secondary); font-size: 1.8rem; margin-top: 10px; }}
                .back-link {{
                    display: inline-block;
                    margin-bottom: 20px;
                    color: var(--primary);
                    text-decoration: none;
                    font-weight: 600;
                }}
                .back-link:hover {{ text-decoration: underline; }}
                .badge-num {{ background: #dbeafe; color: #1e40af; padding: 2px 6px; border-radius: 4px; font-weight: 600; }}
                .badge-date {{ background: #ffedd5; color: #c2410c; padding: 2px 6px; border-radius: 4px; font-weight: 600; }}
                .badge {{ background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 4px; font-weight: 600; border: 1px solid #fde68a; }}
                .explanation-body p {{ margin: 10px 0; }}
                .explanation-body h4 {{ color: var(--primary); margin-top: 25px; }}
                .explanation-body ul {{ padding-left: 20px; }}
                .explanation-body li {{ margin-bottom: 10px; }}
                .source-btn {{
                    display: inline-block;
                    margin-top: 30px;
                    background: var(--primary);
                    color: white;
                    padding: 10px 20px;
                    border-radius: 8px;
                    text-decoration: none;
                    font-weight: 600;
                }}
                .source-btn:hover {{ background: #1d4ed8; }}
            </style>
        </head>
        <body>
            <div class="card">
                <a class="back-link" href="../{date_iso_str}.html">← Back to Daily Briefing</a>
                <span style="font-size: 0.85rem; background: var(--primary-light); color: var(--primary); padding: 4px 10px; border-radius: 20px; font-weight: 600;">{category_name} Analysis</span>
                <h1>{safe_title}</h1>
                <hr style="border:0; border-top:1px solid var(--border-color); margin: 25px 0;">
                {explanation_html}
                <br>
                <a class="source-btn" href="{safe_url}" target="_blank">🔗 Visit Original Web Source</a>
            </div>
        </body>
        </html>
        """

        with open(subpage_path, "w", encoding="utf-8") as sf:
            sf.write(subpage_html)

    return html_cards


# Setup Archive and Today's Dates
current_date_iso = datetime.now().strftime("%Y-%m-%d")
current_date_formatted = datetime.now().strftime("%B %d, %Y")

os.makedirs("public/archive", exist_ok=True)

# Process categories with full subpage generation
national_cards_html = process_items_with_deep_dives(nat_news, "National", current_date_iso)
international_cards_html = process_items_with_deep_dives(intl_news, "International", current_date_iso)

combined_ai_content = f"""
<div class="category-banner">🇮🇳 National News & Governance</div>
<ul>{national_cards_html}</ul>

<div class="category-banner">🌍 International Relations & Global Affairs</div>
<ul>{international_cards_html}</ul>
"""

# Generate Daily HTML Page
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
        .header-bar h1 {{ margin: 0 0 10px 0; font-size: 2rem; }}
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
        }}
        .back-link:hover {{ text-decoration: underline; }}
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
        ul {{ padding-left: 0; list-style: none; }}
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
        strong {{ color: var(--secondary); font-size: 1.1rem; display: block; margin-bottom: 8px; }}

        /* Colorful Badges for concentration */
        .badge-num {{ background: #dbeafe; color: #1e40af; padding: 2px 6px; border-radius: 4px; font-weight: 600; }}
        .badge-date {{ background: #ffedd5; color: #c2410c; padding: 2px 6px; border-radius: 4px; font-weight: 600; }}
        .badge {{ background: #fef3c7; color: #92400e; padding: 2px 8px; border-radius: 4px; font-weight: 600; border: 1px solid #fde68a; }}

        .btn-readmore {{
            display: inline-block;
            background: var(--primary);
            color: white;
            padding: 6px 14px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 600;
            margin-right: 8px;
            transition: background 0.2s;
        }}
        .btn-readmore:hover {{ background: #1d4ed8; }}

        a.source-link {{
            display: inline-block;
            background: var(--primary-light);
            color: var(--primary);
            padding: 6px 14px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 0.9rem;
            font-weight: 600;
        }}
        a.source-link:hover {{ background: #dbeafe; }}
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

# Generate Index Page
archive_files = sorted([f for f in os.listdir("public/archive") if os.path.isdir(os.path.join("public/archive", f)) or f.endswith(".html")], reverse=True)
links_html = ""
for file in archive_files:
    if file.endswith(".html"):
        date_str = file.replace(".html", "")
        links_html += f'<li><a href="archive/{file}">📚 UPSC Edition – <strong>{date_str}</strong> <span style="float:right; color:#64748b; font-size:0.9rem; font-weight:normal;">View Portal →</span></a></li>\n'

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
        h1 {{ color: var(--secondary); border-bottom: 3px solid var(--primary); padding-bottom: 12px; margin-top: 0; }}
        ul {{ list-style-type: none; padding: 0; }}
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
        a:hover {{ text-decoration: underline; }}
        .subtitle {{ color: #64748b; font-size: 1.05rem; margin-bottom: 30px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🏛️ UPSC / IAS Current Affairs Portal</h1>
        <p class="subtitle">Multi-source hybrid intelligence featuring dedicated full-fledged deep-dive explanations for civil services aspirants.</p>
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
print("Advanced Modern UPSC portal build script completed successfully.")
