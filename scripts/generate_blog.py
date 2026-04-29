#!/usr/bin/env python3
"""
generate_blog.py — Meertalige Blog Generator voor pianist.es
══════════════════════════════════════════════════════════════
Voor elke blogpost worden 6 HTML-pagina's aangemaakt:

  pianist.es/blog/[slug]/           ← Spaans (standaard)
  pianist.es/en/blog/[slug]/        ← Engels
  pianist.es/nl/blog/[slug]/        ← Nederlands
  pianist.es/de/blog/[slug]/        ← Duits
  pianist.es/fr/blog/[slug]/        ← Frans
  pianist.es/ru/blog/[slug]/        ← Russisch
"""

import os, re, json, requests
from datetime import date, datetime
from pathlib import Path

CF_SPACE   = os.environ.get("CONTENTFUL_SPACE_ID", "")
CF_TOKEN   = os.environ.get("CONTENTFUL_ACCESS_TOKEN", "")
CF_MGMT    = os.environ.get("CONTENTFUL_MGMT_TOKEN", "")
CLAUDE_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FORCE_SLUG = os.environ.get("FORCE_SLUG", "").strip()
SITE_URL   = "https://pianist.es"
OUT_DIR    = Path(".")

LANGS = ["es", "en", "nl", "de", "fr", "ru"]
LANG_PREFIXES = {"es": "", "en": "en", "nl": "nl", "de": "de", "fr": "fr", "ru": "ru"}
LANG_NAMES    = {"es":"Español","en":"English","nl":"Nederlands","de":"Deutsch","fr":"Français","ru":"Русский"}
LANG_FLAGS    = {"es":"🇪🇸","en":"🇬🇧","nl":"🇳🇱","de":"🇩🇪","fr":"🇫🇷","ru":"🇷🇺"}

SITE_CONTEXT = """pianist.es is de website van Thomas Verheul, een professionele pianist die optreedt
bij bruiloften, bedrijfsevenementen, galadìners en privéfeesten in Málaga, Marbella,
de Costa del Sol en heel Spanje. Thomas heeft meer dan 20 jaar internationale ervaring,
woonde 4 jaar op Bali, spreekt Nederlands, Engels, Duits, Spaans en Indonesisch.
Hij brengt zijn eigen professionele digitale piano en geluidsset mee (geschikt voor 200 personen),
maar regelt ook een vleugel of staande piano op locatie. Zijn repertoire omvat jazz, klassiek, pop,
filmmuziek, bossa nova, blues, soul en bekende covers. Tarieven: €490 voor het eerste uur, €95
per extra uur. Reiskosten €0,50/km vanaf Málaga. Boeken via pianist.es of WhatsApp +34 711 226 882."""

LANG_COPY = {
    "es": {"back":"← Volver a pianist.es","cta_h":"¿Contratar a Thomas para tu evento?",
           "cta_p":"Pianista profesional · Málaga, Marbella & toda España · +34 711 226 882",
           "cta_btn":"Solicitar presupuesto gratuito →","cta_url":"/","by":"Por Thomas Verheul",
           "prompt":"Escribe en español correcto y fluido, con un tono cálido y profesional."},
    "en": {"back":"← Back to pianist.es","cta_h":"Book Thomas for your event?",
           "cta_p":"Professional pianist · Málaga, Marbella & all of Spain · +34 711 226 882",
           "cta_btn":"Request a free quote →","cta_url":"/en/","by":"By Thomas Verheul",
           "prompt":"Write in correct, fluent British English with a warm, professional tone."},
    "nl": {"back":"← Terug naar pianist.es","cta_h":"Thomas boeken voor jouw evenement?",
           "cta_p":"Professioneel pianist · Málaga, Marbella & heel Spanje · +34 711 226 882",
           "cta_btn":"Vrijblijvende offerte aanvragen →","cta_url":"/nl/","by":"Door Thomas Verheul",
           "prompt":"Schrijf in correct, vloeiend Nederlands met een warme, professionele toon."},
    "de": {"back":"← Zurück zu pianist.es","cta_h":"Thomas für Ihre Veranstaltung buchen?",
           "cta_p":"Professioneller Pianist · Málaga, Marbella & ganz Spanien · +34 711 226 882",
           "cta_btn":"Kostenloses Angebot anfragen →","cta_url":"/de/","by":"Von Thomas Verheul",
           "prompt":"Schreibe in korrektem, flüssigem Deutsch mit einem warmen, professionellen Ton."},
    "fr": {"back":"← Retour à pianist.es","cta_h":"Réserver Thomas pour votre événement ?",
           "cta_p":"Pianiste professionnel · Málaga, Marbella & toute l'Espagne · +34 711 226 882",
           "cta_btn":"Demander un devis gratuit →","cta_url":"/fr/","by":"Par Thomas Verheul",
           "prompt":"Écris en français correct et fluide avec un ton chaleureux et professionnel."},
    "ru": {"back":"← Вернуться на pianist.es","cta_h":"Забронировать Томаса для вашего мероприятия?",
           "cta_p":"Профессиональный пианист · Малага, Марбелья & вся Испания · +34 711 226 882",
           "cta_btn":"Запросить бесплатное предложение →","cta_url":"/ru/","by":"Автор: Томас Верхёль",
           "prompt":"Пиши на правильном, беглом русском языке с тёплым, профессиональным тоном."},
}

