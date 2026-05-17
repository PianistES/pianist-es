#!/usr/bin/env python3
"""
build.py — pianist.es Meertalige Site Builder
═══════════════════════════════════════════════
Genereert vanuit index.html (master template) aparte HTML-bestanden
voor elke taal met correcte URLs, hreflang-tags, canonical URLs,
taalspecifieke <title> en <meta description>.

URL-structuur:
  Spaans (default): pianist.es/              → index.html
  Engels:           pianist.es/en/           → en/index.html
  Nederlands:       pianist.es/nl/           → nl/index.html
  Duits:            pianist.es/de/           → de/index.html
  Frans:            pianist.es/fr/           → fr/index.html
  Russisch:         pianist.es/ru/           → ru/index.html

Gebruik:
  python build.py
"""

import re
from pathlib import Path

# ── Config ────────────────────────────────────────────────────────────────────
SOURCE   = Path("index.html")   # master template
OUT_DIR  = Path(".")            # root van je repo
SITE_URL = "https://pianist.es"

LANGS = {
    # code: (url_prefix, html_lang, flag, label)
    "es": ("",    "es", "🇪🇸", "Español"),
    "en": ("en",  "en", "🇬🇧", "English"),
    "nl": ("nl",  "nl", "🇳🇱", "Nederlands"),
    "de": ("de",  "de", "🇩🇪", "Deutsch"),
    "fr": ("fr",  "fr", "🇫🇷", "Français"),
    "ru": ("ru",  "ru", "🇷🇺", "Русский"),
}

# Taalspecifieke <title> en <meta description>
META = {
    "es": {
        "title": "Contratar Pianista para Bodas, Fiestas y Eventos en Málaga, Marbella y toda España | Thomas Verheul",
        "desc":  "Pianista profesional Thomas Verheul en Málaga, Marbella y toda España. ✓ 20+ años de experiencia ✓ Bodas, eventos corporativos, cenas ✓ Piano propio y sistema de sonido ✓ Presupuesto sin compromiso",
        "og_title": "Pianista Thomas Verheul – Málaga, Marbella & España",
        "og_desc":  "Música de piano en vivo para cualquier evento. Más de 20 años de experiencia internacional. Reserva directamente por WhatsApp.",
    },
    "en": {
        "title": "Book a Pianist for Weddings, Events & Parties in Málaga, Marbella & Spain | Thomas Verheul",
        "desc":  "Professional pianist Thomas Verheul in Málaga, Marbella & all of Spain. ✓ 20+ years experience ✓ Weddings, corporate events, dinners ✓ Own piano & sound system ✓ Free quote",
        "og_title": "Pianist Thomas Verheul – Málaga, Marbella & Spain",
        "og_desc":  "Live piano music for any event. 20+ years of international experience. Book directly via WhatsApp.",
    },
    "nl": {
        "title": "Pianist boeken voor bruiloft, feest en evenement in Málaga, Marbella en heel Spanje | Thomas Verheul",
        "desc":  "Professionele pianist Thomas Verheul in Málaga, Marbella & heel Spanje. ✓ 20+ jaar ervaring ✓ Bruiloften, bedrijfsfeesten, diners ✓ Eigen piano & geluidssysteem ✓ Vrijblijvende offerte",
        "og_title": "Pianist Thomas Verheul – Málaga, Marbella & Spanje",
        "og_desc":  "Live pianomuziek voor elk evenement. 20+ jaar internationale ervaring. Boek direct via WhatsApp.",
    },
    "de": {
        "title": "Pianist buchen für Hochzeit, Feier und Event in Málaga, Marbella & ganz Spanien | Thomas Verheul",
        "desc":  "Professioneller Pianist Thomas Verheul in Málaga, Marbella & ganz Spanien. ✓ 20+ Jahre Erfahrung ✓ Hochzeiten, Firmenevents, Dinner ✓ Eigenes Klavier & Soundsystem ✓ Kostenloses Angebot",
        "og_title": "Pianist Thomas Verheul – Málaga, Marbella & Spanien",
        "og_desc":  "Live-Klaviermusik für jedes Event. 20+ Jahre internationale Erfahrung. Direkt per WhatsApp buchen.",
    },
    "fr": {
        "title": "Réserver un Pianiste pour Mariage, Fête et Événement à Málaga, Marbella et toute l'Espagne | Thomas Verheul",
        "desc":  "Pianiste professionnel Thomas Verheul à Málaga, Marbella & toute l'Espagne. ✓ 20+ ans d'expérience ✓ Mariages, événements d'entreprise, dîners ✓ Piano & système son propres ✓ Devis gratuit",
        "og_title": "Pianiste Thomas Verheul – Málaga, Marbella & Espagne",
        "og_desc":  "Musique de piano en direct pour tout événement. Plus de 20 ans d'expérience internationale. Réservez directement via WhatsApp.",
    },
    "ru": {
        "title": "Нанять пианиста для свадьбы, праздника и мероприятия в Малаге, Марбелье и по всей Испании | Томас Верхёль",
        "desc":  "Профессиональный пианист Томас Верхёль в Малаге, Марбелье и по всей Испании. ✓ 20+ лет опыта ✓ Свадьбы, корпоративы, ужины ✓ Собственное фортепиано и звуковая система ✓ Бесплатное предложение",
        "og_title": "Пианист Томас Верхёль – Малага, Марбелья & Испания",
        "og_desc":  "Живая музыка фортепиано для любого мероприятия. 20+ лет международного опыта. Бронируйте прямо через WhatsApp.",
    },
}

