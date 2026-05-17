#!/usr/bin/env python3
"""
generate_blog.py — pianist.es Meertalige Blog Generator
═══════════════════════════════════════════════════════════
Haalt nieuwe Nederlandse blogposts op uit Contentful (language=nl, status=published),
vertaalt ze naar 5 talen via Claude, en genereert HTML-pagina's per taal.

Ondersteunt:
- thumbnail (Contentful Media veld)
- body (Contentful Rich Text veld)  ← nieuw
- title, slug, excerpt, category, publishDate

Gebruik: python scripts/generate_blog.py
"""

import os
import re
import json
import time
import html as html_lib
from pathlib import Path
from datetime import datetime, date

import requests

# ── Config ────────────────────────────────────────────────────────────────────
SPACE_ID      = os.environ["CONTENTFUL_SPACE_ID"]
ACCESS_TOKEN  = os.environ["CONTENTFUL_ACCESS_TOKEN"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")
FORCE_SLUG    = os.environ.get("FORCE_SLUG", "").strip()
SITE_URL      = "https://pianist.es"

LANGS = {
    "es": {"prefix": "",    "html_lang": "es", "label": "Español",    "flag": "🇪🇸"},
    "en": {"prefix": "en",  "html_lang": "en", "label": "English",    "flag": "🇬🇧"},
    "nl": {"prefix": "nl",  "html_lang": "nl", "label": "Nederlands", "flag": "🇳🇱"},
    "de": {"prefix": "de",  "html_lang": "de", "label": "Deutsch",    "flag": "🇩🇪"},
    "fr": {"prefix": "fr",  "html_lang": "fr", "label": "Français",   "flag": "🇫🇷"},
    "ru": {"prefix": "ru",  "html_lang": "ru", "label": "Русский",    "flag": "🇷🇺"},
}

BLOG_INDEX = Path("blog-index.json")

# ── Contentful ophalen ────────────────────────────────────────────────────────
def fetch_contentful(extra_params=""):
    url = (
        f"https://cdn.contentful.com/spaces/{SPACE_ID}/entries"
        f"?access_token={ACCESS_TOKEN}"
        f"&content_type=blogPost"
        f"&fields.language=nl"
        f"&fields.status=published"
        f"&include=2"
        f"&order=-fields.publishDate"
        f"{extra_params}"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


def get_asset_url(data, asset_id):
    """Haal de URL op van een Contentful asset uit de includes."""
    for asset in data.get("includes", {}).get("Asset", []):
        if asset["sys"]["id"] == asset_id:
            file_url = asset.get("fields", {}).get("file", {}).get("url", "")
            if file_url.startswith("//"):
                return "https:" + file_url
            return file_url
    return ""


def rich_text_to_html(node):
    """
    Converteert een Contentful Rich Text document-node naar HTML.
    Ondersteunt: paragraph, heading-2..6, hyperlink, bold, italic,
                 unordered-list, ordered-list, list-item, hr, blockquote.
    """
    if not node:
        return ""

    node_type = node.get("nodeType", "")
    content   = node.get("content", [])

    # ── Inline nodes ──────────────────────────────────────────────────────────
    if node_type == "text":
        text = html_lib.escape(node.get("value", ""))
        for mark in node.get("marks", []):
            t = mark.get("type", "")
            if t == "bold":
                text = f"<strong>{text}</strong>"
            elif t == "italic":
                text = f"<em>{text}</em>"
            elif t == "underline":
                text = f"<u>{text}</u>"
            elif t == "code":
                text = f"<code>{text}</code>"
        return text

    if node_type == "hyperlink":
        href = html_lib.escape(node.get("data", {}).get("uri", "#"))
        inner = "".join(rich_text_to_html(c) for c in content)
        return f'<a href="{href}" target="_blank" rel="noopener">{inner}</a>'

    # ── Block nodes ───────────────────────────────────────────────────────────
    inner = "".join(rich_text_to_html(c) for c in content)

    if node_type == "document":
        return inner

    if node_type == "paragraph":
        stripped = inner.strip()
        return f"<p>{stripped}</p>\n" if stripped else ""

    if node_type == "heading-2":
        return f"<h2>{inner}</h2>\n"
    if node_type == "heading-3":
        return f"<h3>{inner}</h3>\n"
    if node_type == "heading-4":
        return f"<h4>{inner}</h4>\n"
    if node_type == "heading-5":
        return f"<h5>{inner}</h5>\n"
    if node_type == "heading-6":
        return f"<h6>{inner}</h6>\n"

    if node_type == "unordered-list":
        return f"<ul>\n{inner}</ul>\n"
    if node_type == "ordered-list":
        return f"<ol>\n{inner}</ol>\n"
    if node_type == "list-item":
        return f"  <li>{inner.strip()}</li>\n"

    if node_type == "blockquote":
        return f"<blockquote>{inner}</blockquote>\n"

    if node_type == "hr":
        return "<hr>\n"

    if node_type == "embedded-asset-block":
        asset_id = node.get("data", {}).get("target", {}).get("sys", {}).get("id", "")
        # Asset URL is resolved separately; here we emit a placeholder with the ID
        return f'<figure data-asset-id="{asset_id}"></figure>\n'

    # Fallback: just return inner content
    return inner


# ── Claude vertaling ──────────────────────────────────────────────────────────
def translate_post(title_nl, excerpt_nl, body_html_nl, slug_nl, target_langs):
    translations = {}
    
    for lang in target_langs:
        lang_names = {
            "es": "Spanish (Castilian, as spoken in Spain)",
            "en": "English",
            "de": "German",
            "fr": "French",
            "ru": "Russian (Cyrillic script)"
        }
        lang_name = lang_names.get(lang, lang)
        
        prompt = f"""You are a professional translator specializing in music, events, and wedding industry content.
Translate this Dutch blog post about pianist Thomas Verheul (based in Málaga, Spain) into {lang_name}.

Return ONLY valid JSON — no markdown, no code fences, no explanation:
{{
  "{lang}": {{"title": "...", "excerpt": "...", "body_html": "...", "slug": "..."}}
}}

Rules:
- Preserve all HTML tags exactly: <h2>, <h3>, <p>, <a href="...">, <ul>, <li>, <ol>, <strong>, <em>, <blockquote>, <hr>
- "slug": URL-friendly version of the translated title (lowercase, hyphens, no special chars, max 60 chars)
- Keep proper nouns unchanged: Thomas Verheul, Málaga, Marbella, Costa del Sol, Andalucía
- Make the translation feel natural and native

DUTCH TITLE: {title_nl}
DUTCH EXCERPT: {excerpt_nl}
DUTCH BODY HTML:
{body_html_nl}"""

        try:
            response = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": ANTHROPIC_KEY,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": ANTHROPIC_MODEL,
                    "max_tokens": 16000,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=120,
            )
            response.raise_for_status()
            raw = response.json()["content"][0]["text"].strip()
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
            parsed = json.loads(raw)
            translations[lang] = parsed[lang]
            print(f"   ✅ {lang.upper()} vertaald")
        except Exception as e:
            print(f"   ⚠️  {lang.upper()} vertaling mislukt: {e}")
            continue
    
    return translations


# ── Slugify ───────────────────────────────────────────────────────────────────
def slugify(s):
    s = s.lower()
    for a, b in [("á","a"),("é","e"),("í","i"),("ó","o"),("ú","u"),("ü","u"),
                 ("ñ","n"),("ä","a"),("ö","o"),("ü","u"),("è","e"),("ê","e"),
                 ("à","a"),("â","a"),("ô","o"),("û","u"),("ç","c")]:
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9\s-]", "", s)
    s = re.sub(r"\s+", "-", s).strip("-")
    s = re.sub(r"-+", "-", s)
    return s[:60]


