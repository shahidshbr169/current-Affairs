import os
import re
import time
import hashlib
import json
import html as html_lib
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

# ---------------------------------------------------------------------------
# STORY SELECTION
# ---------------------------------------------------------------------------
NATIONAL_LIMIT = 10        # change these to get more or fewer stories per day
INTERNATIONAL_LIMIT = 10

UPSC_KEYWORDS = [
    # polity & governance
    "supreme court", "high court", "constitution", "article", "parliament", "bill", "act",
    "amendment", "commission", "tribunal", "election commission", "cabinet", "scheme",
    "policy", "ministry", "rbi", "sebi", "niti aayog", "census", "reservation", "federal",
    "governor", "lok sabha", "rajya sabha", "ordinance", "statutory", "regulator",
    # economy, environment, science
    "gdp", "inflation", "budget", "gst", "msme", "export", "climate", "biodiversity",
    "wildlife", "emission", "isro", "satellite", "mission", "agriculture", "msp",
    "defence", "security", "health", "education", "report", "index",
    # international relations
    "india", "un ", "united nations", "quad", "brics", "g20", "asean", "saarc", "wto",
    "imf", "world bank", "treaty", "bilateral", "summit", "agreement", "sanction",
    "china", "pakistan", "russia", "united states", "indo-pacific", "nato", "who ",
]


def score_item(item):
    text = f"{item['title']} {item['desc']}".lower()
    score = sum(2 for kw in UPSC_KEYWORDS if kw in text)
    if item.get("trusted"):          # RSS from The Hindu / BBC
        score += 3
    return score


def select_top(items, limit):
    """Remove duplicate headlines, rank by UPSC relevance, keep the top `limit`."""
    seen, unique = set(), []
    for it in items:
        key = re.sub(r'\W+', ' ', it['title'].lower()).strip()
        if not key or key == "no title" or key in seen:
            continue
        seen.add(key)
        unique.append(it)
    unique.sort(key=score_item, reverse=True)   # stable: ties keep original order
    return unique[:limit]


def fetch_all_sources():
    national_items = []
    international_items = []

    print("==================================================")
    print("      FETCHING DATA FOR ADVANCED UPSC PORTAL      ")
    print("==================================================")

    # 1. FETCH FROM NEWSAPI.ORG
    if NEWS_API_KEY and len(NEWS_API_KEY) > 5:
        try:
            newsapi_nat_url = f"https://newsapi.org/v2/top-headlines?country={COUNTRY_CODE}&pageSize=20&apiKey={NEWS_API_KEY}"
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

            newsapi_intl_url = f"https://newsapi.org/v2/top-headlines?category=general&language=en&pageSize=20&apiKey={NEWS_API_KEY}"
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
            cur_nat_url = f"https://api.currentsapi.services/v1/search?country={COUNTRY_CODE.upper()}&language=en&page_size=20"
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

            cur_intl_url = "https://api.currentsapi.services/v1/latest-news?language=en&page_size=20"
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
                for entry in feed.entries[:20]:
                    title = getattr(entry, 'title', 'No Title')
                    link = getattr(entry, 'link', '#')
                    summary = getattr(entry, 'summary', '') or getattr(entry, 'description', '')

                    item_obj = {"title": title, "url": link, "desc": summary, "trusted": True}
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

    return select_top(national_items, NATIONAL_LIMIT), select_top(international_items, INTERNATIONAL_LIMIT)


nat_news, intl_news = fetch_all_sources()

client = OpenAI(
    base_url="https://api.groq.com/openai/v1",
    api_key=GROQ_API_KEY,
)

# Dates first, then numbers/statistics (one pass so matches never overlap)
BADGE_PATTERN = re.compile(
    r'\b(20\d{2}|January|February|March|April|May|June|July|August|September|October|November|December)\b'
    r'|\b(\d+(?:\.\d+)?(?:%|(?:rd|th|st|nd| crore| lakh| billion| million)\b)?)(?!\w)'
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


def generate_analysis(prompt, fallback_html, attempts=4):
    """Call Groq with retries/backoff so rate limits don't degrade content quality."""
    for attempt in range(1, attempts + 1):
        try:
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3  # lower = fewer invented facts
            )
            content = (response.choices[0].message.content or "").replace("```html", "").replace("```", "").strip()
            if content:
                return content
            raise ValueError("Empty response from model")
        except Exception as e:
            wait = 5 * attempt
            print(f"Groq attempt {attempt}/{attempts} failed: {e}. Retrying in {wait}s...")
            time.sleep(wait)
    return fallback_html


