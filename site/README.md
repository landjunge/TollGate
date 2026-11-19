# Tollgate product website

Static product landing (ops desk aesthetic) for GitHub Pages.

**Live:** https://landjunge.github.io/TollGate/

## SEO / Google indexing

| Item | Location |
|------|----------|
| Title, description, keywords | `index.html`, `de.html`, `docs.html` |
| robots `index,follow` + large previews | head meta |
| Canonical + hreflang EN/DE | head links |
| Open Graph + Twitter Card | head meta · image `assets/og.png` (1200×630) |
| JSON-LD `SoftwareApplication` | index |
| JSON-LD `FAQPage` | index + de |
| JSON-LD `WebSite` / `CollectionPage` | index / docs |
| `robots.txt` + `sitemap.xml` (hreflang + images) | site root |
| Semantic HTML | main, section, article, nav |

### Google Search Console

1. Property: `https://landjunge.github.io/TollGate/`
2. Submit sitemap: `https://landjunge.github.io/TollGate/sitemap.xml`
3. Request indexing for `/` and `/de.html`

## Local preview

```bash
cd site && python3 -m http.server 8080
```

## Deploy

Push to `main` → workflow Pages (`.github/workflows/pages.yml`).