# ── HTML pagina genereren ─────────────────────────────────────────────────────
def format_date(iso_date, lang):
    """Formatteer datum per taal."""
    months = {
        "nl": ["jan","feb","mrt","apr","mei","jun","jul","aug","sep","okt","nov","dec"],
        "en": ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
        "es": ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"],
        "de": ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"],
        "fr": ["jan","fév","mar","avr","mai","jun","jul","aoû","sep","oct","nov","déc"],
        "ru": ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"],
    }
    try:
        d = datetime.fromisoformat(str(iso_date))
        m = months.get(lang, months["en"])
        return f"{d.day} {m[d.month - 1]} {d.year}"
    except Exception:
        return str(iso_date)


def build_hreflang(slugs):
    """Genereer hreflang tags voor alle taalpagina's."""
    lines = []
    for lang, data in LANGS.items():
        slug = slugs.get(lang, "")
        if not slug:
            continue
        prefix = data["prefix"]
        url = f"{SITE_URL}/{prefix}/blog/{slug}/" if prefix else f"{SITE_URL}/blog/{slug}/"
        lines.append(f'  <link rel="alternate" hreflang="{data["html_lang"]}" href="{url}">')
    lines.append(f'  <link rel="alternate" hreflang="x-default" href="{SITE_URL}/blog/{slugs.get("es", "")}/">')
    return "\n".join(lines)