# Schema.org LocalBusiness per taal
SCHEMA = {
    "es": "Pianista profesional para bodas, fiestas y eventos en Málaga, Marbella y toda España",
    "en": "Professional pianist for weddings, parties and events in Málaga, Marbella and all of Spain",
    "nl": "Professionele pianist voor bruiloften, feesten en evenementen in Málaga, Marbella en heel Spanje",
    "de": "Professioneller Pianist für Hochzeiten, Feiern und Events in Málaga, Marbella und ganz Spanien",
    "fr": "Pianiste professionnel pour mariages, fêtes et événements à Málaga, Marbella et toute l'Espagne",
    "ru": "Профессиональный пианист для свадеб, вечеринок и мероприятий в Малаге, Марбелье и по всей Испании",
}

def get_canonical(lang_code):
    prefix = LANGS[lang_code][0]
    return f"{SITE_URL}/{prefix}/" if prefix else f"{SITE_URL}/"

def build_hreflang_tags():
    lines = []
    for code, (prefix, html_lang, flag, label) in LANGS.items():
        url = f"{SITE_URL}/{prefix}/" if prefix else f"{SITE_URL}/"
        lines.append(f'<link rel="alternate" hreflang="{html_lang}" href="{url}">')
    # x-default → Spaans (standaard)
    lines.append(f'<link rel="alternate" hreflang="x-default" href="{SITE_URL}/">')
    return "\n".join(lines)

def build_schema(lang_code, canonical):
    desc = SCHEMA.get(lang_code, SCHEMA["en"])
    return f'''<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "LocalBusiness",
  "name": "Pianist.es - Pianist booking in Malaga, Marbella & Spain",
  "description": "{desc}",
  "url": "{canonical}",
  "telephone": "+34711226882",
  "email": "info@pianist.es",
  "address": {{ "@type": "PostalAddress", "addressLocality": "Málaga", "addressCountry": "ES" }},
  "geo": {{ "@type": "GeoCoordinates", "latitude": 36.7213, "longitude": -4.4214 }},
  "areaServed": ["Málaga","Marbella","Granada","Sevilla","Madrid","España"],
  "priceRange": "€€",
  "sameAs": ["https://wa.me/34711226882"]
}}
</script>'''