def clean_text(raw):
    """Strip HTML tags/entities from feed text so cards read cleanly."""
    text = re.sub(r'<[^>]+>', ' ', raw or '')
    text = html_lib.unescape(text)
    return re.sub(r'\s+', ' ', text).strip()


def trim_text(text, limit=320):
    if len(text) <= limit:
        return text
    cut = text[:limit].rsplit(' ', 1)[0].rstrip(' ,;:-')
    return cut + '…'


def esc(text):
    return html_lib.escape(text, quote=False)


def esc_attr(text):
    return html_lib.escape(text, quote=True)


def pretty_date(dt):
    return f"{dt.day} {dt.strftime('%B %Y')}"


# ---------------------------------------------------------------------------
# SITE ASSETS (written once per run to public/assets/)
# ---------------------------------------------------------------------------
SITE_CSS = """
:root{
  --bg:#f5f6f8; --surface:#ffffff; --surface-2:#eef2f7; --text:#243044; --muted:#6b7686;
  --heading:#0b1a33; --border:#e1e6ee; --accent:#1e4fd8; --accent-ink:#ffffff; --accent-soft:#e9efff;
  --nat:#1e4fd8; --nat-soft:#e9efff; --intl:#0e7490; --intl-soft:#def3f8;
  --shadow:0 1px 2px rgba(15,23,42,.04),0 10px 28px rgba(15,23,42,.06);
  --sans:'Inter',system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;
  --serif:'Source Serif 4',Georgia,'Times New Roman',serif;
  --radius:14px;
}
[data-theme="dark"]{
  --bg:#0d1320; --surface:#151d2e; --surface-2:#1b2538; --text:#d3dbe8; --muted:#8e9bb0;
  --heading:#f2f5fb; --border:#27324a; --accent:#6d9bff; --accent-ink:#0b1220; --accent-soft:#1d2c52;
  --nat:#7aa5ff; --nat-soft:#1d2c52; --intl:#52c7de; --intl-soft:#12333c;
  --shadow:0 1px 2px rgba(0,0,0,.3),0 10px 28px rgba(0,0,0,.35);
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--text);font-family:var(--sans);line-height:1.6;-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--accent);text-decoration:none}
a:hover{text-decoration:underline}
img{max-width:100%}

/* ---------- layout ---------- */
.wrap{max-width:1040px;margin:0 auto;padding:32px 20px 72px}
.wrap.narrow{max-width:760px}
.topbar{position:sticky;top:0;z-index:20;background:var(--surface);background:color-mix(in srgb,var(--surface) 88%,transparent);-webkit-backdrop-filter:blur(10px);backdrop-filter:blur(10px);border-bottom:1px solid var(--border)}
.topbar-inner{max-width:1040px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;justify-content:space-between;gap:16px}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;color:var(--heading);letter-spacing:-.01em}
.brand:hover{text-decoration:none}
.brand-mark{display:grid;place-items:center;width:32px;height:32px;border-radius:9px;background:var(--accent);color:var(--accent-ink);font-size:16px}
.nav{display:flex;align-items:center;gap:6px}
.nav a{color:var(--muted);font-weight:500;font-size:.92rem;padding:6px 10px;border-radius:8px}
.nav a:hover{background:var(--surface-2);color:var(--heading);text-decoration:none}
.icon-btn{border:1px solid var(--border);background:var(--surface);color:var(--text);width:36px;height:36px;border-radius:10px;cursor:pointer;font-size:15px}
.icon-btn:hover{background:var(--surface-2)}
.progress{position:fixed;top:0;left:0;height:3px;width:0;background:var(--accent);z-index:30}
.crumbs{font-size:.85rem;color:var(--muted);margin-bottom:22px}
.crumbs span{margin:0 4px}
.footer{border-top:1px solid var(--border);padding:26px 20px;text-align:center;color:var(--muted);font-size:.85rem}

/* ---------- headings & hero ---------- */
.eyebrow{margin:0 0 8px;font-size:.78rem;font-weight:700;letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.hero{padding:18px 0 28px}
.hero h1,.page-head h1{margin:0 0 12px;font-family:var(--serif);font-size:2.8rem;line-height:1.12;letter-spacing:-.02em;color:var(--heading)}
.lead{margin:0;max-width:640px;font-size:1.1rem;color:var(--muted)}
.page-head{padding:6px 0 22px}
.chips{display:flex;flex-wrap:wrap;gap:10px;margin-top:20px}
.chip{display:inline-block;padding:8px 14px;border-radius:999px;font-size:.88rem;font-weight:600;border:1px solid var(--border);background:var(--surface);color:var(--heading)}
.chip:hover{text-decoration:none;border-color:var(--accent)}
.chip-national{border-left:4px solid var(--nat)}
.chip-international{border-left:4px solid var(--intl)}
.section-title{margin:44px 0 18px;font-size:1.25rem;font-weight:700;color:var(--heading);display:flex;align-items:center;gap:12px;letter-spacing:-.01em}
.section-title::before{content:"";width:5px;height:24px;border-radius:3px;background:var(--accent)}
.section-title.nat::before{background:var(--nat)}
.section-title.intl::before{background:var(--intl)}
.section-head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:40px 0 4px}
.section-head h2{margin:0;font-size:1.4rem;color:var(--heading)}
.search{padding:10px 14px;min-width:240px;border:1px solid var(--border);border-radius:10px;background:var(--surface);color:var(--text);font:inherit;font-size:.92rem}
.search:focus{outline:2px solid var(--accent);outline-offset:1px}

/* ---------- buttons & tags ---------- */
.btn{display:inline-block;padding:10px 18px;border-radius:10px;font-weight:600;font-size:.92rem;border:1px solid transparent;cursor:pointer}
.btn:hover{text-decoration:none}
.btn-sm{padding:7px 14px;font-size:.85rem}
.btn-primary{background:var(--accent);color:var(--accent-ink)}
.btn-primary:hover{filter:brightness(1.08)}
.btn-ghost{background:transparent;color:var(--text);border-color:var(--border)}
.btn-ghost:hover{background:var(--surface-2)}
.tag{display:inline-block;font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase;padding:4px 10px;border-radius:999px}
.tag-national{background:var(--nat-soft);color:var(--nat)}
.tag-international{background:var(--intl-soft);color:var(--intl)}

/* ---------- index ---------- */
.featured{display:flex;justify-content:space-between;align-items:center;gap:24px;padding:30px;border-radius:18px;background:linear-gradient(135deg,#102349,#1e4fd8);color:#fff;box-shadow:var(--shadow)}
.featured .eyebrow{color:#b9ccff}
.featured h2{margin:0 0 6px;font-family:var(--serif);font-size:1.9rem;line-height:1.2}
.featured p{margin:0;color:#d6e0ff}
.featured .btn{background:#fff;color:#102349;white-space:nowrap}
.month{margin:30px 0 12px;font-size:.78rem;text-transform:uppercase;letter-spacing:.12em;color:var(--muted);font-weight:700}
.edition-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(270px,1fr));gap:14px}
.edition{display:flex;align-items:center;gap:14px;padding:14px 16px;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--text);transition:transform .15s,border-color .15s}
.edition:hover{text-decoration:none;transform:translateY(-2px);border-color:var(--accent)}
.edition-date{display:flex;flex-direction:column;align-items:center;justify-content:center;min-width:52px;height:56px;border-radius:10px;background:var(--accent-soft);color:var(--accent);line-height:1}
.edition-day{font-family:var(--serif);font-size:1.5rem;font-weight:700}
.edition-mon{font-size:.68rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;margin-top:3px}
.edition-info strong{display:block;color:var(--heading);font-size:.98rem}
.edition-info span{font-size:.82rem;color:var(--muted)}

/* ---------- story cards (daily page) ---------- */
.story{display:flex;gap:20px;padding:24px;background:var(--surface);border:1px solid var(--border);border-radius:var(--radius);box-shadow:var(--shadow);margin-bottom:16px;transition:transform .15s,border-color .15s}
.story:hover{transform:translateY(-2px);border-color:var(--accent)}
.story-num{flex:0 0 auto;min-width:38px;font-family:var(--serif);font-size:1.7rem;font-weight:700;line-height:1.2;color:var(--nat)}
.story.international .story-num{color:var(--intl)}
.story h3{margin:0 0 10px;font-family:var(--serif);font-size:1.32rem;line-height:1.3;letter-spacing:-.005em}
.story h3 a{color:var(--heading)}
.story h3 a:hover{color:var(--accent);text-decoration:none}
.summary{margin:0 0 16px;font-size:1rem;line-height:1.7;color:var(--text)}
.story-actions{display:flex;flex-wrap:wrap;gap:10px}

/* ---------- article (analysis page) ---------- */
.article header{margin-bottom:30px}
.article h1{font-family:var(--serif);font-size:2.25rem;line-height:1.2;letter-spacing:-.015em;color:var(--heading);margin:14px 0 14px}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:8px;color:var(--muted);font-size:.9rem}
.meta .dot{opacity:.5}
.explanation-body{font-family:var(--serif);font-size:1.14rem;line-height:1.8;color:var(--text)}
.explanation-body p{margin:0 0 16px;padding:16px 20px;background:var(--surface);border:1px solid var(--border);border-left:4px solid var(--accent);border-radius:10px}
.explanation-body > p:first-child{font-size:1.2rem;border-left-color:var(--nat)}
.explanation-body p strong{display:block;margin-bottom:6px;font-family:var(--sans);font-size:.72rem;font-weight:700;letter-spacing:.09em;text-transform:uppercase;color:var(--accent)}
.explanation-body h4{margin:38px 0 14px;padding-bottom:10px;border-bottom:1px solid var(--border);font-family:var(--sans);font-size:.8rem;font-weight:700;letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.explanation-body ul{list-style:none;margin:0 0 8px;padding:0;display:grid;gap:12px}
.explanation-body li{padding:14px 18px;background:var(--surface);border:1px solid var(--border);border-radius:10px;line-height:1.7}
.explanation-body li em{display:block;margin-bottom:4px;font-style:normal;font-family:var(--sans);font-size:.74rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--accent)}
.actions{margin-top:30px}
.pager{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:44px}
.pager a{display:block;padding:16px 18px;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--heading);font-weight:600;font-size:.95rem;line-height:1.4}
.pager a:hover{text-decoration:none;border-color:var(--accent)}
.pager small{display:block;margin-bottom:4px;color:var(--muted);font-size:.72rem;font-weight:700;letter-spacing:.08em;text-transform:uppercase}
.pager .next{text-align:right}

/* ---------- highlight badges ---------- */
.badge{display:inline-block;margin:2px 4px 2px 0;padding:1px 10px;border-radius:999px;background:#fff4d6;color:#8a4b00;border:1px solid #f3dc9c;font-family:var(--sans);font-size:.88rem;font-weight:600;line-height:1.6}
.badge-num{padding:0 5px;border-radius:5px;background:#e6eeff;color:#1e40af;font-weight:600}
.badge-date{padding:0 5px;border-radius:5px;background:#fff0dd;color:#b45309;font-weight:600}
[data-theme="dark"] .badge{background:#3a2d0c;color:#f6cf75;border-color:#5a4513}
[data-theme="dark"] .badge-num{background:#1d2c52;color:#9db9ff}
[data-theme="dark"] .badge-date{background:#3a2a10;color:#f3b86a}

/* ---------- responsive & print ---------- */
@media (max-width:640px){
  .wrap{padding:24px 16px 56px}
  .hero h1,.page-head h1{font-size:2.1rem}
  .article h1{font-size:1.7rem}
  .explanation-body{font-size:1.05rem}
  .story{flex-direction:column;gap:8px;padding:20px}
  .featured{flex-direction:column;align-items:flex-start;padding:24px}
  .pager{grid-template-columns:1fr}
  .pager .next{text-align:left}
  .nav a.hide-sm{display:none}
  .search{width:100%}
}
@media print{
  .topbar,.progress,.pager,.actions,.footer{display:none}
  body{background:#fff}
  .explanation-body p,.explanation-body li{break-inside:avoid}
}
"""