def build_lang_switcher(slugs, current_lang):
    """Taalknopjes bovenaan het artikel."""
    buttons = []
    for lang, data in LANGS.items():
        slug = slugs.get(lang, "")
        if not slug:
            continue
        prefix = data["prefix"]
        url = f"/{prefix}/blog/{slug}/" if prefix else f"/blog/{slug}/"
        active = ' class="active"' if lang == current_lang else ""
        buttons.append(
            f'<a href="{url}"{active}>{data["flag"]} {data["label"]}</a>'
        )
    return "\n        ".join(buttons)


def generate_html(
    lang, slug, title, excerpt, body_html, thumbnail_url,
    category, publish_date, all_slugs, back_url
):
    """Genereer een volledige HTML-blogpagina."""
    data        = LANGS[lang]
    prefix      = data["prefix"]
    html_lang   = data["html_lang"]
    canon_url   = f"{SITE_URL}/{prefix}/blog/{slug}/" if prefix else f"{SITE_URL}/blog/{slug}/"
    home_url    = f"/{prefix}/" if prefix else "/"
    blog_url    = f"/{prefix}/blog/" if prefix else "/blog/"
    date_str    = format_date(publish_date, lang)
    hreflang    = build_hreflang(all_slugs)
    lang_switch = build_lang_switcher(all_slugs, lang)

    # Thumbnail HTML
    if thumbnail_url:
        thumb_html = f'''  <div class="blog-hero">
    <img src="{thumbnail_url}" alt="{html_lib.escape(title)}" class="blog-hero-img" loading="eager">
  </div>'''
    else:
        thumb_html = ""

    # Back label per taal
    back_labels = {
        "nl": "← Terug naar blog",
        "en": "← Back to blog",
        "es": "← Volver al blog",
        "de": "← Zurück zum Blog",
        "fr": "← Retour au blog",
        "ru": "← Назад к блогу",
    }
    book_labels = {
        "nl": "Pianist boeken →",
        "en": "Book Pianist →",
        "es": "Reservar Pianista →",
        "de": "Pianist buchen →",
        "fr": "Réserver Pianiste →",
        "ru": "Забронировать →",
    }
    back_label = back_labels.get(lang, back_labels["en"])
    book_label = book_labels.get(lang, book_labels["en"])
    book_url   = f"{home_url}#offerte"

    # Schema.org Article
    schema = json.dumps({
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title,
        "description": excerpt,
        "image": thumbnail_url or "",
        "datePublished": str(publish_date),
        "author": {
            "@type": "Person",
            "name": "Thomas Verheul",
            "url": SITE_URL
        },
        "publisher": {
            "@type": "Organization",
            "name": "Pianist.es",
            "url": SITE_URL
        },
        "url": canon_url,
        "inLanguage": html_lang,
    }, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="{html_lang}">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html_lib.escape(title)} | Pianist.es</title>
  <meta name="description" content="{html_lib.escape(excerpt)}">
  <meta property="og:title" content="{html_lib.escape(title)}">
  <meta property="og:description" content="{html_lib.escape(excerpt)}">
  <meta property="og:type" content="article">
  <meta property="og:url" content="{canon_url}">
  {f'<meta property="og:image" content="{thumbnail_url}">' if thumbnail_url else ""}
  <link rel="canonical" href="{canon_url}">
{hreflang}
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,700;0,900;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
  <script type="application/ld+json">{schema}</script>
  <style>
    :root {{
      --gold: #c9a96e; --gold-dark: #a07840; --gold-light: #e8d5b0;
      --cream: #faf8f3; --white: #ffffff; --dark: #1c1a16;
      --mid: #4a4540; --muted: #8a8070; --border: #e8e0d0;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      font-family: 'DM Sans', sans-serif;
      background: var(--cream); color: var(--dark);
      line-height: 1.7;
    }}

    /* ── NAV ── */
    .site-nav {{
      position: sticky; top: 0; z-index: 100;
      background: rgba(250,248,243,0.95); backdrop-filter: blur(12px);
      border-bottom: 1px solid var(--border);
      padding: 1rem 2rem;
      display: flex; align-items: center; justify-content: space-between;
    }}
    .site-nav a.logo {{
      font-family: 'Playfair Display', serif; font-size: 18px;
      font-weight: 700; color: var(--dark); text-decoration: none;
    }}
    .site-nav a.back {{
      font-size: 13px; font-weight: 500; color: var(--muted);
      text-decoration: none; letter-spacing: 0.05em;
      transition: color 0.2s;
    }}
    .site-nav a.back:hover {{ color: var(--gold-dark); }}

    /* ── HERO IMAGE ── */
    .blog-hero {{
      width: 100%; max-height: 500px; overflow: hidden;
    }}
    .blog-hero-img {{
      width: 100%; height: 500px;
      object-fit: cover; object-position: center;
      display: block;
    }}

    /* ── ARTICLE ── */
    .article-wrap {{
      max-width: 780px; margin: 0 auto;
      padding: 3rem 2rem 5rem;
    }}

    /* ── LANG SWITCHER ── */
    .lang-switcher {{
      display: flex; gap: 8px; flex-wrap: wrap;
      margin-bottom: 2rem;
    }}
    .lang-switcher a {{
      font-size: 11px; font-weight: 500; letter-spacing: 0.08em;
      text-transform: uppercase; border: 1px solid var(--border);
      background: none; color: var(--mid); padding: 5px 12px;
      border-radius: 20px; text-decoration: none; transition: all 0.2s;
    }}
    .lang-switcher a:hover {{ border-color: var(--gold); color: var(--gold-dark); }}
    .lang-switcher a.active {{
      background: var(--gold); border-color: var(--gold); color: #fff;
    }}

    /* ── META ── */
    .article-meta {{
      display: flex; align-items: center; gap: 1rem;
      margin-bottom: 1.2rem;
    }}
    .meta-date {{
      font-size: 12px; font-weight: 500; letter-spacing: 0.1em;
      text-transform: uppercase; color: var(--muted);
    }}
    .meta-cat {{
      font-size: 11px; font-weight: 500; letter-spacing: 0.1em;
      text-transform: uppercase; background: var(--gold-light);
      color: var(--gold-dark); padding: 3px 10px; border-radius: 20px;
    }}

    /* ── TITLE ── */
    h1.article-title {{
      font-family: 'Playfair Display', serif;
      font-size: clamp(28px, 5vw, 46px);
      font-weight: 900; line-height: 1.15;
      color: var(--dark); margin-bottom: 1.2rem;
      letter-spacing: -0.02em;
    }}

    /* ── EXCERPT ── */
    .article-excerpt {{
      font-size: 18px; font-weight: 300; color: var(--mid);
      line-height: 1.75; margin-bottom: 2.5rem;
      padding-bottom: 2rem; border-bottom: 1px solid var(--border);
    }}

    /* ── BODY CONTENT ── */
    .article-body {{
      font-size: 17px; font-weight: 300; color: var(--mid);
      line-height: 1.9;
    }}
    .article-body h2 {{
      font-family: 'Playfair Display', serif;
      font-size: clamp(22px, 3vw, 30px); font-weight: 700;
      color: var(--dark); margin: 2.5rem 0 1rem;
      line-height: 1.2;
    }}
    .article-body h3 {{
      font-family: 'Playfair Display', serif;
      font-size: clamp(18px, 2.5vw, 24px); font-weight: 700;
      color: var(--dark); margin: 2rem 0 0.8rem;
    }}
    .article-body h4, .article-body h5, .article-body h6 {{
      font-family: 'Playfair Display', serif; font-weight: 700;
      color: var(--dark); margin: 1.5rem 0 0.6rem;
    }}
    .article-body p {{ margin-bottom: 1.4rem; }}
    .article-body a {{
      color: var(--gold-dark); text-decoration: underline;
      text-decoration-color: var(--gold-light);
      transition: color 0.2s;
    }}
    .article-body a:hover {{ color: var(--gold); }}
    .article-body strong {{ font-weight: 500; color: var(--dark); }}
    .article-body em {{ font-style: italic; }}
    .article-body ul, .article-body ol {{
      padding-left: 1.6rem; margin-bottom: 1.4rem;
    }}
    .article-body li {{ margin-bottom: 0.5rem; }}
    .article-body blockquote {{
      border-left: 3px solid var(--gold);
      padding: 0.8rem 1.5rem; margin: 2rem 0;
      background: var(--white); border-radius: 0 8px 8px 0;
      font-style: italic; color: var(--mid);
    }}
    .article-body hr {{
      border: none; border-top: 1px solid var(--border);
      margin: 2.5rem 0;
    }}
    .article-body code {{
      font-family: monospace; background: var(--cream);
      padding: 2px 6px; border-radius: 4px; font-size: 14px;
    }}

    /* ── CTA ── */
    .article-cta {{
      margin-top: 3.5rem; padding: 2.5rem;
      background: var(--dark); border-radius: 16px;
      text-align: center;
    }}
    .article-cta p {{
      font-size: 15px; font-weight: 300; color: #c0b8a8;
      margin-bottom: 1.5rem; line-height: 1.7;
    }}
    .article-cta a {{
      display: inline-flex; align-items: center; gap: 8px;
      background: var(--gold); color: #fff;
      padding: 14px 32px; border-radius: 50px;
      font-size: 15px; font-weight: 500;
      text-decoration: none; transition: all 0.25s;
      letter-spacing: 0.03em;
    }}
    .article-cta a:hover {{
      background: var(--gold-dark); transform: translateY(-2px);
    }}

    /* ── FOOTER ── */
    .site-footer {{
      background: var(--dark); color: #a09585;
      text-align: center; padding: 2rem;
      font-size: 13px;
    }}
    .site-footer a {{
      color: var(--gold); text-decoration: none;
    }}

    @media (max-width: 640px) {{
      .article-wrap {{ padding: 2rem 1.2rem 4rem; }}
      .blog-hero-img {{ height: 250px; }}
      .site-nav {{ padding: 0.8rem 1.2rem; }}
    }}
  </style>
