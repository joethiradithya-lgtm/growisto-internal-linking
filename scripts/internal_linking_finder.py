#!/usr/bin/env python3
"""
Internal Linking Opportunity Finder
====================================
Crawls a domain to find internal linking opportunities between blog posts /
category footer content and commercial (category/product) pages.

Usage:
    python3 scripts/internal_linking_finder.py [domain] [options]

Examples:
    # Full site scan — analyse all category pages
    python3 scripts/internal_linking_finder.py https://www.livfast.in

    # Single target — script asks whether to search all keywords or a specific one
    python3 scripts/internal_linking_finder.py https://www.livfast.in \\
        --target https://www.livfast.in/automotive-batteries/car-batteries/

    # Single target + specific keyword (skips the interactive prompt)
    python3 scripts/internal_linking_finder.py https://www.livfast.in \\
        --target https://www.livfast.in/automotive-batteries/car-batteries/ \\
        --keyword "car batteries"

    python3 scripts/internal_linking_finder.py https://www.livfast.in --max-blogs 20
    python3 scripts/internal_linking_finder.py https://www.livfast.in --delay 2.0

Output:
    output/{domain}-internal-linking-{date}.csv
    output/{domain}-{target-slug}-{date}.csv            (--target mode, all keywords)
    output/{domain}-{target-slug}-{keyword-slug}-{date}.csv  (--target + --keyword)
"""

import argparse
import csv
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import date
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

# ── Constants ────────────────────────────────────────────────────────────────

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

DEFAULT_DELAY = 1.0   # seconds between requests
MAX_LINKS_PER_PAGE = 2

STOP_WORDS = {
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "our",
    "get", "has", "its", "let", "use", "with", "that", "this", "from",
    "they", "will", "your", "what", "when", "make", "like", "time", "into",
    "also", "more", "than", "only", "here", "just", "very", "well", "been",
    "does", "each", "much", "same", "some", "them", "then", "these", "those",
    "best", "top", "buy", "online", "india", "price", "shop", "find", "wide",
    "range", "high", "quality", "available", "know", "need", "now", "new",
    "right", "help", "way", "day", "take", "over", "such", "good", "great",
}

SKIP_NAV_PATTERNS = [
    "warranty", "dealer", "contact", "about", "career", "privacy",
    "terms", "blog", "press", "battery-finder", "bmhr", "sitemap",
    "author", "tag", "page", "feed", "login", "register",
]

# URL path segments that are CMS structural prefixes, not topic keywords.
# Shopify uses /collections/ and /products/; WordPress uses /blog/, /category/ etc.
SKIP_SLUG_SEGMENTS = {
    "collections", "products", "product", "blogs", "blog", "news",
    "pages", "page", "categories", "category", "articles", "article",
    "posts", "post", "shop", "store", "all",
}

GENERIC_HEADING_PATTERNS = [
    r"^why (choose|us|livfast)",
    r"^about (us|livfast|the)",
    r"^contact",
    r"^home$",
    r"^(our )?(products?|services?|solutions?)$",
    r"^features?$",
    r"^benefits?$",
    r"^specifications?$",
    r"^faq",
    r"^related",
    r"^let us help",
    r"^buy .+ today",
    r"^find the right",
    r"superior hai toh hai",
    r"delivers more",
    r"we('re| are) here",
    r"^explore",
    r"^discover",
    r"powered by",
]


# ── HTTP helpers ─────────────────────────────────────────────────────────────

def fetch(url, timeout=15):
    """GET a URL. Returns requests.Response or None on failure."""
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        r.raise_for_status()
        return r
    except Exception as e:
        print(f"  [WARN] {url} — {e}")
        return None


# ── Sitemap parsing ──────────────────────────────────────────────────────────

def parse_sitemap(url, visited=None):
    """Recursively parse a sitemap or sitemap index. Returns list of page URLs."""
    if visited is None:
        visited = set()
    if url in visited:
        return []
    visited.add(url)

    r = fetch(url)
    if not r:
        return []

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError as e:
        print(f"  [WARN] XML parse error for {url}: {e}")
        return []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}

    # Sitemap index?
    children = root.findall(".//sm:sitemap/sm:loc", ns)
    if children:
        urls = []
        for child in children:
            time.sleep(0.3)
            urls.extend(parse_sitemap(child.text.strip(), visited))
        return urls

    return [loc.text.strip() for loc in root.findall(".//sm:url/sm:loc", ns)]


# ── Page discovery ───────────────────────────────────────────────────────────