SITE_JS = """
(function () {
  var root = document.documentElement, key = 'upsc-theme', saved = null;
  try { saved = localStorage.getItem(key); } catch (e) {}
  var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  root.setAttribute('data-theme', saved || (prefersDark ? 'dark' : 'light'));

  document.addEventListener('DOMContentLoaded', function () {
    var btn = document.getElementById('theme-toggle');
    function label() { if (btn) btn.textContent = root.getAttribute('data-theme') === 'dark' ? '☀️' : '🌙'; }
    if (btn) {
      label();
      btn.addEventListener('click', function () {
        var next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
        root.setAttribute('data-theme', next);
        try { localStorage.setItem(key, next); } catch (e) {}
        label();
      });
    }

    var bar = document.getElementById('progress');
    if (bar) {
      window.addEventListener('scroll', function () {
        var h = document.documentElement;
        var total = h.scrollHeight - h.clientHeight;
        bar.style.width = (total > 0 ? (h.scrollTop / total) * 100 : 0) + '%';
      }, { passive: true });
    }

    var q = document.getElementById('archive-search');
    if (q) {
      q.addEventListener('input', function () {
        var v = q.value.trim().toLowerCase();
        document.querySelectorAll('.edition').forEach(function (el) {
          var hit = el.getAttribute('data-date').toLowerCase().indexOf(v) > -1;
          el.style.display = hit ? '' : 'none';
        });
        document.querySelectorAll('.month-group').forEach(function (g) {
          var visible = Array.prototype.some.call(g.querySelectorAll('.edition'), function (el) {
            return el.style.display !== 'none';
          });
          g.style.display = visible ? '' : 'none';
        });
      });
    }
  });
})();
"""