def cf_fetch(params):
    r = requests.get(f"https://cdn.contentful.com/spaces/{CF_SPACE}/entries",
                     params={"access_token": CF_TOKEN, **params}, timeout=30)
    r.raise_for_status()
    return r.json()

def get_next_post():
    params = {"content_type":"blogPost","fields.status":"planned","order":"fields.publishDate","limit":1}
    if FORCE_SLUG:
        params = {"content_type":"blogPost","fields.slug":FORCE_SLUG,"limit":1}
    data  = cf_fetch(params)
    items = data.get("items", [])
    if not items:
        print("Geen geplande posts gevonden.")
        exit(0)
    entry = items[0]
    f = entry["fields"]
    def field(key, default=""):
        v = f.get(key, default)
        if isinstance(v, dict):
            return v.get("nl") or v.get("en") or list(v.values())[0]
        return v or default
    return {"id":entry["sys"]["id"],"slug":field("slug"),"title":field("title"),
            "category":field("category","Blog"),"excerpt":field("excerpt",""),
            "date":field("publishDate", date.today().isoformat())}

def write_blog_in_lang(post, lang):
    c = LANG_COPY[lang]
    prompt = f"""Je schrijft een blogpost voor pianist.es van Thomas Verheul.

CONTEXT: {SITE_CONTEXT}

BLOGTITEL (vertaal naar {LANG_NAMES[lang]}): {post['title']}
CATEGORIE: {post['category']}

INSTRUCTIES:
- {c['prompt']}
- 850-1100 woorden
- SEO: gebruik de hoofdzoekterm 4-6x
- Structuur: inleiding, 3-5 <h2>-kopjes, conclusie met CTA naar pianist.es of WhatsApp +34 711 226 882
- Geef ALLEEN HTML-body content (<h2>, <p>, <ul> etc.)
- Begin direct met <p>

Schrijf nu:"""
    r = requests.post("https://api.anthropic.com/v1/messages",
        headers={"x-api-key":CLAUDE_KEY,"anthropic-version":"2023-06-01","content-type":"application/json"},
        json={"model":"claude-sonnet-4-20250514","max_tokens":2000,
              "messages":[{"role":"user","content":prompt}]}, timeout=120)
    r.raise_for_status()
    return r.json()["content"][0]["text"].strip()

def blog_url(lang, slug):
    p = LANG_PREFIXES[lang]
    return f"{SITE_URL}/{p}/blog/{slug}/" if p else f"{SITE_URL}/blog/{slug}/"

def blog_out_path(lang, slug):
    p = LANG_PREFIXES[lang]
    return OUT_DIR / p / "blog" / slug / "index.html" if p else OUT_DIR / "blog" / slug / "index.html"