def _discover_blog_urls(domain):
    """
    Find blog/article URLs for any CMS platform.

    Strategy:
    1. Try WordPress /post-sitemap.xml directly.
    2. Try /sitemap.xml — if it's a sitemap index, filter child sitemaps
       whose name contains 'blog' or 'article', then parse those.
    3. From any flat sitemap, keep only URLs whose path looks like a blog
       article (contains /blogs/, /blog/, /news/, or /articles/).

    Returns a list of article URLs (blog index pages excluded).
    """
    # 1. WordPress
    wp_sitemap = f"{domain}/post-sitemap.xml"
    r = fetch(wp_sitemap)
    if r and r.status_code == 200:
        urls = parse_sitemap(wp_sitemap)
        if urls:
            print(f"  Source: WordPress post-sitemap.xml ({len(urls)} URLs)")
            return urls

    # 2. Generic /sitemap.xml
    root_sitemap = f"{domain}/sitemap.xml"
    r = fetch(root_sitemap)
    if not r:
        return []

    try:
        root = ET.fromstring(r.content)
    except ET.ParseError:
        return []

    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    child_locs = [el.text.strip() for el in root.findall(".//sm:sitemap/sm:loc", ns)]

    if child_locs:
        # Sitemap index — find blog-related children
        blog_children = [
            loc for loc in child_locs
            if re.search(r"blog|article", loc, re.I)
        ]
        if not blog_children:
            # No obvious blog sitemap; fall back to all children and filter by URL pattern
            blog_children = child_locs

        all_urls = []
        for child in blog_children:
            time.sleep(0.3)
            all_urls.extend(parse_sitemap(child))

        # Keep only article URLs: must have a path segment after the blog handle
        # e.g. /blogs/news/some-article  but NOT /blogs/news (index page)
        blog_path_re = re.compile(r"/(blogs?|articles?|news)/[^/]+/[^/]+", re.I)
        articles = [u for u in all_urls if blog_path_re.search(urlparse(u).path)]
        if articles:
            print(f"  Source: sitemap.xml → blog children ({len(articles)} articles)")
            return articles

        # Fallback: return everything from blog children even without the pattern
        if all_urls:
            print(f"  Source: sitemap.xml blog children ({len(all_urls)} URLs)")
            return all_urls

    # 3. Flat sitemap — filter by URL pattern
    flat_urls = [loc.text.strip() for loc in root.findall(".//sm:url/sm:loc", ns)]
    blog_path_re = re.compile(r"/(blogs?|articles?|news|posts?)/", re.I)
    articles = [u for u in flat_urls if blog_path_re.search(urlparse(u).path)]
    if articles:
        print(f"  Source: flat sitemap.xml ({len(articles)} blog URLs)")
        return articles

    return []


def get_category_pages_from_nav(domain):
    """
    Extract category/product landing page URLs from the main navigation.
    Returns only pages that look like category pages (1–2 URL path segments).
    """
    r = fetch(domain)
    if not r:
        return []

    soup = BeautifulSoup(r.content, "lxml")
    nav = (
        soup.find("nav")
        or soup.find(class_=re.compile(r"(main[-_]nav|primary[-_]nav|site[-_]nav|navbar)", re.I))
        or soup.find(id=re.compile(r"(nav|menu|navigation)", re.I))
    )
    if not nav:
        # Fall back: scan all anchor tags
        nav = soup

    seen = set()
    pages = []
    domain_host = urlparse(domain).netloc

    for a in nav.find_all("a", href=True):
        full = urljoin(domain, a["href"])
        parsed = urlparse(full)

        if parsed.netloc != domain_host:
            continue
        if parsed.query or parsed.fragment:
            continue

        path = parsed.path.rstrip("/")
        segments = [s for s in path.split("/") if s]

        # Only 1–2 path segments = category/sub-category landing pages
        if not (1 <= len(segments) <= 2):
            continue

        if any(p in path.lower() for p in SKIP_NAV_PATTERNS):
            continue

        if full not in seen:
            seen.add(full)
            pages.append(full)

    return pages


# ── Keyword extraction ───────────────────────────────────────────────────────

def is_generic(text):
    t = text.strip().lower()
    return any(re.search(p, t) for p in GENERIC_HEADING_PATTERNS)


def is_clean_keyword(kw):
    """
    Return False if the keyword is noisy:
    - Contains digits or special promotional characters (*+&@#$%^)
    - More than 4 words (too long to be a useful anchor)
    - Over 40 characters
    """
    if re.search(r"[0-9*+&@#$%^(){}\[\]<>]", kw):
        return False
    if len(kw.split()) > 4:
        return False
    if len(kw) > 40:
        return False
    return True