FONTS_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700'
    '&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600;8..60,700&display=swap" rel="stylesheet">'
)

FOOTER = '<footer class="footer">AI-assisted summaries built from public news feeds. Always verify facts against official sources and standard references.</footer>'


def write_assets():
    os.makedirs("public/assets", exist_ok=True)
    with open("public/assets/style.css", "w", encoding="utf-8") as f:
        f.write(SITE_CSS)
    with open("public/assets/site.js", "w", encoding="utf-8") as f:
        f.write(SITE_JS)


def page_head(title, description, root):
    return f"""<!DOCTYPE html>
<html lang="en" data-theme="light">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{esc(title)}</title>
<meta name="description" content="{esc_attr(description)}">
{FONTS_LINK}
<link rel="stylesheet" href="{root}assets/style.css">
<script src="{root}assets/site.js"></script>
</head>"""


def topbar(root):
    return f"""<header class="topbar"><div class="topbar-inner">
  <a class="brand" href="{root}index.html"><span class="brand-mark">🏛️</span><span>UPSC Current Affairs</span></a>
  <nav class="nav">
    <a class="hide-sm" href="{root}index.html#archive">Archive</a>
    <button class="icon-btn" id="theme-toggle" type="button" aria-label="Toggle dark mode" title="Toggle theme">🌙</button>
  </nav>
</div></header>"""