def format_date(iso_str, lang):
    try:
        d = datetime.fromisoformat(iso_str[:10])
        months = {"nl":["jan","feb","mrt","apr","mei","jun","jul","aug","sep","okt","nov","dec"],
                  "en":["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"],
                  "es":["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"],
                  "de":["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"],
                  "fr":["jan","fév","mar","avr","mai","jun","jul","aoû","sep","oct","nov","déc"],
                  "ru":["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]}
        m = months.get(lang, months["en"])
        return f"{d.day} {m[d.month-1]} {d.year}"
    except:
        return iso_str

def build_hreflang(slug):
    lines = [f'  <link rel="alternate" hreflang="{lg}" href="{blog_url(lg, slug)}">' for lg in LANGS]
    lines.append(f'  <link rel="alternate" hreflang="x-default" href="{blog_url("es", slug)}">')
    return "\n".join(lines)

def build_lang_switcher(slug, current_lang):
    items = []
    for lang in LANGS:
        active = ' style="font-weight:700;color:var(--gold-dark);"' if lang == current_lang else ''
        items.append(f'<a href="{blog_url(lang, slug)}"{active}>{LANG_FLAGS[lang]} {LANG_NAMES[lang]}</a>')
    return " · ".join(items)

def build_html(post, lang, content_html, title_translated):
    c         = LANG_COPY[lang]
    slug      = post["slug"]
    canonical = blog_url(lang, slug)
    date_fmt  = format_date(post["date"], lang)
    hreflang  = build_hreflang(slug)
    lang_sw   = build_lang_switcher(slug, lang)
    clean     = re.sub(r'<[^>]+>', '', content_html)
    meta_desc = clean[:157].rstrip() + "…"
    schema    = json.dumps({"@context":"https://schema.org","@type":"BlogPosting",
        "headline":title_translated,"datePublished":post["date"][:10],
        "inLanguage":lang,"author":{"@type":"Person","name":"Thomas Verheul","url":SITE_URL},
        "publisher":{"@type":"Organization","name":"pianist.es","url":SITE_URL},
        "url":canonical,"description":meta_desc}, ensure_ascii=False, indent=2)

    return f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title_translated} | pianist.es</title>
<meta name="description" content="{meta_desc}">
<link rel="canonical" href="{canonical}">
{hreflang}
<meta property="og:title" content="{title_translated}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="article">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE_URL}/assets/thomas-hero.jpg">
<script async src="https://www.googletagmanager.com/gtag/js?id=G-W87PC5M8NT"></script>
<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}gtag('js',new Date());gtag('config','G-W87PC5M8NT');</script>
<script type="application/ld+json">
{schema}
</script>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,700;0,900;1,400&family=DM+Sans:wght@300;400;500&display=swap" rel="stylesheet">
<style>
:root{{--gold:#c9a96e;--gold-dark:#a07840;--cream:#faf8f3;--dark:#1c1a16;--mid:#4a4540;--muted:#8a8070;--border:#e8e0d0;}}
*{{box-sizing:border-box;margin:0;padding:0;}}
body{{font-family:'DM Sans',sans-serif;background:var(--cream);color:var(--mid);line-height:1.7;}}
.top-bar{{background:var(--dark);padding:14px 2.5rem;display:flex;align-items:center;justify-content:space-between;gap:1rem;position:sticky;top:0;z-index:100;}}
.top-bar a.back{{color:var(--gold);text-decoration:none;font-size:13px;font-weight:500;}}
.top-bar a.back:hover{{color:#fff;}}
.top-logo{{font-family:'Playfair Display',serif;color:#fff;font-size:17px;font-weight:700;text-decoration:none;}}
.lang-sw{{font-size:11px;display:flex;flex-wrap:wrap;gap:6px;}}
.lang-sw a{{color:rgba(255,255,255,.5);text-decoration:none;font-size:12px;transition:color .2s;}}
.lang-sw a:hover{{color:var(--gold);}}
article{{max-width:760px;margin:0 auto;padding:4rem 2rem 6rem;}}
.eyebrow{{font-size:11px;font-weight:600;letter-spacing:.18em;text-transform:uppercase;color:var(--gold-dark);display:flex;align-items:center;gap:10px;margin-bottom:1rem;}}
.eyebrow::before{{content:'';width:24px;height:1px;background:var(--gold);}}
h1{{font-family:'Playfair Display',serif;font-size:clamp(28px,4.5vw,48px);font-weight:900;color:var(--dark);line-height:1.1;letter-spacing:-.02em;margin-bottom:.8rem;}}
.meta{{font-size:13px;color:var(--muted);margin-bottom:2.5rem;padding-bottom:1.5rem;border-bottom:1px solid var(--border);}}
.content h2{{font-family:'Playfair Display',serif;font-size:clamp(20px,2.5vw,26px);font-weight:700;color:var(--dark);margin:2.5rem 0 .8rem;}}
.content h3{{font-family:'Playfair Display',serif;font-size:20px;font-weight:700;color:var(--dark);margin:1.8rem 0 .6rem;}}
.content p{{margin-bottom:1.25rem;font-size:16px;font-weight:300;}}
.content strong{{color:var(--dark);font-weight:500;}}
.content ul{{margin:1rem 0 1.25rem 1.5rem;}}
.content ul li{{margin-bottom:.5rem;font-size:16px;font-weight:300;}}
.content a{{color:var(--gold-dark);text-decoration:underline;}}
.cta{{background:var(--dark);border-radius:16px;padding:2.5rem 2rem;margin-top:3.5rem;text-align:center;}}
.cta h3{{font-family:'Playfair Display',serif;font-size:22px;color:#fff;margin-bottom:.6rem;}}
.cta p{{color:#a09585;font-size:14px;margin-bottom:1.5rem;font-weight:300;}}
.cta-btn{{display:inline-block;background:var(--gold);color:#fff;padding:13px 28px;border-radius:50px;font-size:14px;font-weight:500;text-decoration:none;transition:background .2s;}}
.cta-btn:hover{{background:var(--gold-dark);}}
footer{{background:#111;color:#555;text-align:center;padding:2rem;font-size:12px;}}
footer a{{color:var(--gold);text-decoration:none;}}
@media(max-width:640px){{article{{padding:2rem 1.2rem 4rem;}}.top-bar{{flex-wrap:wrap;padding:12px 1.2rem;}}.lang-sw{{display:none;}}}}
</style>
</head>
<body>
<div class="top-bar">
  <a href="{c['cta_url']}" class="back">{c['back']}</a>
  <a href="{SITE_URL}" class="top-logo">pianist.es</a>
  <div class="lang-sw">{lang_sw}</div>
</div>
<article>
  <div class="eyebrow">{post['category']}</div>
  <h1>{title_translated}</h1>
  <div class="meta">{c['by']} · {date_fmt}</div>
  <div class="content">{content_html}</div>
  <div class="cta">
    <h3>{c['cta_h']}</h3>
    <p>{c['cta_p']}</p>
    <a href="{SITE_URL}{c['cta_url']}#offerte" class="cta-btn">{c['cta_btn']}</a>
  </div>
</article>
<footer><p>© 2025 <a href="{SITE_URL}">pianist.es</a> · Thomas Verheul · Málaga, España</p></footer>
</body>
</html>"""

def update_blog_index(post, titles):
    index_path = OUT_DIR / "blog-index.json"
    try:
        index = json.loads(index_path.read_text()) if index_path.exists() else []
    except:
        index = []
    entry = {"slug":post["slug"],"date":post["date"][:10],"category":post["category"],
             "titles":titles,"urls":{lg:blog_url(lg,post["slug"]) for lg in LANGS}}
    existing = next((i for i,e in enumerate(index) if e["slug"]==post["slug"]), None)
    if existing is not None:
        index[existing] = entry
    else:
        index.insert(0, entry)
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2))
    print(f"  ✅ blog-index.json ({len(index)} posts)")

def mark_published(entry_id):
    if not CF_MGMT:
        return
    r = requests.get(
        f"https://api.contentful.com/spaces/{CF_SPACE}/environments/master/entries/{entry_id}",
        headers={"Authorization":f"Bearer {CF_MGMT}"})
    if not r.ok:
        return
    version = r.json()["sys"]["version"]
    requests.patch(
        f"https://api.contentful.com/spaces/{CF_SPACE}/environments/master/entries/{entry_id}",
        headers={"Authorization":f"Bearer {CF_MGMT}",
                 "Content-Type":"application/vnd.contentful.management.v1+json",
                 "X-Contentful-Version":str(version)},
        json={"fields":{"status":{"nl":"published","en":"published"}}})

def main():
    print("🎹 Meertalige Blog Generator — pianist.es\n")
    post = get_next_post()
    print(f"📝 '{post['title']}' (slug: {post['slug']})\n")

    contents, titles = {}, {}
    for lang in LANGS:
        print(f"  🤖 {lang.upper()}...", end=" ", flush=True)
        content_html = write_blog_in_lang(post, lang)
        m = re.search(r'<h1[^>]*>(.*?)</h1>', content_html, re.DOTALL)
        title_lang = re.sub(r'<[^>]+>', '', m.group(1)).strip() if m else post["title"]
        contents[lang] = content_html
        titles[lang]   = title_lang
        print(f"✅ '{title_lang[:50]}...'")

    print()
    for lang in LANGS:
        out = blog_out_path(lang, post["slug"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_html(post, lang, contents[lang], titles[lang]), encoding="utf-8")
        print(f"  📄 {blog_url(lang, post['slug'])}")

    print()
    update_blog_index(post, titles)
    mark_published(post["id"])
    Path("/tmp/new_post_title.txt").write_text(titles.get("nl") or titles.get("en") or post["title"])
    print(f"\n🎉 Klaar! 6 pagina's aangemaakt.")

if __name__ == "__main__":
    main()