def extract_slug_keywords(url):
    """
    Derive candidate keywords from URL slug segments.
    /automotive-batteries/car-batteries/ → ["car batteries", "automotive batteries"]
    Slug keywords are the most reliable because they directly name the page topic.
    """
    path = urlparse(url).path
    segments = [s for s in path.split("/") if s]
    keywords = []
    for seg in reversed(segments):  # most specific segment first
        kw = seg.replace("-", " ").replace("_", " ").lower()
        words = kw.split()
        if kw in SKIP_SLUG_SEGMENTS:
            continue
        if (
            len(kw) >= 4
            and len(words) >= 1
            and not all(w in STOP_WORDS for w in words)
            and not is_generic(kw)
        ):
            keywords.append(kw)
    return keywords


def extract_page_keywords(url, soup):
    """
    Extract keyword candidates from a commercial page.
    Returns list of (keyword_string, priority_int).
    Priority: slug > title > H1 phrase > H2
    """
    candidates = []

    # 1. Slug keywords (highest priority — most reliable)
    for i, kw in enumerate(extract_slug_keywords(url)):
        candidates.append((kw, 10 - i))

    # 2. Cleaned page title — take as a single short keyword only (no subphrase extraction
    #    to avoid noisy promotional phrases like "24+24* months warranty")
    title_tag = soup.find("title")
    if title_tag:
        t = re.sub(r"\s*[\|\-–:]\s*.+$", "", title_tag.text).strip().lower()
        t = re.sub(r"\blivfast\b", "", t).strip()
        # Strip leading promotional adjectives before evaluating length
        t = re.sub(r"^(best|top|buy|get|shop|find|leading|premium)\s+", "", t).strip()
        t = t.rstrip(".,!?")
        words = t.split()
        if 2 <= len(words) <= 5 and is_clean_keyword(t) and not is_generic(t):
            candidates.append((t, 7))

    # 3. H1 — 2–3 word subphrases, but only from short product-name H1s.
    #    Long H1s (> 7 words) are usually promotional taglines, not product names.
    h1 = soup.find("h1")
    if h1:
        h1_text = h1.get_text(" ", strip=True).lower()
        h1_text = re.sub(r"^(best|top|buy|get|shop|find|leading|premium)\s+", "", h1_text).strip()
        h1_raw_words = h1_text.split()
        if len(h1_raw_words) <= 7:  # skip promotional long-form H1s
            words = [w for w in h1_raw_words if w not in STOP_WORDS and len(w) > 2]
            for n in (2, 3):
                for i in range(len(words) - n + 1):
                    phrase = " ".join(words[i : i + n])
                    # Strip trailing punctuation that may cling to last word
                    phrase = phrase.rstrip(".,!?")
                    if not is_generic(phrase) and len(phrase) > 5 and is_clean_keyword(phrase):
                        candidates.append((phrase, 5))

    # Deduplicate and filter
    seen = set()
    result = []
    for kw, pri in sorted(candidates, key=lambda x: -x[1]):
        kw = kw.strip()
        if kw in seen or len(kw) < 4:
            continue
        if all(w in STOP_WORDS for w in kw.split()):
            continue
        if is_generic(kw):
            continue
        if not is_clean_keyword(kw):
            continue
        seen.add(kw)
        result.append((kw, pri))

    return result[:12]  # cap at 12 per page


# ── Content extraction ───────────────────────────────────────────────────────

def get_article_body(soup):
    """
    Return the BeautifulSoup element containing the blog article body text.
    Tries multiple selectors in priority order.
    """
    candidates = [
        # WordPress / generic
        soup.find(class_=re.compile(r"entry[-_]content", re.I)),
        soup.find(class_=re.compile(r"post[-_]content", re.I)),
        soup.find(class_=re.compile(r"blog[-_]content", re.I)),
        soup.find(class_=re.compile(r"article[-_]content", re.I)),
        soup.find(class_=re.compile(r"elementor[-_]widget[-_]theme[-_]post[-_]content", re.I)),
        # Shopify — more specific selectors first to avoid catching sidebar wrappers
        soup.find(class_=re.compile(r"article-template__(body|content|text)", re.I)),
        soup.find(class_=re.compile(r"article__(body|content|text)", re.I)),
        # Semantic fallbacks
        soup.find("article"),
        soup.find("main"),
    ]

    for el in candidates:
        if el and len(el.get_text(strip=True)) > 200:
            return el

    # Last resort: strip noise from body
    body = soup.find("body")
    if body:
        body = BeautifulSoup(str(body), "lxml")  # work on a copy
        for noise in body.find_all(
            class_=re.compile(r"(nav|header|footer|sidebar|widget|menu|breadcrumb|comment)", re.I)
        ):
            noise.decompose()
        for tag in body.find_all(["nav", "header", "footer", "aside"]):
            tag.decompose()
        if len(body.get_text(strip=True)) > 200:
            return body

    return None


