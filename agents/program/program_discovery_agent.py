"""
Univora - Program Discovery Agent (Stage 2)

Strategy (v3.0.0 — rebuilt):
    Verified university domain (data/processed/university_sources.csv)
        ↓
    Sitemap / robots.txt discovery of candidate academic URLs   [PRIMARY]
        ↓ (only if sitemap yields too few candidates)
    Shallow same-domain crawl from homepage (depth 1-2)          [SECONDARY]
        ↓
    Keyword + structural filtering of candidate pages
        ↓
    Structured extraction (tables / cards / lists)
        ↓
    School / Department -> Program -> Degree
        ↓
    Persistent programs.csv + program_discovery_registry.json

Why this version is different from v2.2.0:
    The previous version depended on scraping DuckDuckGo's HTML search
    results ("site:domain ..." queries) to find candidate pages. That is
    an unreliable, unofficial dependency — DuckDuckGo can rate-limit,
    block automated requests, or change its markup at any time, and when
    it does, discovery silently returns 0-1 candidate pages for every
    university, even ones as well-documented as MIT or Stanford.

    This version never depends on any search engine. It uses two
    protocols that are meant to be machine-read:
      1. sitemap.xml / robots.txt (the standard way sites advertise
         their own page structure)
      2. a bounded, same-domain, polite crawl from the homepage as a
         fallback when a site has no usable sitemap

No LLM
No Ollama
No Gemini
No OpenAI
No IPEDS
No search-engine scraping
No generic full-site / unbounded crawling

Requirements:
    pip install requests beautifulsoup4

Run:
    python agents/program/program_discovery_agent.py --limit 3 --force
    python agents/program/program_discovery_agent.py --limit 184
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import OrderedDict, deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

AGENT_VERSION = "3.0.0"

ROOT = Path(__file__).resolve().parents[2]

UNIVERSITY_FILE = ROOT / "data" / "processed" / "university_sources.csv"

PROGRAM_DIR = ROOT / "data" / "processed"
PROGRAM_FILE = PROGRAM_DIR / "programs.csv"
REGISTRY_FILE = PROGRAM_DIR / "program_discovery_registry.json"
REVIEW_FILE = PROGRAM_DIR / "program_discovery_review.csv"

PROGRAM_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_TIMEOUT = 20
MAX_CANDIDATE_PAGES = 12
MAX_PAGE_SIZE = 3_000_000
REQUEST_DELAY = 0.8

# Crawl bounds (fallback discovery only)
CRAWL_MAX_DEPTH = 2
CRAWL_MAX_PAGES_VISITED = 40  # hard ceiling on homepage-crawl fetches per university

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)

PROGRAM_FIELDS = [
    "program_id",
    "university_id",
    "university_name",
    "school_name",
    "department_name",
    "program_name",
    "degree_level",
    "degree_name",
    "program_url",
    "source_url",
    "evidence",
    "confidence",
    "status",
    "agent_version",
]

REVIEW_FIELDS = [
    "university_id",
    "university_name",
    "official_domain",
    "official_website",
    "status",
    "reason",
    "pages_checked",
    "programs_found",
    "agent_version",
]

# Path/URL keywords that indicate an "academic/program" page.
# Order doesn't matter here; scoring happens in rank_candidate_pages().
PROGRAM_URL_TERMS = [
    "program",
    "degree",
    "graduate",
    "academic",
    "department",
    "school-of",
    "college-of",
    "majors",
    "phd",
    "masters",
    "admission",
    "catalog",
]

BAD_URL_TERMS = [
    "facebook.com",
    "twitter.com",
    "x.com",
    "instagram.com",
    "linkedin.com",
    "youtube.com",
    "mailto:",
    "tel:",
    ".pdf",
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".zip",
    ".mp4",
    "/login",
    "/signin",
    "/search?",
    "/donate",
    "/giving",
    "/athletics",
    "/news/",
    "/events/",
    "/calendar",
    "/alumni",
    "/careers",
    "/jobs",
]

BAD_TEXT_PATTERNS = [
    "click here",
    "read more",
    "learn more",
    "all rights reserved",
    "privacy policy",
    "terms of use",
]

GENERIC_PROGRAM_NAMES = {
    "programs",
    "graduate programs",
    "academic programs",
    "degree programs",
    "overview",
    "home",
}

GENERIC_DEPARTMENT_NAMES = {
    "department",
    "school",
    "college",
    "division",
}

ACADEMIC_TERMS = [
    "program",
    "degree",
    "master",
    "phd",
    "doctoral",
    "graduate",
    "curriculum",
    "credit hours",
    "admission requirements",
    "faculty",
    "department",
    "school of",
    "college of",
]

DEGREE_PATTERNS = [
    (r"\bph\.?d\.?\b", "PhD"),
    (r"\bdoctor of philosophy\b", "PhD"),
    (r"\bm\.?s\.?\b", "MS"),
    (r"\bmaster of science\b", "MS"),
    (r"\bm\.?a\.?\b", "MA"),
    (r"\bmaster of arts\b", "MA"),
    (r"\bmba\b", "MBA"),
    (r"\bmaster of business administration\b", "MBA"),
    (r"\bmeng\b|\bm\.eng\.?\b", "MEng"),
    (r"\bmaster of engineering\b", "MEng"),
    (r"\bcertificate\b", "Certificate"),
    (r"\bundergraduate\b|\bbachelor'?s?\b|\bb\.?s\.?\b|\bb\.?a\.?\b", "Bachelors"),
]


# ============================================================
# NETWORK
# ============================================================

def fetch(url: str) -> Optional[str]:
    """Fetch a page safely. Returns None on any failure."""
    try:
        response = SESSION.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)

        if response.status_code >= 400:
            return None

        content_type = response.headers.get("content-type", "").lower()

        if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
            return None

        content = response.content

        if len(content) > MAX_PAGE_SIZE:
            return None

        response.encoding = response.apparent_encoding or response.encoding

        time.sleep(REQUEST_DELAY)

        return response.text

    except requests.RequestException:
        return None


def fetch_raw(url: str, timeout: int = REQUEST_TIMEOUT) -> Optional[str]:
    """Fetch raw text content (used for robots.txt / sitemap.xml, which
    are not always served as text/html)."""
    try:
        response = SESSION.get(url, timeout=timeout, allow_redirects=True)

        if response.status_code >= 400:
            return None

        content = response.content

        if len(content) > MAX_PAGE_SIZE:
            return None

        response.encoding = response.apparent_encoding or response.encoding

        return response.text

    except requests.RequestException:
        return None


# ============================================================
# GENERAL HELPERS
# ============================================================

def normalize_space(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "")
    return text.strip()


def clean_text(text: str) -> str:
    text = unquote(text or "")
    text = text.replace("\xa0", " ")
    text = normalize_space(text)
    return text


def normalize_name(text: str) -> str:
    text = clean_text(text).lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def slugify(text: str) -> str:
    text = normalize_name(text)
    return re.sub(r"\s+", "-", text)[:120]


def same_domain(url: str, domain: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        domain = domain.lower().replace("www.", "")
        host = host.replace("www.", "")

        return host == domain or host.endswith("." + domain)
    except Exception:
        return False


def make_absolute(base_url: str, href: str) -> Optional[str]:
    if not href:
        return None

    href = href.strip()

    if href.startswith("#") or href.startswith("mailto:") or href.startswith("javascript:"):
        return None

    try:
        return urljoin(base_url, href)
    except Exception:
        return None


def normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)

        clean_query = "&".join(
            f"{k}={v[0]}"
            for k, v in parse_qs(parsed.query).items()
            if k.lower() not in {
                "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
            }
        )

        path = parsed.path.rstrip("/")

        return parsed._replace(
            query=clean_query,
            fragment="",
            path=path or "/",
        ).geturl()

    except Exception:
        return url


def is_bad_text(text: str) -> bool:
    normalized = normalize_name(text)

    if not normalized:
        return True

    if normalized in GENERIC_PROGRAM_NAMES:
        return True

    if normalized in GENERIC_DEPARTMENT_NAMES:
        return True

    for pattern in BAD_TEXT_PATTERNS:
        if pattern in normalized:
            return True

    return False


def is_bad_url(url: str) -> bool:
    low = url.lower()
    return any(term in low for term in BAD_URL_TERMS)


# ============================================================
# UNIVERSITY / REGISTRY / OUTPUT I/O
# ============================================================

def load_universities() -> List[Dict[str, str]]:
    if not UNIVERSITY_FILE.exists():
        return []

    with UNIVERSITY_FILE.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)

    universities = []

    for row in rows:
        domain = clean_text(row.get("official_domain", ""))
        website = clean_text(
            row.get("university_website", "") or (f"https://{domain}" if domain else "")
        )

        if not domain:
            continue

        universities.append({
            "university_id": clean_text(row.get("university_id", "")),
            "university_name": clean_text(row.get("university_name", "")),
            "official_domain": domain,
            "official_website": website,
        })

    return universities


def load_registry() -> Dict[str, Dict]:
    if not REGISTRY_FILE.exists():
        return {}

    try:
        with REGISTRY_FILE.open("r", encoding="utf-8") as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError):
        return {}


def save_registry(registry: Dict[str, Dict]) -> None:
    with REGISTRY_FILE.open("w", encoding="utf-8") as fh:
        json.dump(registry, fh, indent=2, ensure_ascii=False)


def already_processed(university_id: str, registry: Dict[str, Dict], force: bool) -> bool:
    if force:
        return False

    entry = registry.get(university_id)

    return bool(entry and entry.get("status") == "completed")


def load_programs() -> List[Dict[str, str]]:
    if not PROGRAM_FILE.exists():
        return []

    with PROGRAM_FILE.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def save_programs(rows: List[Dict[str, str]]) -> None:
    with PROGRAM_FILE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=PROGRAM_FIELDS)
        writer.writeheader()

        for row in rows:
            writer.writerow({field: row.get(field, "") for field in PROGRAM_FIELDS})


def save_review(rows: List[Dict[str, str]]) -> None:
    with REVIEW_FILE.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=REVIEW_FIELDS)
        writer.writeheader()

        for row in rows:
            writer.writerow({field: row.get(field, "") for field in REVIEW_FIELDS})


# ============================================================
# DISCOVERY - PRIMARY: SITEMAP / ROBOTS.TXT
# ============================================================

def sitemap_candidates(domain: str) -> List[str]:
    """
    Read robots.txt for declared sitemaps, plus the conventional
    /sitemap.xml location. Supports one level of sitemap-index nesting
    (a sitemap.xml that itself lists other sitemap files, which is
    common on large university sites).
    """
    sitemap_urls: List[str] = []

    robots_text = fetch_raw(f"https://{domain}/robots.txt")

    if robots_text:
        for line in robots_text.splitlines():
            if line.lower().startswith("sitemap:"):
                candidate = line.split(":", 1)[1].strip()

                if candidate.startswith("http"):
                    sitemap_urls.append(candidate)

    sitemap_urls.append(f"https://{domain}/sitemap.xml")
    sitemap_urls = list(OrderedDict.fromkeys(sitemap_urls))

    page_urls: List[str] = []
    nested_sitemaps: List[str] = []

    for sitemap_url in sitemap_urls:
        text = fetch_raw(sitemap_url)

        if not text:
            continue

        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", text, flags=re.IGNORECASE | re.DOTALL)

        is_index = "<sitemapindex" in text.lower()

        for loc in locs:
            loc = clean_text(loc)

            if not loc.startswith("http"):
                continue

            if is_index:
                nested_sitemaps.append(loc)
            else:
                if same_domain(loc, domain):
                    page_urls.append(normalize_url(loc))

    # One level of nested-sitemap expansion, bounded to a handful of
    # sitemaps so a huge university site doesn't trigger thousands of
    # fetches.
    for nested_url in nested_sitemaps[:5]:
        text = fetch_raw(nested_url)

        if not text:
            continue

        locs = re.findall(r"<loc>\s*(.*?)\s*</loc>", text, flags=re.IGNORECASE | re.DOTALL)

        for loc in locs:
            loc = clean_text(loc)

            if loc.startswith("http") and same_domain(loc, domain):
                page_urls.append(normalize_url(loc))

    return list(OrderedDict.fromkeys(page_urls))


# ============================================================
# DISCOVERY - SECONDARY: BOUNDED SAME-DOMAIN CRAWL
# ============================================================

def extract_page_links(html: str, base_url: str, domain: str) -> List[str]:
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []

    for anchor in soup.find_all("a", href=True):
        absolute = make_absolute(base_url, anchor["href"])

        if not absolute:
            continue

        if not same_domain(absolute, domain):
            continue

        if is_bad_url(absolute):
            continue

        links.append(normalize_url(absolute))

    return list(OrderedDict.fromkeys(links))


def crawl_candidates(domain: str, homepage: str) -> List[str]:
    """
    Bounded, polite, same-domain breadth-first crawl starting from the
    homepage. Used only as a fallback when the sitemap yields too few
    candidates. This is NOT a general-purpose crawler — it is capped by
    both depth and total pages visited, and only follows links whose
    path contains a program/academic keyword (checked in
    rank_candidate_pages, applied here as a pre-filter to avoid wasting
    fetches on obviously irrelevant pages like /news/2024/...).
    """
    visited: set = set()
    found: List[str] = []

    queue = deque([(normalize_url(homepage), 0)])
    visited.add(normalize_url(homepage))

    pages_fetched = 0

    while queue and pages_fetched < CRAWL_MAX_PAGES_VISITED:
        url, depth = queue.popleft()

        html = fetch(url)
        pages_fetched += 1

        if not html:
            continue

        links = extract_page_links(html, url, domain)

        for link in links:
            if link in visited:
                continue

            visited.add(link)

            path = urlparse(link).path.lower()
            keyword_hit = any(term in path for term in PROGRAM_URL_TERMS)

            if keyword_hit:
                found.append(link)

            if depth < CRAWL_MAX_DEPTH and keyword_hit:
                # Only expand outward from pages that already look
                # relevant — this keeps the crawl small and on-topic
                # instead of wandering the whole site.
                queue.append((link, depth + 1))

            if pages_fetched >= CRAWL_MAX_PAGES_VISITED:
                break

    return list(OrderedDict.fromkeys(found))


# ============================================================
# CANDIDATE RANKING
# ============================================================

def rank_candidate_pages(urls: List[str], domain: str) -> List[str]:
    scored: List[Tuple[int, str]] = []

    for url in urls:
        if not same_domain(url, domain):
            continue

        if is_bad_url(url):
            continue

        path = urlparse(url).path.lower()
        score = 0

        for term in PROGRAM_URL_TERMS:
            if term in path:
                score += 5

        if "/graduate" in path:
            score += 20
        if "/program" in path:
            score += 15
        if "/degree" in path:
            score += 12
        if "/academic" in path:
            score += 10
        if "/department" in path:
            score += 8

        scored.append((score, url))

    scored.sort(key=lambda x: (-x[0], len(x[1])))

    return [url for _, url in scored]


def page_keyword_score(url: str, title: str, text: str) -> int:
    path = urlparse(url).path.lower()
    low_title = (title or "").lower()
    low_text = (text or "").lower()[:5000]

    score = 0

    for term in PROGRAM_URL_TERMS:
        if term in path:
            score += 4

    for term in ["program", "graduate", "degree", "master", "phd"]:
        if term in low_title:
            score += 3

    for term in ACADEMIC_TERMS:
        if term in low_text:
            score += 1

    return score


def is_academic_page(url: str, title: str, text: str) -> bool:
    score = page_keyword_score(url, title, text)
    low_text = (text or "").lower()

    non_academic_hits = sum(
        1
        for term in ["housing", "campus map", "alumni", "donate", "athletics", "events", "news"]
        if term in low_text[:15000]
    )

    if non_academic_hits >= 3:
        return False

    academic_signal = sum(1 for term in ACADEMIC_TERMS if term in low_text[:30000])

    return score >= 6 and academic_signal >= 2


# ============================================================
# PAGE CLEANING
# ============================================================

def extract_main_content(html: str) -> Tuple[Optional[BeautifulSoup], str]:
    soup = BeautifulSoup(html, "html.parser")

    for tag in soup(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(attrs={"role": "main"})
        or soup.find("body")
    )

    if main is None:
        return None, ""

    text = clean_text(main.get_text(" ", strip=True))

    return main, text


def detect_degrees(text: str) -> List[Tuple[str, str]]:
    """Returns list of (matched_span, normalized_degree_level)."""
    results = []
    low = text.lower()

    for pattern, level in DEGREE_PATTERNS:
        if re.search(pattern, low):
            results.append((pattern, level))

    return results


def looks_like_academic_unit(text: str) -> bool:
    if is_bad_text(text):
        return False

    low = normalize_name(text)

    return any(
        term in low
        for term in ["school of", "college of", "department of", "division of"]
    )


def clean_unit_name(text: str) -> str:
    text = clean_text(text)
    text = re.sub(r"^(school|college|department|division) of\s+", "", text, flags=re.IGNORECASE)
    return text.strip()


def looks_like_program(text: str) -> bool:
    if is_bad_text(text):
        return False

    if len(text) < 4 or len(text) > 160:
        return False

    low = text.lower()

    has_degree_signal = any(re.search(pattern, low) for pattern, _ in DEGREE_PATTERNS)

    return has_degree_signal or "program" in low or "studies" in low


# ============================================================
# STRUCTURED EXTRACTION
# ============================================================

def _build_record(
    university: Dict[str, str],
    program_text: str,
    page_url: str,
    school_name: str = "",
    department_name: str = "",
) -> Optional[Dict]:

    if not looks_like_program(program_text):
        return None

    degrees = detect_degrees(program_text)
    degree_level = degrees[0][1] if degrees else "Unspecified"

    program_name = clean_text(program_text)

    return {
        "university_id": university["university_id"],
        "university_name": university["university_name"],
        "school_name": clean_unit_name(school_name) if school_name else "",
        "department_name": clean_unit_name(department_name) if department_name else "",
        "program_name": program_name,
        "degree_level": degree_level,
        "degree_name": program_name,
        "program_url": page_url,
        "source_url": page_url,
        "evidence": program_text[:200],
        "confidence": 0.6 if degrees else 0.4,
    }


def extract_from_tables(main: BeautifulSoup, page_url: str, university: Dict[str, str]) -> List[Dict]:
    records = []

    for table in main.find_all("table"):
        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])

            if not cells:
                continue

            row_text = clean_text(" ".join(c.get_text(" ", strip=True) for c in cells))

            record = _build_record(university, row_text, page_url)

            if record:
                records.append(record)

    return records


def extract_from_cards(main: BeautifulSoup, page_url: str, university: Dict[str, str]) -> List[Dict]:
    records = []

    card_selectors = [
        {"class_": re.compile(r"card|program|degree|listing", re.IGNORECASE)},
    ]

    seen_elements = set()

    for selector in card_selectors:
        for el in main.find_all(["div", "li", "article"], **selector):
            el_id = id(el)

            if el_id in seen_elements:
                continue

            seen_elements.add(el_id)

            heading = el.find(["h1", "h2", "h3", "h4"])
            text_source = heading.get_text(" ", strip=True) if heading else el.get_text(" ", strip=True)

            record = _build_record(university, clean_text(text_source), page_url)

            if record:
                records.append(record)

    return records


def extract_from_lists(main: BeautifulSoup, page_url: str, university: Dict[str, str]) -> List[Dict]:
    records = []

    for list_tag in main.find_all(["ul", "ol"]):
        for item in list_tag.find_all("li", recursive=False):
            text = clean_text(item.get_text(" ", strip=True))

            record = _build_record(university, text, page_url)

            if record:
                records.append(record)

    return records


def deduplicate_records(records: List[Dict]) -> List[Dict]:
    seen = OrderedDict()

    for record in records:
        key = (
            record["university_id"],
            normalize_name(record["program_name"]),
            record["degree_level"],
        )

        if key not in seen:
            seen[key] = record
        else:
            # keep the higher-confidence version
            if record["confidence"] > seen[key]["confidence"]:
                seen[key] = record

    return list(seen.values())


def finalize_program_records(university: Dict[str, str], records: List[Dict]) -> List[Dict]:
    finalized = []

    for i, record in enumerate(records, start=1):
        program_id = f"{university['university_id']}-PROG-{i:04d}"

        finalized.append({
            "program_id": program_id,
            "university_id": record["university_id"],
            "university_name": record["university_name"],
            "school_name": record.get("school_name", ""),
            "department_name": record.get("department_name", ""),
            "program_name": record["program_name"],
            "degree_level": record["degree_level"],
            "degree_name": record["degree_name"],
            "program_url": record["program_url"],
            "source_url": record["source_url"],
            "evidence": record["evidence"],
            "confidence": record["confidence"],
            "status": "verified" if record["confidence"] >= 0.6 else "review",
            "agent_version": AGENT_VERSION,
        })

    return finalized


# ============================================================
# MAIN PER-UNIVERSITY PIPELINE
# ============================================================

def process_university(university: Dict[str, str]) -> Tuple[List[Dict], Dict]:
    university_name = university["university_name"]
    domain = university["official_domain"]
    website = university["official_website"]

    print()
    print("=" * 70)
    print(f"{university_name}")
    print(f"Domain: {domain}")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. PRIMARY: sitemap discovery
    # --------------------------------------------------------

    sitemap_urls = sitemap_candidates(domain)
    sitemap_urls = [u for u in sitemap_urls if not is_bad_url(u)]
    ranked_sitemap = rank_candidate_pages(sitemap_urls, domain)

    candidate_pages: List[str] = ranked_sitemap[:MAX_CANDIDATE_PAGES]

    print(f"Sitemap candidates found: {len(sitemap_urls)} (using top {len(candidate_pages)})")

    # --------------------------------------------------------
    # 2. SECONDARY: bounded crawl fallback, only if sitemap is thin
    # --------------------------------------------------------

    if len(candidate_pages) < 3:
        print("Sitemap yielded too few candidates, falling back to homepage crawl...")

        crawled = crawl_candidates(domain, website or f"https://{domain}/")
        crawled = [u for u in crawled if not is_bad_url(u)]
        ranked_crawled = rank_candidate_pages(crawled, domain)

        for url in ranked_crawled:
            if url not in candidate_pages:
                candidate_pages.append(url)

            if len(candidate_pages) >= MAX_CANDIDATE_PAGES:
                break

        print(f"Crawl candidates added: {len(ranked_crawled)}")

    # Final fallback seed: homepage itself, so we always check at least
    # one real page even if both discovery methods came back empty.
    homepage = normalize_url(website or f"https://{domain}/")

    if homepage not in candidate_pages:
        candidate_pages.append(homepage)

    candidate_pages = rank_candidate_pages(candidate_pages, domain)[:MAX_CANDIDATE_PAGES]

    print(f"Candidate academic pages: {len(candidate_pages)}")

    # --------------------------------------------------------
    # 3. Fetch + parse pages
    # --------------------------------------------------------

    all_records: List[Dict] = []
    pages_checked = 0
    academic_pages = 0

    for index, page_url in enumerate(candidate_pages, start=1):
        html = fetch(page_url)

        if not html:
            continue

        pages_checked += 1

        main, main_text = extract_main_content(html)

        if main is None:
            continue

        soup_for_title = BeautifulSoup(html, "html.parser")
        title_tag = soup_for_title.find("title")
        title = clean_text(title_tag.get_text(" ", strip=True) if title_tag else "")

        if not is_academic_page(page_url, title, main_text):
            continue

        academic_pages += 1

        print(f"  [{index}] academic page: {page_url}")

        table_records = extract_from_tables(main, page_url, university)
        card_records = extract_from_cards(main, page_url, university)
        list_records = extract_from_lists(main, page_url, university)

        page_records = table_records + card_records + list_records

        all_records.extend(page_records)

        print(f"      structured records: {len(page_records)}")

    # --------------------------------------------------------
    # 4. Deduplicate + finalize
    # --------------------------------------------------------

    all_records = deduplicate_records(all_records)
    finalized = finalize_program_records(university, all_records)

    if finalized:
        status = "completed"
        reason = f"Found {len(finalized)} program-degree records from official academic pages."
    elif academic_pages == 0:
        status = "needs_review"
        reason = "Official academic pages could not be confidently identified."
    else:
        status = "no_programs_found"
        reason = "Academic pages were found, but no program-degree pair met structural validation rules."

    review = {
        "university_id": university["university_id"],
        "university_name": university["university_name"],
        "official_domain": domain,
        "official_website": website,
        "status": status,
        "reason": reason,
        "pages_checked": pages_checked,
        "programs_found": len(finalized),
        "agent_version": AGENT_VERSION,
    }

    return finalized, review


# ============================================================
# APPEND / UPSERT
# ============================================================

def upsert_university_programs(
    existing_rows: List[Dict[str, str]],
    university_id: str,
    new_rows: List[Dict],
) -> List[Dict[str, str]]:

    filtered = [row for row in existing_rows if row.get("university_id") != university_id]
    filtered.extend(new_rows)

    return filtered


# ============================================================
# MAIN
# ============================================================

def main() -> None:
    parser = argparse.ArgumentParser(description="Univora Program Discovery Agent")
    parser.add_argument("--limit", type=int, default=10, help="Number of universities to process")
    parser.add_argument("--force", action="store_true", help="Reprocess universities even if already completed")
    args = parser.parse_args()

    print("=" * 70)
    print(f"UNIVORA - PROGRAM DISCOVERY AGENT v{AGENT_VERSION}")
    print("=" * 70)
    print("Strategy: Sitemap-first, bounded-crawl fallback")
    print("Structure: Department -> Program -> Degree")
    print("LLM: OFF")
    print("Search engine dependency: OFF")
    print("=" * 70)

    universities = load_universities()
    registry = load_registry()
    programs = load_programs()
    review_rows: List[Dict] = []

    selected = universities[: args.limit]

    print(f"Mode: {'FORCE REPROCESS' if args.force else 'NORMAL'}")
    print(f"Universities available: {len(universities)}")
    print(f"Universities selected: {len(selected)}")
    print(f"Existing program rows: {len(programs)}")

    processed_count = 0
    skipped_count = 0
    completed_count = 0
    no_programs_count = 0
    needs_review_count = 0
    total_new_rows = 0

    for i, university in enumerate(selected, start=1):
        university_id = university["university_id"]

        if already_processed(university_id, registry, args.force):
            skipped_count += 1
            continue

        print(f"\n[{i}/{len(selected)}] PROCESSING")

        finalized, review = process_university(university)

        processed_count += 1
        total_new_rows += len(finalized)

        if review["status"] == "completed":
            completed_count += 1
        elif review["status"] == "no_programs_found":
            no_programs_count += 1
        else:
            needs_review_count += 1

        registry[university_id] = {
            "university_id": university_id,
            "university_name": university["university_name"],
            "status": review["status"],
            "programs_found": review["programs_found"],
            "pages_checked": review["pages_checked"],
            "last_run_agent_version": AGENT_VERSION,
        }

        programs = upsert_university_programs(programs, university_id, finalized)
        review_rows.append(review)

        save_registry(registry)
        save_programs(programs)

        if review_rows:
            save_review(review_rows)

    print()
    print("=" * 70)
    print("RUN COMPLETE")
    print("=" * 70)
    print(f"Processed this run: {processed_count}")
    print(f"Skipped by registry: {skipped_count}")
    print(f"Completed universities: {completed_count}")
    print(f"No programs found: {no_programs_count}")
    print(f"Needs review: {needs_review_count}")
    print(f"Program rows discovered this run: {total_new_rows}")
    print(f"Total program rows saved: {len(programs)}")
    print(f"Programs file: {PROGRAM_FILE}")
    print(f"Registry file: {REGISTRY_FILE}")
    print(f"Review file: {REVIEW_FILE}")
    print("=" * 70)


if __name__ == "__main__":
    main()