# ---------------------------------------------------------------------------
# CONTENT GENERATION
# ---------------------------------------------------------------------------
def build_stories(items, category_name):
    stories = []
    for idx, item in enumerate(items):
        title = clean_text(item['title']) or "Untitled"
        desc = clean_text(item['desc'])
        url = item['url'] or "#"

        print(f"Generating full-fledged explanation for [{category_name}] item {idx+1}: {title[:40]}...")

        prompt = f"""
Process the following raw news item for the {category_name} pillar.

News Title: {title}
News Details: {desc}

{PILLAR_SCHEMAS[category_name]}
"""
        fallback = f"<div class='explanation-body'><p>{esc(desc or title)}</p></div>"
        explanation = generate_analysis(prompt, fallback)
        explanation = re.sub(r'<script.*?</script>', '', explanation, flags=re.S | re.I)

        words = len(re.sub(r'<[^>]+>', ' ', explanation).split())
        minutes = max(1, round(words / 200))
        explanation = colorize_text(explanation)

        # Stable file name derived from the story URL (title only if there is no URL)
        key = url if url not in ("", "#") else title
        story_id = hashlib.md5(key.encode("utf-8")).hexdigest()[:8]

        stories.append({
            "title": title,
            "desc": desc,
            "url": url,
            "html": explanation,
            "minutes": minutes,
            "filename": f"{category_name.lower()}_{story_id}.html",
        })
    return stories