def get_category_footer_block(soup):
    """
    Return the SEO / description text block that appears below the product
    grid on a category page (not the site-wide footer).

    livfast.in uses Elementor: content blocks have class 'elementor-widget-text-editor'.
    The site-wide footer is wrapped in a div with class 'footer-width-fixer' — any
    element inside that container is excluded.

    Returns a BeautifulSoup element or None.
    """
    # Identify the site-wide footer container so we can exclude its descendants
    site_footer = (
        soup.find(class_=re.compile(r"footer[-_]width[-_]fixer", re.I))
        or soup.find("footer")
    )

    def inside_site_footer(el):
        if site_footer is None:
            return False
        for parent in el.parents:
            if parent == site_footer:
                return True
        return False

    # 1. Explicit semantic class patterns (non-Elementor sites)
    for el in soup.find_all(
        ["div", "section"],
        class_=re.compile(
            r"(seo[-_]text|category[-_]desc|cat[-_]desc|term[-_]desc|"
            r"bottom[-_]content|page[-_]description)",
            re.I,
        ),
    ):
        if inside_site_footer(el):
            continue
        text = el.get_text(" ", strip=True)
        if len(text) > 150:
            return el

    # 2. Elementor: find all 'elementor-widget-text-editor' blocks outside the footer
    #    Take the last substantial one — on category pages this is typically the SEO
    #    description block that lives below the product grid.
    all_blocks = soup.find_all(class_=re.compile(r"elementor-widget-text-editor", re.I))
    substantial = [
        b for b in all_blocks
        if len(b.get_text(strip=True)) > 150 and not inside_site_footer(b)
    ]
    if substantial:
        return substantial[-1]

    return None


# ── Matching helpers ─────────────────────────────────────────────────────────

def keyword_in_text(keyword, text):
    """Case-insensitive word-boundary match. Returns True if keyword found."""
    pattern = r"(?<![a-zA-Z])" + re.escape(keyword.lower()) + r"(?![a-zA-Z])"
    return bool(re.search(pattern, text.lower()))


def keyword_is_already_linked(keyword, element):
    """
    True if the keyword text already appears inside an <a> tag in this element.
    Prevents recommending links that already exist.
    """
    for a in element.find_all("a"):
        if keyword.lower() in a.get_text(" ", strip=True).lower():
            return True
    return False


def get_linked_target_urls(element, domain):
    """Return set of normalised URLs that are already linked from this element."""
    targets = set()
    for a in element.find_all("a", href=True):
        full = urljoin(domain, a["href"]).rstrip("/")
        targets.add(full)
    return targets