def patch_head(html: str, lang_code: str) -> str:
    """Vervang title, meta description, og-tags, canonical, hreflang en schema."""
    prefix, html_lang, *_ = LANGS[lang_code]
    canonical  = get_canonical(lang_code)
    meta       = META[lang_code]
    hreflang   = build_hreflang_tags()
    schema     = build_schema(lang_code, canonical)

    # html lang attribuut
    html = re.sub(r'<html\s+lang="[^"]*"', f'<html lang="{html_lang}"', html)

    # <title>
    html = re.sub(r'<title>.*?</title>', f'<title>{meta["title"]}</title>', html, flags=re.DOTALL)

    # meta description
    html = re.sub(
        r'<meta\s+name="description"\s+content="[^"]*">',
        f'<meta name="description" content="{meta["desc"]}">',
        html
    )

    # og:title
    html = re.sub(
        r'<meta\s+property="og:title"\s+content="[^"]*">',
        f'<meta property="og:title" content="{meta["og_title"]}">',
        html
    )

    # og:description
    html = re.sub(
        r'<meta\s+property="og:description"\s+content="[^"]*">',
        f'<meta property="og:description" content="{meta["og_desc"]}">',
        html
    )

    # og:url
    html = re.sub(
        r'<meta\s+property="og:url"\s+content="[^"]*">',
        f'<meta property="og:url" content="{canonical}">',
        html
    )

    # canonical
    html = re.sub(
        r'<link\s+rel="canonical"\s+href="[^"]*">',
        f'<link rel="canonical" href="{canonical}">\n{hreflang}',
        html
    )

    # Vervang bestaand schema
    html = re.sub(
        r'<script\s+type="application/ld\+json">.*?</script>',
        schema,
        html,
        count=1,
        flags=re.DOTALL
    )

    return html

def patch_nav_links(html: str, lang_code: str) -> str:
    """
    Pas alle anchor-hrefs aan zodat ze correct zijn voor de taalmap.
    - Interne anchors (#about, #videos etc) blijven zoals ze zijn.
    - Taalwissel-knoppen worden bijgewerkt naar de juiste URLs.
    - Logo-link wordt bijgewerkt.
    """
    prefix = LANGS[lang_code][0]
    root   = f"/{prefix}/" if prefix else "/"

    # Logo href → root van deze taal
    html = re.sub(
        r'(<a\s+href=")#("\s+class="nav-logo")',
        f'\\1{root}\\2',
        html
    )

    # Taalwissel: vervang onclick="setLang('xx')" door navigatie naar taalURL
    def lang_switch_href(code):
        p = LANGS[code][0]
        return f"/{p}/" if p else "/"

    # Update de taalknop onclick naar window.location
    for code in LANGS:
        target = lang_switch_href(code)
        html = html.replace(
            f"onclick=\"setLang('{code}')\"",
            f"onclick=\"window.location.href='{target}'\""
        )
        html = html.replace(
            f"onclick=\"setLang('{code}'); toggleLangMenu()\"",
            f"onclick=\"window.location.href='{target}'\""
        )
        html = html.replace(
            f"onclick=\"setLang('{code}'); toggleLangMenu(event)\"",
            f"onclick=\"window.location.href='{target}'\""
        )

    # Blog-links: #blog → /LANG/blog/ of /blog/ voor ES
    blog_url = f"/{prefix}/blog/" if prefix else "/blog/"

    # Vervang setLang JavaScript call in de taalwissel-knoppen van de dropdown
    return html

def patch_initial_language(html: str, lang_code: str) -> str:
    """
    Zorg dat de juiste taal actief is als standaard:
    - data-lang="LANG" elements krijgen class="active"
    - alle andere data-lang elements verliezen class="active"
    """
    # Verwijder eerst alle bestaande 'active' classes van data-lang elementen
    html = re.sub(
        r'(<(?:span|div|a|li|p|h[1-6]|button)[^>]*data-lang="[^"]*"[^>]*)\s+class="active"',
        r'\1',
        html
    )
    html = re.sub(
        r'(<(?:span|div|a|li|p|h[1-6]|button)[^>]*)\s+class="active"([^>]*data-lang="[^"]*")',
        r'\1\2',
        html
    )

    # Voeg 'active' toe aan elementen met data-lang="LANG_CODE"
    html = re.sub(
        rf'(<(?:span|div|a|li|p|h[1-6]|button)[^>]*data-lang="{lang_code}")',
        r'\1 class="active"',
        html
    )

    return html