# ---------------------------------------------------------------------------
# PAGE WRITERS
# ---------------------------------------------------------------------------
def write_subpages(stories, category_name, date_iso, dt):
    folder = f"public/archive/{date_iso}"
    os.makedirs(folder, exist_ok=True)
    cls = category_name.lower()
    pretty = pretty_date(dt)

    for i, s in enumerate(stories):
        prev_s = stories[i - 1] if i > 0 else None
        next_s = stories[i + 1] if i < len(stories) - 1 else None

        if prev_s:
            prev_html = f'<a class="prev" href="{prev_s["filename"]}"><small>← Previous</small>{esc(trim_text(prev_s["title"], 90))}</a>'
        else:
            prev_html = '<span></span>'
        if next_s:
            next_html = f'<a class="next" href="{next_s["filename"]}"><small>Next →</small>{esc(trim_text(next_s["title"], 90))}</a>'
        else:
            next_html = '<span></span>'

        page = page_head(f"{s['title']} · UPSC Current Affairs", trim_text(s['desc'] or s['title'], 160), "../../") + f"""
<body>
<div class="progress" id="progress"></div>
{topbar('../../')}
<main class="wrap narrow">
  <nav class="crumbs"><a href="../../index.html">Archive</a><span>›</span><a href="../{date_iso}.html">{pretty}</a><span>›</span>{category_name}</nav>
  <article class="article">
    <header>
      <span class="tag tag-{cls}">{category_name}</span>
      <h1>{esc(s['title'])}</h1>
      <div class="meta"><span>{pretty}</span><span class="dot">•</span><span>{s['minutes']} min read</span></div>
    </header>
    {s['html']}
    <div class="actions"><a class="btn btn-primary" href="{esc_attr(s['url'])}" target="_blank" rel="noopener">Read original source ↗</a></div>
  </article>
  <nav class="pager">{prev_html}{next_html}</nav>
</main>
{FOOTER}
</body>
</html>"""

        with open(f"{folder}/{s['filename']}", "w", encoding="utf-8") as f:
            f.write(page)


def render_cards(stories, category_name, date_iso):
    cls = category_name.lower()
    out = ""
    for i, s in enumerate(stories, 1):
        summary = ""
        if s['desc']:
            summary = f'<p class="summary">{colorize_text(esc(trim_text(s["desc"])))}</p>'
        href = f"{date_iso}/{s['filename']}"
        out += f"""
    <article class="story {cls}">
      <div class="story-num">{i:02d}</div>
      <div class="story-body">
        <h3><a href="{href}">{esc(s['title'])}</a></h3>
        {summary}
        <div class="story-actions">
          <a class="btn btn-primary btn-sm" href="{href}">Read analysis →</a>
          <a class="btn btn-ghost btn-sm" href="{esc_attr(s['url'])}" target="_blank" rel="noopener">Source ↗</a>
        </div>
      </div>
    </article>"""
    return out


def write_daily_page(date_iso, dt, national, international):
    pretty = pretty_date(dt)
    weekday = dt.strftime("%A")
    nat_cards = render_cards(national, "National", date_iso)
    intl_cards = render_cards(international, "International", date_iso)

    page = page_head(f"UPSC Current Affairs · {pretty}",
                     f"Daily UPSC current affairs for {pretty}: national governance and international relations, mapped to the syllabus.",
                     "../") + f"""
<body>
{topbar('../')}
<main class="wrap">
  <nav class="crumbs"><a href="../index.html">Archive</a><span>›</span>{pretty}</nav>
  <header class="page-head">
    <p class="eyebrow">{weekday} · Daily Briefing</p>
    <h1>{pretty}</h1>
    <p class="lead">Syllabus-mapped analysis with prelims pointers and mains perspectives.</p>
    <div class="chips">
      <a class="chip chip-national" href="#national">🇮🇳 National &amp; Governance · {len(national)}</a>
      <a class="chip chip-international" href="#international">🌍 International Relations · {len(international)}</a>
    </div>
  </header>

  <section id="national">
    <h2 class="section-title nat">National News &amp; Governance</h2>
    {nat_cards}
  </section>

  <section id="international">
    <h2 class="section-title intl">International Relations &amp; Global Affairs</h2>
    {intl_cards}
  </section>
</main>
{FOOTER}
</body>
</html>"""

    with open(f"public/archive/{date_iso}.html", "w", encoding="utf-8") as f:
        f.write(page)

    # Small manifest so the archive index can show accurate story counts
    with open(f"public/archive/{date_iso}/_meta.json", "w", encoding="utf-8") as f:
        json.dump({"national": len(national), "international": len(international)}, f)