def find_opportunities(source_url, element, keyword_map, domain, location):
    """
    Scan an HTML element for unlinked keyword matches.

    Args:
        source_url:   URL of the page being scanned
        element:      BeautifulSoup element (article body or footer block)
        keyword_map:  dict of keyword → {url, priority}
        domain:       base domain URL
        location:     'Body' or 'Footer Content'

    Returns:
        List of opportunity dicts (capped at MAX_LINKS_PER_PAGE).
    """
    text = element.get_text(" ", strip=True)
    if len(text) < 50:
        return []

    existing_targets = get_linked_target_urls(element, domain)
    seen_targets = set()
    results = []

    # Process keywords: most specific (longest, highest priority) first
    sorted_kws = sorted(
        keyword_map.items(), key=lambda x: (-x[1]["priority"], -len(x[0]))
    )

    for kw, info in sorted_kws:
        target_url = info["url"].rstrip("/")

        if source_url.rstrip("/") == target_url:
            continue  # no self-links
        if target_url in existing_targets:
            continue  # already linked to this target
        if target_url in seen_targets:
            continue  # already recommended to this target from this page
        if keyword_is_already_linked(kw, element):
            continue  # keyword already hyperlinked (possibly to different target)
        if not keyword_in_text(kw, text):
            continue  # keyword not found

        results.append(
            {
                "source_url": source_url,
                "anchor_text": kw,
                "location": location,
                "target_url": info["url"],
            }
        )
        seen_targets.add(target_url)

        if len(results) >= MAX_LINKS_PER_PAGE:
            break

    return results


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Find internal linking opportunities for a domain.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "domain",
        nargs="?",
        default="https://www.livfast.in",
        help="Full domain URL (default: https://www.livfast.in)",
    )
    parser.add_argument(
        "--max-blogs",
        type=int,
        default=None,
        metavar="N",
        help="Limit blog posts analysed (default: all)",
    )
    parser.add_argument(
        "--target",
        type=str,
        default=None,
        metavar="URL",
        help="Analyse a single target URL only — find where on the site this page can be linked from",
    )
    parser.add_argument(
        "--keyword",
        type=str,
        default=None,
        metavar="KEYWORD",
        help="(Use with --target) Search for this specific keyword only; skips the interactive prompt",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_DELAY,
        metavar="SECS",
        help=f"Seconds between requests (default: {DEFAULT_DELAY})",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        metavar="PATH",
        help="Custom output CSV path (default: <plugin>/output/{domain}-internal-linking-{date}.csv)",
    )
    args = parser.parse_args()

    domain = args.domain.rstrip("/")
    delay = args.delay
    target_url = args.target.rstrip("/") if args.target else None

    # Validate target belongs to this domain
    if target_url:
        target_host = urlparse(target_url).netloc
        domain_host = urlparse(domain).netloc
        if target_host and target_host != domain_host:
            print(f"[ERROR] --target must belong to {domain_host}, got {target_host}")
            sys.exit(1)

    # Output file path
    domain_name = urlparse(domain).netloc.replace("www.", "")
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "..", "output")
    os.makedirs(output_dir, exist_ok=True)

    if args.output:
        # User-supplied output path overrides everything
        output_file = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        target_slug = (
            urlparse(target_url).path.strip("/").replace("/", "-") or "target"
        ) if target_url else None
    elif target_url:
        target_slug = urlparse(target_url).path.strip("/").replace("/", "-") or "target"
        # Final output filename is set after keyword selection (see Step 3)
        output_file = None
    else:
        output_file = os.path.join(
            output_dir, f"{domain_name}-internal-linking-{date.today()}.csv"
        )

    print(f"\n{'='*65}")
    print(f"  Internal Linking Finder")
    print(f"  Domain : {domain}")
    if target_url:
        print(f"  Target : {target_url}")
    print(f"  Delay  : {delay}s between requests")
    if output_file:
        print(f"  Output : {output_file}")
    print(f"{'='*65}\n")

    # ── STEP 1: Discover category pages from navigation ──────────────

    print("► STEP 1: Discovering category pages from navigation...")
    category_pages = get_category_pages_from_nav(domain)
    print(f"  Found {len(category_pages)} category pages:")
    for url in category_pages:
        print(f"    · {url}")

    if not category_pages:
        print("  [ERROR] No category pages found. Exiting.")
        sys.exit(1)

    # ── STEP 2: Discover blog URLs ───────────────────────────────────
    # WordPress  → /post-sitemap.xml
    # Shopify    → /sitemap.xml (index) → sitemap_blogs_N.xml children
    # Generic    → /sitemap.xml (flat)

    print(f"\n► STEP 2: Discovering blog URLs...")
    blog_urls = _discover_blog_urls(domain)

    if args.max_blogs:
        blog_urls = blog_urls[: args.max_blogs]
        print(f"  Using {len(blog_urls)} blog posts (--max-blogs {args.max_blogs})")
    else:
        print(f"  Found {len(blog_urls)} blog posts")

    if not blog_urls:
        print("  [WARN] No blog posts found")

    # ── STEP 3: Build keyword-to-URL map ────────────────────────────────
    # Target mode  → extract keywords from the single --target URL only.
    # Full-site mode → extract keywords from every discovered category page.

    keyword_map = {}  # keyword → {url, priority}

    if target_url:
        print(f"\n► STEP 3: Extracting keywords from target URL...")
        print(f"  Target: {target_url}")
        r = fetch(target_url)
        if not r:
            print("  [ERROR] Could not fetch target URL. Exiting.")
            sys.exit(1)
        soup = BeautifulSoup(r.content, "lxml")
        keywords = extract_page_keywords(target_url, soup)
        for kw, priority in keywords:
            keyword_map[kw] = {"url": target_url, "priority": priority}
        if keywords:
            print(f"  Keywords found: {', '.join(kw for kw, _ in keywords)}")
        else:
            print("  [ERROR] No keywords extracted from target URL. Exiting.")
            sys.exit(1)

        # ── Keyword selection (target mode only) ──────────────────────
        # Use --keyword if supplied, otherwise ask interactively.
        specific_keyword = args.keyword.strip().lower() if args.keyword else None

        if not specific_keyword:
            print(f"\n  Do you want to search for a specific keyword, or use all of the above?")
            print(f"  Enter a keyword to narrow the search, or press Enter to use all:")
            try:
                user_input = input("  > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                user_input = ""
            specific_keyword = user_input if user_input else None

        if specific_keyword:
            if specific_keyword not in keyword_map:
                # Try partial match
                matches = [kw for kw in keyword_map if specific_keyword in kw]
                if matches:
                    print(f"  Exact match not found. Using closest match: '{matches[0]}'")
                    specific_keyword = matches[0]
                else:
                    print(f"  [WARN] '{specific_keyword}' not in extracted keywords. Searching anyway.")
                    keyword_map = {specific_keyword: {"url": target_url, "priority": 10}}
            else:
                keyword_map = {specific_keyword: keyword_map[specific_keyword]}
            print(f"  Searching for: '{specific_keyword}' → {target_url}")
            kw_slug = specific_keyword.replace(" ", "-")
            # --output, if supplied, takes precedence over auto-naming
            if not args.output:
                # Only append keyword slug if it isn't already the last segment of target_slug
                if target_slug.endswith(kw_slug):
                    output_file = os.path.join(
                        output_dir, f"{domain_name}-{target_slug}-{date.today()}.csv"
                    )
                else:
                    output_file = os.path.join(
                        output_dir, f"{domain_name}-{target_slug}-{kw_slug}-{date.today()}.csv"
                    )
        else:
            print(f"  Searching for all {len(keyword_map)} keywords.")
            if not args.output:
                output_file = os.path.join(
                    output_dir, f"{domain_name}-{target_slug}-{date.today()}.csv"
                )

        print(f"\n  Keyword map: {len(keyword_map)} keyword(s) → {target_url}")
        print(f"  Output : {output_file}")
    else:
        print(f"\n► STEP 3: Extracting keywords from {len(category_pages)} category pages...")
        for url in category_pages:
            print(f"  Mapping: {url}")
            r = fetch(url)
            if not r:
                continue
            soup = BeautifulSoup(r.content, "lxml")
            keywords = extract_page_keywords(url, soup)
            added = []
            for kw, priority in keywords:
                if kw not in keyword_map or keyword_map[kw]["priority"] < priority:
                    keyword_map[kw] = {"url": url, "priority": priority}
                    added.append(kw)
            if added:
                print(f"    Keywords: {', '.join(added)}")
            time.sleep(delay)

        print(f"\n  Keyword map: {len(keyword_map)} total keywords across {len(category_pages)} pages")

        if not keyword_map:
            print("  [ERROR] No keywords extracted. Exiting.")
            sys.exit(1)

    # ── STEP 4: Scan blog posts ──────────────────────────────────────

    print(f"\n► STEP 4: Scanning {len(blog_urls)} blog posts for unlinked keywords...")
    blog_opportunities = []
    skipped_blogs = 0

    for i, url in enumerate(blog_urls, 1):
        sys.stdout.write(f"  [{i:>3}/{len(blog_urls)}] {url} ")
        sys.stdout.flush()

        r = fetch(url)
        if not r:
            skipped_blogs += 1
            print()
            continue

        soup = BeautifulSoup(r.content, "lxml")
        body = get_article_body(soup)

        if not body or len(body.get_text(strip=True)) < 150:
            print("→ skipped (no body)")
            skipped_blogs += 1
            time.sleep(delay)
            continue

        opps = find_opportunities(url, body, keyword_map, domain, "Body")

        if opps:
            print(f"→ {len(opps)} opportunity/ies")
            for o in opps:
                print(f"       ✓ '{o['anchor_text']}' → {o['target_url']}")
            blog_opportunities.extend(opps)
        else:
            print("→ none")

        time.sleep(delay)

    print(f"\n  Blog scan complete: {len(blog_opportunities)} opportunities found "
          f"({skipped_blogs} posts skipped)")

    # ── STEP 5: Scan category page footer content ────────────────────

    print(f"\n► STEP 5: Scanning {len(category_pages)} category page footers...")
    footer_opportunities = []

    for url in category_pages:
        sys.stdout.write(f"  {url} ")
        sys.stdout.flush()

        r = fetch(url)
        if not r:
            print()
            continue

        soup = BeautifulSoup(r.content, "lxml")
        footer_block = get_category_footer_block(soup)

        if not footer_block or len(footer_block.get_text(strip=True)) < 100:
            print("→ no SEO footer block")
            time.sleep(delay)
            continue

        opps = find_opportunities(url, footer_block, keyword_map, domain, "Footer Content")

        if opps:
            print(f"→ {len(opps)} opportunity/ies")
            for o in opps:
                print(f"       ✓ '{o['anchor_text']}' → {o['target_url']}")
            footer_opportunities.extend(opps)
        else:
            print("→ no gaps found")

        time.sleep(delay)

    # ── STEP 6: Write CSV output ─────────────────────────────────────

    all_opps = blog_opportunities + footer_opportunities

    print(f"\n► STEP 6: Writing results to CSV...")

    with open(output_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "Opportunity Page URL",
                "Anchor Text",
                "Location on Page",
                "Target URL",
            ],
        )
        writer.writeheader()
        for opp in all_opps:
            writer.writerow(
                {
                    "Opportunity Page URL": opp["source_url"],
                    "Anchor Text": opp["anchor_text"],
                    "Location on Page": opp["location"],
                    "Target URL": opp["target_url"],
                }
            )

    print(f"\n{'='*65}")
    print(f"  DONE")
    print(f"  Blog opportunities   : {len(blog_opportunities)}")
    print(f"  Footer opportunities : {len(footer_opportunities)}")
    print(f"  Total                : {len(all_opps)}")
    print(f"  Output               : {output_file}")
    print(f"{'='*65}\n")

    if not all_opps:
        print("  No opportunities found. Possible causes:")
        print("  · All keywords already linked on blog posts")
        print("  · Blog content is very short or JS-rendered")
        print("  · Keyword map did not produce matches (try --delay 2)")