</head>
<body>

  <nav class="site-nav">
    <a href="{home_url}" class="logo">Pianist.es</a>
    <a href="{blog_url}" class="back">{back_label}</a>
  </nav>

{thumb_html}

  <article class="article-wrap">

    <div class="lang-switcher">
      {lang_switch}
    </div>

    <div class="article-meta">
      <span class="meta-date">{date_str}</span>
      {f'<span class="meta-cat">{html_lib.escape(category)}</span>' if category else ""}
    </div>

    <h1 class="article-title">{html_lib.escape(title)}</h1>

    <p class="article-excerpt">{html_lib.escape(excerpt)}</p>

    <div class="article-body">
      {body_html}
    </div>

    <div class="article-cta">
      <p>Thomas Verheul — professioneel pianist voor bruiloften, diners en evenementen in Málaga, Marbella en heel Spanje.</p>
      <a href="{book_url}">{book_label}</a>
    </div>

  </article>

  <footer class="site-footer">
    <p>© 2025 <a href="{home_url}">Pianist.es</a> · Thomas Verheul · Málaga, España</p>
  </footer>

</body>
</html>
"""


# ── Blog index bijwerken ──────────────────────────────────────────────────────
def update_blog_index(entry):
    """Voeg een nieuwe post toe aan blog-index.json (of update bestaande)."""
    index = []
    if BLOG_INDEX.exists():
        index = json.loads(BLOG_INDEX.read_text(encoding="utf-8"))

    # Verwijder bestaande entry met dezelfde source_slug
    index = [e for e in index if e.get("source_slug") != entry["source_slug"]]
    index.append(entry)

    # Sorteer op datum (nieuwste eerst)
    index.sort(key=lambda e: e.get("date", ""), reverse=True)

    BLOG_INDEX.write_text(
        json.dumps(index, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )
    print(f"  ✅ blog-index.json bijgewerkt ({len(index)} posts)")


# ── Hoofdfunctie ──────────────────────────────────────────────────────────────
def main():
    print("🎹 pianist.es Blog Generator")
    print("════════════════════════════")

    # Haal posts op uit Contentful
    data = fetch_contentful()
    items = data.get("items", [])

    if not items:
        print("ℹ️  Geen gepubliceerde Nederlandse blogposts gevonden in Contentful.")
        return

    # Laad bestaande blog-index om te checken welke al verwerkt zijn
    existing_slugs = set()
    if BLOG_INDEX.exists():
        for entry in json.loads(BLOG_INDEX.read_text(encoding="utf-8")):
            existing_slugs.add(entry.get("source_slug", ""))

    processed = 0

    for item in items:
        fields = item.get("fields", {})

        title_nl      = fields.get("title", "").strip()
        slug_nl       = fields.get("slug", "").strip() or slugify(title_nl)
        excerpt_nl    = fields.get("excerpt", "").strip()
        category      = fields.get("category", "").strip()
        publish_date  = fields.get("publishDate", date.today().isoformat())
        body_field    = fields.get("body") or fields.get("content")  # beide veldnamen ondersteunen

        # FORCE_SLUG: verwerk alleen deze slug (voor handmatige re-run)
        if FORCE_SLUG and slug_nl != FORCE_SLUG:
            continue

        # Sla over als al verwerkt (tenzij force)
        if slug_nl in existing_slugs and not FORCE_SLUG:
            print(f"  ⏭️  '{slug_nl}' al verwerkt — overgeslagen")
            continue

        if not title_nl:
            print(f"  ⚠️  Post zonder titel overgeslagen")
            continue

        print(f"\n📝 Verwerken: '{title_nl}'")
        print(f"   Slug: {slug_nl}")

        # ── Thumbnail ophalen ──────────────────────────────────────────────────
        thumbnail_url = ""
        thumb_field = fields.get("thumbnail")
        if thumb_field:
            asset_id = thumb_field.get("sys", {}).get("id", "")
            if asset_id:
                thumbnail_url = get_asset_url(data, asset_id)
                if thumbnail_url:
                    print(f"   Thumbnail: {thumbnail_url}")
                else:
                    print(f"   ⚠️  Thumbnail asset niet gevonden in includes")

        # ── Rich text → HTML ───────────────────────────────────────────────────
        if isinstance(body_field, dict) and body_field.get("nodeType") == "document":
            body_html_nl = rich_text_to_html(body_field)
        elif isinstance(body_field, str):
            # Fallback: plain tekst in <p> tags
            body_html_nl = "\n".join(
                f"<p>{html_lib.escape(p.strip())}</p>"
                for p in body_field.split("\n\n") if p.strip()
            )
        else:
            body_html_nl = f"<p>{html_lib.escape(excerpt_nl)}</p>"

        # ── Vertalen naar 5 talen ──────────────────────────────────────────────
        target_langs = [l for l in LANGS if l != "nl"]
        print(f"   🌍 Vertalen naar: {', '.join(target_langs)}...")

        try:
            translations = translate_post(
                title_nl, excerpt_nl, body_html_nl, slug_nl, target_langs
            )
            print(f"   ✅ Vertaling gelukt")
        except Exception as e:
            print(f"   ❌ Vertaling mislukt: {type(e).__name__}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"   ❌ Response status: {e.response.status_code}")
                print(f"   ❌ Response body: {e.response.text}")
            print(f"   ℹ️  Post wordt alleen in het Nederlands gepubliceerd")
            translations = {}

        # Voeg Nederlandse versie toe
        all_versions = {
            "nl": {
                "title": title_nl,
                "excerpt": excerpt_nl,
                "body_html": body_html_nl,
                "slug": slug_nl,
            }
        }
        for lang, t in translations.items():
            if lang in LANGS:
                all_versions[lang] = t

        # Bouw slugs-dict voor hreflang en lang-switcher
        all_slugs = {lang: v.get("slug", slug_nl) for lang, v in all_versions.items()}

        # ── HTML pagina's schrijven ────────────────────────────────────────────
        index_entry = {
            "source_slug": slug_nl,
            "date": str(publish_date),
            "category": category,
            "thumbnail": thumbnail_url,
            "slugs": {},
            "titles": {},
            "excerpts": {},
            "urls": {},
        }

        for lang, version in all_versions.items():
            lang_data = LANGS[lang]
            prefix    = lang_data["prefix"]
            v_slug    = version.get("slug", slug_nl)
            v_title   = version.get("title", title_nl)
            v_excerpt = version.get("excerpt", excerpt_nl)
            v_body    = version.get("body_html", body_html_nl)

            # Bepaal uitvoerpad
            if prefix:
                out_dir = Path(prefix) / "blog" / v_slug
            else:
                out_dir = Path("blog") / v_slug
            out_dir.mkdir(parents=True, exist_ok=True)

            back_url = f"/{prefix}/" if prefix else "/"

            html_content = generate_html(
                lang=lang,
                slug=v_slug,
                title=v_title,
                excerpt=v_excerpt,
                body_html=v_body,
                thumbnail_url=thumbnail_url,
                category=category,
                publish_date=publish_date,
                all_slugs=all_slugs,
                back_url=back_url,
            )

            out_file = out_dir / "index.html"
            out_file.write_text(html_content, encoding="utf-8")

            url = f"{SITE_URL}/{prefix}/blog/{v_slug}/" if prefix else f"{SITE_URL}/blog/{v_slug}/"
            print(f"   ✅ {lang.upper()}: {out_file} → {url}")

            index_entry["slugs"][lang]   = v_slug
            index_entry["titles"][lang]  = v_title
            index_entry["excerpts"][lang] = v_excerpt
            index_entry["urls"][lang]    = url

        # ── Blog index bijwerken ───────────────────────────────────────────────
        update_blog_index(index_entry)

        # Sla post-titel op voor de git commit message
        Path("/tmp/new_post_title.txt").write_text(title_nl, encoding="utf-8")

        processed += 1

        # Kleine pauze tussen posts (rate limiting)
        if processed < len(items):
            time.sleep(1)

    if processed == 0:
        print("\nℹ️  Geen nieuwe posts om te verwerken.")
    else:
        print(f"\n🎉 Klaar! {processed} post(s) verwerkt in {len(all_versions)} talen.")


if __name__ == "__main__":
    main()
