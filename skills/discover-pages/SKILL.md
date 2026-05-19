---
name: discover-pages
description: Crawl a domain's sitemaps and homepage to discover and classify all pages into blogs, categories, products, and other. First phase of internal linking analysis.
when_to_use: Use at the start of any domain analysis to build a complete URL inventory. Invoked by /analyze-domain or independently when user needs to understand a site's page structure.
argument-hint: [domain-url]
---

# Site Discovery and Page Classification

Discover and classify all pages on **$ARGUMENTS**.

## Workflow

### 1. Fetch the homepage

Use `WebFetch` on the domain's root URL. Extract:
- All main navigation links with full URLs
- Footer navigation links with full URLs
- CMS/platform indicators (Shopify: `/collections/`, `/products/`; WordPress: `/wp-content/`, `/category/`; custom: varies)

Record the URL patterns you observe for:
- **Blog/article pages** (e.g., `/blog/`, `/articles/`, `/news/`, `/insights/`, `/resources/`)
- **Category pages** (e.g., `/collections/`, `/category/`, `/product-category/`, or custom patterns)
- **Product pages** (e.g., `/products/`, `/product/`, `/p/`, or nested under categories)

### 2. Fetch the sitemap

Use `WebFetch` on `{domain}/sitemap.xml`. If it is a sitemap index, identify the child sitemaps and fetch each one. Common WordPress sitemaps:
- `post-sitemap.xml` — blog posts
- `page-sitemap.xml` — static pages
- Category-specific sitemaps (e.g., `automotivebatteries-sitemap.xml`)

Extract all URLs from each sitemap.

### 3. Classify URLs

Assign every discovered URL to one of these categories:

| Type | Description | Examples |
|------|-------------|---------|
| **Blog** | Editorial content, articles, how-to guides | `/blog/how-to-choose-battery/` |
| **Category** | Collection or listing pages | `/automotive-batteries/`, `/solar-solutions/` |
| **Product** | Individual product detail pages | `/automotive-batteries/car-batteries/model-x/` |
| **Utility** | About, contact, warranty, dealer locator | `/about-us`, `/contact-us` |
| **Other** | Anything that doesn't fit above | Author pages, tag archives |

Classification rules:
- Use the URL patterns discovered in Step 1 as the primary signal
- Pages with more than 2 path segments under a category pattern are likely products
- Pages from `post-sitemap.xml` are blogs
- When ambiguous, use WebFetch to check the page and determine its type

### 4. Output

Present the classified URL inventory as a structured summary:

```
SITE DISCOVERY: {domain}
Platform: {detected CMS}
Blog pattern: {pattern}
Category pattern: {pattern}
Product pattern: {pattern}

BLOGS ({count}):
- {url_1}
- {url_2}
...

CATEGORIES ({count}):
- {url_1}
- {url_2}
...

PRODUCTS ({count}):
- {url_1}
- {url_2}
...

UTILITY ({count}):
- {url_1}
...
```

Retain this data in conversation context for the next phases.

## Guardrails

- Do NOT fetch every page on the site — only the homepage, sitemaps, and a few sample pages for ambiguous classification
- If the sitemap is missing or empty, fall back to WebSearch: `site:{domain}` to discover pages
- If a sitemap has more than 500 URLs, report the count but only list the first 100 per category; note the remainder as "and {N} more"
- Exclude obvious non-content URLs: `wp-admin`, `wp-login`, `feed/`, `?s=`, `/tag/`, `/author/`
- Pages under `/tag/` or `/author/` go to "Other" — they are not analysis targets