# ── Web app entry point ───────────────────────────────────────────────────────

def run_analysis(domain, target_url=None, keyword=None, max_blogs=None, delay=DEFAULT_DELAY, custom_urls=None):
    """
    Generator for the Flask web app.
    Yields event dicts that are streamed to the browser as Server-Sent Events.

    Event shapes:
      {"type": "step",         "step": N, "message": "..."}
      {"type": "step_done",    "step": N, "message": "...", "data": {...}}
      {"type": "log",          "message": "..."}
      {"type": "blog_scan",    "current": N, "total": N, "url": "...", "found": N}
      {"type": "footer_scan",  "url": "...", "found": N}
      {"type": "opportunity",  "source_url": "...", "anchor_text": "...",
                               "location": "...", "target_url": "..."}
      {"type": "complete",     "stats": {...}, "opportunities": [...]}
      {"type": "error",        "message": "..."}
    """
    domain = domain.rstrip("/")
    target_url = target_url.rstrip("/") if target_url else None

    # ── Step 1: Category pages ───────────────────────────────────────
    yield {"type": "step", "step": 1, "message": "Discovering category pages from navigation…"}
    category_pages = get_category_pages_from_nav(domain)
    if not category_pages:
        yield {"type": "error", "message": "No category pages found — check the domain URL."}
        return
    yield {
        "type": "step_done", "step": 1,
        "message": f"Found {len(category_pages)} category pages",
        "data": {"pages": category_pages},
    }

    # ── Step 2: Blog URLs ────────────────────────────────────────────
    if custom_urls:
        yield {"type": "step", "step": 2, "message": "Using provided URL list…"}
        blog_urls = [u.strip() for u in custom_urls if u.strip()]
        if max_blogs:
            blog_urls = blog_urls[:max_blogs]
        yield {
            "type": "step_done", "step": 2,
            "message": f"Using {len(blog_urls)} custom URLs",
            "data": {"count": len(blog_urls)},
        }
    else:
        yield {"type": "step", "step": 2, "message": "Discovering blog / article URLs…"}
        blog_urls = _discover_blog_urls(domain)
        if max_blogs:
            blog_urls = blog_urls[:max_blogs]
        yield {
            "type": "step_done", "step": 2,
            "message": f"Found {len(blog_urls)} blog posts",
            "data": {"count": len(blog_urls)},
        }

    # ── Step 3: Keyword map ──────────────────────────────────────────
    keyword_map = {}

    if target_url:
        yield {"type": "step", "step": 3, "message": f"Extracting keywords from target URL…"}
        r = fetch(target_url)
        if not r:
            yield {"type": "error", "message": "Could not fetch the target URL."}
            return
        soup = BeautifulSoup(r.content, "lxml")
        kws = extract_page_keywords(target_url, soup)
        for kw, priority in kws:
            keyword_map[kw] = {"url": target_url, "priority": priority}

        # Apply user-specified keyword filter (supports comma-separated list)
        if keyword:
            requested = [k.strip().lower() for k in keyword.split(",") if k.strip()]
            filtered = {}
            for kw_req in requested:
                if kw_req in keyword_map:
                    filtered[kw_req] = keyword_map[kw_req]
                else:
                    matches = [k for k in keyword_map if kw_req in k]
                    if matches:
                        for m in matches:
                            filtered[m] = keyword_map[m]
                    else:
                        filtered[kw_req] = {"url": target_url, "priority": 10}
            keyword_map = filtered

        if not keyword_map:
            yield {"type": "error", "message": "No keywords could be extracted from the target URL."}
            return

        yield {
            "type": "step_done", "step": 3,
            "message": f"Keyword map: {len(keyword_map)} keyword(s)",
            "data": {"keywords": list(keyword_map.keys())},
        }
    else:
        yield {"type": "step", "step": 3,
               "message": f"Extracting keywords from {len(category_pages)} category pages…"}
        for url in category_pages:
            yield {"type": "log", "message": f"Mapping: {url}"}
            r = fetch(url)
            if not r:
                time.sleep(delay)
                continue
            soup = BeautifulSoup(r.content, "lxml")
            kws = extract_page_keywords(url, soup)
            for kw, pri in kws:
                if kw not in keyword_map or keyword_map[kw]["priority"] < pri:
                    keyword_map[kw] = {"url": url, "priority": pri}
            time.sleep(delay)

        if not keyword_map:
            yield {"type": "error", "message": "No keywords extracted from category pages."}
            return

        yield {
            "type": "step_done", "step": 3,
            "message": f"Keyword map: {len(keyword_map)} keywords across {len(category_pages)} pages",
            "data": {"keywords": list(keyword_map.keys())},
        }

    # ── Step 4: Scan blog posts ──────────────────────────────────────
    yield {"type": "step", "step": 4,
           "message": f"Scanning {len(blog_urls)} blog posts for unlinked keywords…"}
    blog_opportunities = []

    for i, url in enumerate(blog_urls, 1):
        r = fetch(url)
        if not r:
            yield {"type": "blog_scan", "current": i, "total": len(blog_urls),
                   "url": url, "found": 0}
            time.sleep(delay)
            continue

        soup = BeautifulSoup(r.content, "lxml")
        body = get_article_body(soup)
        found = 0

        if body and len(body.get_text(strip=True)) >= 150:
            opps = find_opportunities(url, body, keyword_map, domain, "Body")
            found = len(opps)
            for opp in opps:
                blog_opportunities.append(opp)
                yield {"type": "opportunity", **opp}

        yield {"type": "blog_scan", "current": i, "total": len(blog_urls),
               "url": url, "found": found}
        time.sleep(delay)

    yield {
        "type": "step_done", "step": 4,
        "message": f"Blog scan complete — {len(blog_opportunities)} opportunities found",
    }

    # ── Step 5: Scan category footers ───────────────────────────────
    footer_opportunities = []

    if custom_urls:
        yield {"type": "step", "step": 5, "message": "Footer scan skipped (custom URL mode)"}
        yield {"type": "step_done", "step": 5,
               "message": "Footer scan skipped — using custom URL list"}
    else:
        yield {"type": "step", "step": 5,
               "message": f"Scanning {len(category_pages)} category page footers…"}

        for i, url in enumerate(category_pages, 1):
            r = fetch(url)
            if not r:
                yield {"type": "footer_scan", "current": i, "total": len(category_pages),
                       "url": url, "found": 0}
                time.sleep(delay)
                continue

            soup = BeautifulSoup(r.content, "lxml")
            footer_block = get_category_footer_block(soup)
            found = 0

            if footer_block and len(footer_block.get_text(strip=True)) >= 100:
                opps = find_opportunities(url, footer_block, keyword_map, domain, "Footer Content")
                found = len(opps)
                for opp in opps:
                    footer_opportunities.append(opp)
                    yield {"type": "opportunity", **opp}

            yield {"type": "footer_scan", "current": i, "total": len(category_pages),
                   "url": url, "found": found}
            time.sleep(delay)

        yield {
            "type": "step_done", "step": 5,
            "message": f"Footer scan complete — {len(footer_opportunities)} opportunities found",
        }

    # ── Done ─────────────────────────────────────────────────────────
    all_opps = blog_opportunities + footer_opportunities
    yield {
        "type": "complete",
        "stats": {
            "total": len(all_opps),
            "blog": len(blog_opportunities),
            "footer": len(footer_opportunities),
        },
        "opportunities": all_opps,
    }


if __name__ == "__main__":
    main()