def list_editions():
    editions = []
    for name in os.listdir("public/archive"):
        m = re.fullmatch(r'(\d{4}-\d{2}-\d{2})\.html', name)
        if not m:
            continue
        iso = m.group(1)
        try:
            dt = datetime.strptime(iso, "%Y-%m-%d")
        except ValueError:
            continue
        counts = None
        meta_path = os.path.join("public/archive", iso, "_meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as mf:
                    counts = json.load(mf)
            except Exception:
                counts = None
        editions.append({"iso": iso, "dt": dt, "counts": counts})
    editions.sort(key=lambda e: e["iso"], reverse=True)
    return editions


def counts_label(counts):
    if not counts:
        return "Daily briefing"
    return f"{counts.get('national', 0)} national · {counts.get('international', 0)} international"


def write_index():
    editions = list_editions()

    featured = ""
    if editions:
        latest = editions[0]
        featured = f"""
  <section class="featured">
    <div>
      <p class="eyebrow">Latest edition</p>
      <h2>{pretty_date(latest['dt'])}</h2>
      <p>{latest['dt'].strftime('%A')} · {counts_label(latest['counts'])}</p>
    </div>
    <a class="btn" href="archive/{latest['iso']}.html">Read today's briefing →</a>
  </section>"""

    groups, current_month, grid = "", None, ""
    for e in editions:
        month = e['dt'].strftime("%B %Y")
        if month != current_month:
            if current_month is not None:
                groups += f'<section class="month-group"><h3 class="month">{current_month}</h3><div class="edition-grid">{grid}</div></section>\n'
            current_month, grid = month, ""
        search_text = f"{e['iso']} {month} {e['dt'].day} {e['dt'].strftime('%A')}"
        grid += f"""
      <a class="edition" href="archive/{e['iso']}.html" data-date="{esc_attr(search_text)}">
        <div class="edition-date"><span class="edition-day">{e['dt'].day}</span><span class="edition-mon">{e['dt'].strftime('%b')}</span></div>
        <div class="edition-info"><strong>{e['dt'].strftime('%A')}</strong><span>{counts_label(e['counts'])}</span></div>
      </a>"""
    if current_month is not None:
        groups += f'<section class="month-group"><h3 class="month">{current_month}</h3><div class="edition-grid">{grid}</div></section>\n'

    page = page_head("UPSC Current Affairs · Daily Briefings & Archive",
                     "Daily UPSC Civil Services current affairs with syllabus mapping, prelims pointers and mains analysis.",
                     "") + f"""
<body>
{topbar('')}
<main class="wrap">
  <section class="hero">
    <p class="eyebrow">Civil Services · Daily Briefing</p>
    <h1>UPSC Current Affairs</h1>
    <p class="lead">National governance and international relations news, mapped to the GS syllabus with prelims pointers and mains perspectives.</p>
  </section>
  {featured}
  <section id="archive">
    <div class="section-head">
      <h2>Archive</h2>
      <input class="search" id="archive-search" type="search" placeholder="Search by date or month…" aria-label="Search archive">
    </div>
    {groups}
  </section>
</main>
{FOOTER}
</body>
</html>"""

    with open("public/index.html", "w", encoding="utf-8") as f:
        f.write(page)


# ---------------------------------------------------------------------------
# RUN
# ---------------------------------------------------------------------------
current_dt = datetime.now()
current_date_iso = current_dt.strftime("%Y-%m-%d")

os.makedirs("public/archive", exist_ok=True)
write_assets()

national_stories = build_stories(nat_news, "National")
international_stories = build_stories(intl_news, "International")

write_subpages(national_stories, "National", current_date_iso, current_dt)
write_subpages(international_stories, "International", current_date_iso, current_dt)
write_daily_page(current_date_iso, current_dt, national_stories, international_stories)
write_index()

print("Advanced Modern UPSC portal build script completed successfully.")