def patch_js_language(html: str, lang_code: str) -> str:
    """Zet de standaard taal in de JavaScript."""
    html = html.replace(
        "let currentLang = 'nl';",
        f"let currentLang = '{lang_code}';"
    )
    html = html.replace(
        "let currentLang = 'es';",
        f"let currentLang = '{lang_code}';"
    )
    html = html.replace(
        "let currentLang = 'en';",
        f"let currentLang = '{lang_code}';"
    )
    return html

def patch_lang_flag(html: str, lang_code: str) -> str:
    """Update de initiële vlag en code in de taalknop."""
    _, _, flag, _ = LANGS[lang_code]
    codes = {"es":"ES", "en":"EN", "nl":"NL", "de":"DE", "fr":"FR", "ru":"RU"}
    code_label = codes[lang_code]

    html = re.sub(
        r'(<span id="langCurrentFlag">)[^<]*(</span>)',
        f'\\1{flag}\\2',
        html
    )
    html = re.sub(
        r'(<span id="langCurrentCode">)[^<]*(</span>)',
        f'\\1{code_label}\\2',
        html
    )
    return html

def build_language_page(source_html: str, lang_code: str) -> str:
    html = source_html
    html = patch_head(html, lang_code)
    html = patch_initial_language(html, lang_code)
    html = patch_js_language(html, lang_code)
    html = patch_lang_flag(html, lang_code)
    html = patch_nav_links(html, lang_code)
    return html

def write_page(html: str, lang_code: str):
    prefix = LANGS[lang_code][0]
    if prefix:
        out_dir = OUT_DIR / prefix
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / "index.html"
    else:
        out_path = OUT_DIR / "index.html"

    out_path.write_text(html, encoding="utf-8")
    url = f"{SITE_URL}/{prefix}/" if prefix else f"{SITE_URL}/"
    print(f"  ✅ {lang_code.upper()}: {out_path} → {url}")

def build_all():
    print("🎹 pianist.es Build Script")
    print("══════════════════════════")

    source_html = SOURCE.read_text(encoding="utf-8")
    print(f"📄 Template: {SOURCE} ({len(source_html):,} bytes)")
    print()

    for lang_code in LANGS:
        html = build_language_page(source_html, lang_code)
        write_page(html, lang_code)

    print()
    print("🗺️  Sitemap genereren...")
    build_sitemap()
    print("✅ Klaar! Alle taalpagina's gegenereerd.")

def build_sitemap():
    from datetime import date
    today = date.today().isoformat()

    urls = []
    # Hoofd taalpagins
    for lang_code, (prefix, html_lang, *_) in LANGS.items():
        url  = f"{SITE_URL}/{prefix}/" if prefix else f"{SITE_URL}/"
        prio = "1.0" if lang_code == "es" else "0.9"
        urls.append(f"""  <url>
    <loc>{url}</loc>
    <lastmod>{today}</lastmod>
    <changefreq>weekly</changefreq>
    <priority>{prio}</priority>
    <xhtml:link rel="alternate" hreflang="x-default" href="{SITE_URL}/"/>
  </url>""")

    # Bestaande blog-URLs toevoegen
    for lang_code, (prefix, *_) in LANGS.items():
        blog_base = f"{SITE_URL}/{prefix}/blog" if prefix else f"{SITE_URL}/blog"
        blog_dir  = OUT_DIR / prefix / "blog" if prefix else OUT_DIR / "blog"
        if blog_dir.exists():
            for post_dir in sorted(blog_dir.iterdir()):
                if (post_dir / "index.html").exists():
                    urls.append(f"""  <url>
    <loc>{blog_base}/{post_dir.name}/</loc>
    <lastmod>{today}</lastmod>
    <changefreq>monthly</changefreq>
    <priority>0.7</priority>
  </url>""")

    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset
  xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"
  xmlns:xhtml="http://www.w3.org/1999/xhtml">
{chr(10).join(urls)}
</urlset>"""

    sitemap_path = OUT_DIR / "sitemap.xml"
    sitemap_path.write_text(sitemap, encoding="utf-8")
    print(f"  ✅ sitemap.xml ({len(urls)} URLs)")

if __name__ == "__main__":
    build_all()
