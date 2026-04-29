#!/usr/bin/env python3
"""
update_sitemap.py
─────────────────
Scant de /blog/ map voor alle index.html bestanden en
genereert een volledige sitemap.xml met alle blog-URLs
plus de hoofd-URL van pianist.es.
"""

from pathlib import Path
from datetime import date
import re

SITE_URL  = "https://pianist.es"
BLOG_DIR  = Path("blog")
SITEMAP   = Path("sitemap.xml")

def get_blog_urls():
    urls = []
    for html_file in sorted(BLOG_DIR.glob("*/index.html")):
        slug = html_file.parent.name
        # Probeer datum uit de HTML te lezen
        content = html_file.read_text(encoding="utf-8")
        m = re.search(r'"datePublished"\s*:\s*"(\d{4}-\d{2}-\d{2})"', content)
        lastmod = m.group(1) if m else date.today().isoformat()
        urls.append({
            "loc":     f"{SITE_URL}/blog/{slug}/",
            "lastmod": lastmod,
            "priority": "0.7",
            "changefreq": "monthly",
        })
    return urls

def build_sitemap(urls):
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']

    # Hoofdpagina
    lines += [
        "  <url>",
        f"    <loc>{SITE_URL}/</loc>",
        f"    <lastmod>{date.today().isoformat()}</lastmod>",
        "    <changefreq>weekly</changefreq>",
        "    <priority>1.0</priority>",
        "  </url>",
    ]

    # Blog index
    lines += [
        "  <url>",
        f"    <loc>{SITE_URL}/#blog</loc>",
        f"    <lastmod>{date.today().isoformat()}</lastmod>",
        "    <changefreq>weekly</changefreq>",
        "    <priority>0.8</priority>",
        "  </url>",
    ]

    # Individuele blogposts
    for u in urls:
        lines += [
            "  <url>",
            f"    <loc>{u['loc']}</loc>",
            f"    <lastmod>{u['lastmod']}</lastmod>",
            f"    <changefreq>{u['changefreq']}</changefreq>",
            f"    <priority>{u['priority']}</priority>",
            "  </url>",
        ]

    lines.append("</urlset>")
    return "\n".join(lines)

def ping_google(sitemap_url):
    import urllib.request
    ping = f"https://www.google.com/ping?sitemap={sitemap_url}"
    try:
        urllib.request.urlopen(ping, timeout=10)
        print(f"📡 Google gepingd: {ping}")
    except Exception as e:
        print(f"⚠️ Google ping mislukt: {e}")

def main():
    blog_urls = get_blog_urls()
    sitemap_xml = build_sitemap(blog_urls)
    SITEMAP.write_text(sitemap_xml, encoding="utf-8")
    print(f"🗺️  Sitemap bijgewerkt: {len(blog_urls)} blog-URLs + 2 hoofd-URLs")

    # Google pingt alleen als er posts zijn
    if blog_urls:
        ping_google(f"{SITE_URL}/sitemap.xml")

if __name__ == "__main__":
    main()
