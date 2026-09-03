"""
Strategy:
    QS USA Universities
        ↓
    Official university domain
        ↓
    Targeted discovery of official academic/program pages
        ↓
    Main academic content only
        ↓
    Structured extraction
        ↓
    School / Department → Program → Degree
        ↓
    Persistent programs.csv

No LLM
No Ollama
No Gemini
No OpenAI
No IPEDS
No generic full-site crawling

Requirements:
    pip install requests beautifulsoup4

Run:
    python agents/program/program_discovery_agent.py --limit 4 --force

Then:
    python agents/program/program_discovery_agent.py --limit 184
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import time
from collections import OrderedDict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import (
    parse_qs,
    quote_plus,
    unquote,
    urljoin,
    urlparse,
)

import requests
from bs4 import BeautifulSoup


# ============================================================
# CONFIG
# ============================================================

AGENT_VERSION = "2.2.0"

ROOT = Path(__file__).resolve().parents[2]

UNIVERSITY_FILE = ROOT / "data" / "processed" / "university_sources.csv"

PROGRAM_DIR = ROOT / "data" / "processed"
PROGRAM_FILE = PROGRAM_DIR / "programs.csv"
REGISTRY_FILE = PROGRAM_DIR / "program_discovery_registry.json"
REVIEW_FILE = PROGRAM_DIR / "program_discovery_review.csv"

PROGRAM_DIR.mkdir(parents=True, exist_ok=True)

REQUEST_TIMEOUT = 20
SEARCH_TIMEOUT = 20

MAX_SEARCH_RESULTS_PER_QUERY = 8
MAX_CANDIDATE_PAGES = 12
MAX_PAGE_SIZE = 3_000_000

REQUEST_DELAY = 0.8

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


# ============================================================
# CONSTANTS / RULES
# ============================================================

ACADEMIC_TERMS = [
    "graduate",
    "graduate programs",
    "graduate study",
    "graduate education",
    "degree programs",
    "academic programs",
    "programs",
    "degrees",
    "masters",
    "master's",
    "doctoral",
    "doctorate",
    "phd",
    "ph.d",
    "department",
    "departments",
    "school",
    "schools",
    "college",
    "colleges",
]

PROGRAM_URL_TERMS = [
    "graduate",
    "program",
    "programs",
    "degree",
    "degrees",
    "academics",
    "academic",
    "department",
    "departments",
    "school",
    "schools",
    "college",
    "colleges",
    "doctoral",
    "phd",
    "masters",
]

BAD_URL_TERMS = [
    "admission",
    "admissions",
    "tuition",
    "financial-aid",
    "financialaid",
    "housing",
    "calendar",
    "events",
    "news",
    "blog",
    "alumni",
    "giving",
    "donate",
    "directory",
    "search",
    "login",
    "signin",
    "contact",
    "campus",
    "visit",
    "about",
    "library",
    "employment",
    "careers",
    "newsroom",
    "media",
    "athletics",
    "privacy",
    "accessibility",
    "emergency",
    "map",
]

BAD_TEXT_PATTERNS = [
    "main navigation",
    "site navigation",
    "footer menu",
    "actions menu",
    "breadcrumb",
    "campus map",
    "related sites",
    "quick links",
    "resources",
    "alumni",
    "give",
    "donate",
    "contact us",
    "apply now",
    "request information",
    "student life",
    "housing",
    "events",
    "news",
]

DEGREE_PATTERNS = [
    (
        "Doctoral",
        "PhD",
        [
            r"\bph\.?d\.?\b",
            r"\bdoctor of philosophy\b",
            r"\bdoctoral\b",
        ],
    ),
    (
        "Doctoral",
        "EdD",
        [
            r"\bed\.?d\.?\b",
            r"\bdoctor of education\b",
        ],
    ),
    (
        "Doctoral",
        "MD",
        [
            r"\bdoctor of medicine\b",
            r"\bmedical doctor\b",
        ],
    ),
    (
        "Doctoral",
        "JD",
        [
            r"\bjuris doctor\b",
            r"\bJ\.?D\.?\b",
        ],
    ),
    (
        "Doctoral",
        "DPT",
        [
            r"\bdoctor of physical therapy\b",
            r"\bD\.?P\.?T\.?\b",
        ],
    ),
    (
        "Master's",
        "MA",
        [
            r"\bmaster of arts\b",
            r"\bM\.?A\.?\b",
        ],
    ),
    (
        "Master's",
        "MS",
        [
            r"\bmaster of science\b",
            r"\bM\.?S\.?\b",
        ],
    ),
    (
        "Master's",
        "MEng",
        [
            r"\bmaster of engineering\b",
            r"\bM\.?Eng\.?\b",
        ],
    ),
    (
        "Master's",
        "MEd",
        [
            r"\bmaster of education\b",
            r"\bM\.?Ed\.?\b",
        ],
    ),
    (
        "Master's",
        "MPA",
        [
            r"\bmaster of public administration\b",
            r"\bM\.?P\.?A\.?\b",
        ],
    ),
    (
        "Master's",
        "MPP",
        [
            r"\bmaster of public policy\b",
            r"\bM\.?P\.?P\.?\b",
        ],
    ),
    (
        "Master's",
        "MBA",
        [
            r"\bmaster of business administration\b",
            r"\bM\.?B\.?A\.?\b",
        ],
    ),
    (
        "Master's",
        "MFA",
        [
            r"\bmaster of fine arts\b",
            r"\bM\.?F\.?A\.?\b",
        ],
    ),
    (
        "Master's",
        "MPH",
        [
            r"\bmaster of public health\b",
            r"\bM\.?P\.?H\.?\b",
        ],
    ),
    (
        "Master's",
        "MSW",
        [
            r"\bmaster of social work\b",
            r"\bM\.?S\.?W\.?\b",
        ],
    ),
    (
        "Bachelor's",
        "BA",
        [
            r"\bbachelor of arts\b",
            r"\bB\.?A\.?\b",
        ],
    ),
    (
        "Bachelor's",
        "BS",
        [
            r"\bbachelor of science\b",
            r"\bB\.?S\.?\b",
        ],
    ),
]

GENERIC_PROGRAM_NAMES = {
    "programs",
    "graduate programs",
    "graduate studies",
    "academics",
    "degrees",
    "degree programs",
    "departments",
    "schools",
    "colleges",
    "academic programs",
    "graduate education",
    "graduate study",
    "home",
    "about",
    "apply",
    "admissions",
    "contact",
}

GENERIC_DEPARTMENT_NAMES = {
    "menu",
    "main navigation",
    "site navigation",
    "footer menu",
    "breadcrumb",
    "explore programs",
    "campus",
    "community",
    "related sites",
    "resources",
    "academics",
    "graduate studies",
    "programs",
    "departments",
    "schools",
    "colleges",
}


# ============================================================
# HTTP
# ============================================================

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url: str) -> Optional[str]:
    """Fetch a page safely."""
    try:
        response = SESSION.get(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
        )

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


def canonical_domain(url: str) -> str:
    parsed = urlparse(url)

    host = parsed.netloc.lower().strip()

    if host.startswith("www."):
        host = host[4:]

    return host


def make_absolute(base_url: str, href: str) -> Optional[str]:
    if not href:
        return None

    href = href.strip()

    if href.startswith("#"):
        return None

    if href.startswith("mailto:"):
        return None

    if href.startswith("javascript:"):
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
                "utm_source",
                "utm_medium",
                "utm_campaign",
                "utm_term",
                "utm_content",
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
# UNIVERSITY LOADING
# ============================================================

def load_universities() -> List[Dict[str, str]]:
    """Load official university sources."""
    if not UNIVERSITY_FILE.exists():
        raise FileNotFoundError(
            f"Missing university source file:\n{UNIVERSITY_FILE}"
        )

    rows: List[Dict[str, str]] = []

    with UNIVERSITY_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            university_id = clean_text(row.get("university_id", ""))
            university_name = clean_text(row.get("university_name", ""))
            domain = clean_text(row.get("official_domain", ""))
            website = clean_text(row.get("university_website", ""))

            if not university_id:
                continue

            if not domain and website:
                domain = canonical_domain(website)

            if not website and domain:
                website = f"https://{domain}/"

            rows.append(
                {
                    "university_id": university_id,
                    "university_name": university_name,
                    "official_domain": domain,
                    "official_website": website,
                }
            )

    return rows


# ============================================================
# REGISTRY
# ============================================================

def load_registry() -> Dict[str, Dict]:
    if not REGISTRY_FILE.exists():
        return {}

    try:
        with REGISTRY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data

    except (json.JSONDecodeError, OSError):
        pass

    return {}


def save_registry(registry: Dict[str, Dict]) -> None:
    temp = REGISTRY_FILE.with_suffix(".tmp")

    with temp.open("w", encoding="utf-8") as f:
        json.dump(
            registry,
            f,
            indent=2,
            ensure_ascii=False,
        )

    temp.replace(REGISTRY_FILE)


def already_processed(
    registry: Dict[str, Dict],
    university_id: str,
) -> bool:
    entry = registry.get(university_id)

    if not entry:
        return False

    return entry.get("status") in {
        "completed",
        "needs_review",
        "no_programs_found",
    }


# ============================================================
# PROGRAM FILE
# ============================================================

def load_programs() -> List[Dict[str, str]]:
    if not PROGRAM_FILE.exists():
        return []

    rows: List[Dict[str, str]] = []

    with PROGRAM_FILE.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        reader = csv.DictReader(f)

        for row in reader:
            rows.append(dict(row))

    return rows


def save_programs(rows: List[Dict[str, str]]) -> None:
    temp = PROGRAM_FILE.with_suffix(".tmp")

    with temp.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=PROGRAM_FIELDS,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row.get(field, "")
                    for field in PROGRAM_FIELDS
                }
            )

    temp.replace(PROGRAM_FILE)


def save_review(rows: List[Dict[str, str]]) -> None:
    temp = REVIEW_FILE.with_suffix(".tmp")

    with temp.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=REVIEW_FIELDS,
            extrasaction="ignore",
        )

        writer.writeheader()

        for row in rows:
            writer.writerow(
                {
                    field: row.get(field, "")
                    for field in REVIEW_FIELDS
                }
            )

    temp.replace(REVIEW_FILE)


# ============================================================
# SEARCH ENGINE DISCOVERY
# ============================================================

def extract_ddg_links(html: str, domain: str) -> List[str]:
    """
    Extract real URLs from DuckDuckGo HTML results.
    Only official-domain results are retained.
    """
    soup = BeautifulSoup(html, "html.parser")
    links: List[str] = []

    for anchor in soup.select("a.result__a, a[href]"):
        href = anchor.get("href")

        if not href:
            continue

        href = unquote(href)

        # Direct official links.
        absolute = make_absolute("https://duckduckgo.com", href)

        if not absolute:
            continue

        parsed = urlparse(absolute)

        if parsed.netloc and "duckduckgo.com" not in parsed.netloc:
            if same_domain(absolute, domain):
                links.append(normalize_url(absolute))

            continue

        # DDG redirect format.
        if "uddg=" in href:
            try:
                target = parse_qs(urlparse(href).query).get("uddg", [])

                if target:
                    target_url = unquote(target[0])

                    if same_domain(target_url, domain):
                        links.append(normalize_url(target_url))

            except Exception:
                pass

    return list(OrderedDict.fromkeys(links))


def search_official_pages(
    university_name: str,
    domain: str,
) -> List[str]:
    """
    Targeted search restricted to the university's official domain.

    This is NOT generic crawling.
    We ask search engines to locate academic pages.
    """

    queries = [
        f'site:{domain} graduate programs',
        f'site:{domain} graduate degree programs',
        f'site:{domain} academic programs graduate',
        f'site:{domain} departments graduate programs',
        f'site:{domain} schools departments programs',
        f"site:{domain} master's phd programs",
        f'site:{domain} graduate program directory',
    ]

    candidates: List[str] = []

    for query in queries:
        try:
            search_url = (
                "https://html.duckduckgo.com/html/?q="
                + quote_plus(query)
            )

            html = SESSION.get(
                search_url,
                timeout=SEARCH_TIMEOUT,
                headers=HEADERS,
            ).text

            links = extract_ddg_links(
                html,
                domain,
            )

            for link in links:
                if same_domain(link, domain):
                    candidates.append(link)

                if len(candidates) >= MAX_CANDIDATE_PAGES:
                    break

            if len(candidates) >= MAX_CANDIDATE_PAGES:
                break

        except requests.RequestException:
            continue

        time.sleep(0.5)

    # Homepage as a final seed.
    homepage = f"https://{domain}/"

    if homepage not in candidates:
        candidates.append(homepage)

    candidates = list(
        OrderedDict.fromkeys(
            normalize_url(url)
            for url in candidates
            if same_domain(url, domain)
            and not is_bad_url(url)
        )
    )

    return rank_candidate_pages(
        candidates,
        university_name,
        domain,
    )[:MAX_CANDIDATE_PAGES]


# ============================================================
# OPTIONAL SITEMAP DISCOVERY
# ============================================================

def sitemap_candidates(domain: str) -> List[str]:
    """
    Read robots.txt / sitemap.xml only.
    No broad site crawl.
    """
    urls: List[str] = []

    robots_url = f"https://{domain}/robots.txt"
    robots_html = fetch(robots_url)

    if robots_html:
        for line in robots_html.splitlines():
            if line.lower().startswith("sitemap:"):
                sitemap_url = line.split(":", 1)[1].strip()

                if sitemap_url.startswith("http"):
                    urls.append(sitemap_url)

    urls.append(f"https://{domain}/sitemap.xml")

    discovered: List[str] = []

    for sitemap_url in list(OrderedDict.fromkeys(urls)):
        try:
            response = SESSION.get(
                sitemap_url,
                timeout=REQUEST_TIMEOUT,
                headers=HEADERS,
            )

            if response.status_code >= 400:
                continue

            text = response.text

            for match in re.findall(
                r"<loc>\s*(.*?)\s*</loc>",
                text,
                flags=re.IGNORECASE | re.DOTALL,
            ):
                candidate = clean_text(match)

                if (
                    candidate.startswith("http")
                    and same_domain(candidate, domain)
                ):
                    discovered.append(
                        normalize_url(candidate)
                    )

        except requests.RequestException:
            continue

    return list(
        OrderedDict.fromkeys(discovered)
    )


# ============================================================
# CANDIDATE RANKING
# ============================================================

def page_keyword_score(
    url: str,
    title: str,
    text: str = "",
) -> int:

    score = 0

    low_url = url.lower()
    low_title = title.lower()
    low_text = text.lower()[:30000]

    for term in PROGRAM_URL_TERMS:
        if term in low_url:
            score += 5

    for term in ACADEMIC_TERMS:
        if term in low_title:
            score += 8

    for term in ACADEMIC_TERMS:
        if term in low_text:
            score += 1

    if "graduate" in low_url:
        score += 15

    if "program" in low_url:
        score += 12

    if "degree" in low_url:
        score += 10

    if "department" in low_url:
        score += 8

    if "academic" in low_url:
        score += 8

    if is_bad_url(url):
        score -= 30

    return score


def rank_candidate_pages(
    urls: List[str],
    university_name: str,
    domain: str,
) -> List[str]:

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

    scored.sort(
        key=lambda x: (
            -x[0],
            len(x[1]),
        )
    )

    return [
        url
        for _, url in scored
    ]


# ============================================================
# PAGE CLEANING
# ============================================================

def extract_main_content(
    html: str,
) -> Tuple[Optional[BeautifulSoup], str]:

    soup = BeautifulSoup(html, "html.parser")

    # Remove obvious non-content sections.
    for tag in soup([
        "script",
        "style",
        "noscript",
        "svg",
        "iframe",
        "canvas",
        "form",
        "header",
        "nav",
        "footer",
        "aside",
    ]):
        tag.decompose()

    main = (
        soup.find("main")
        or soup.find("article")
        or soup.find(
            "div",
            attrs={
                "role": "main"
            }
        )
    )

    if main is None:
        # Look for semantic containers.
        for selector in [
            '[id*="content"]',
            '[class*="content"]',
            '[class*="main"]',
            '[class*="academic"]',
        ]:
            main = soup.select_one(selector)

            if main:
                break

    if main is None:
        main = soup.body

    if main is None:
        return None, ""

    text = normalize_space(main.get_text(" ", strip=True))

    return main, text


# ============================================================
# DEGREE DETECTION
# ============================================================

def detect_degrees(text: str) -> List[Tuple[str, str]]:
    """
    Degree detection is only used when the degree text appears
    in the SAME structural block as the program.

    We never assign a page-level degree to every program.
    """

    found: List[Tuple[str, str]] = []

    text = clean_text(text)

    for level, degree_name, patterns in DEGREE_PATTERNS:
        for pattern in patterns:
            if re.search(
                pattern,
                text,
                flags=re.IGNORECASE,
            ):
                found.append(
                    (
                        level,
                        degree_name,
                    )
                )
                break

    return list(OrderedDict.fromkeys(found))


# ============================================================
# ACADEMIC UNIT DETECTION
# ============================================================

def looks_like_academic_unit(text: str) -> bool:
    text = clean_text(text)

    if len(text) < 3 or len(text) > 180:
        return False

    if is_bad_text(text):
        return False

    normalized = normalize_name(text)

    unit_markers = [
        "department",
        "school",
        "college",
        "faculty",
        "institute",
        "division",
        "program in",
        "studies",
        "engineering",
        "science",
        "arts",
        "business",
        "education",
        "medicine",
        "law",
        "public health",
    ]

    return any(
        marker in normalized
        for marker in unit_markers
    )


def clean_unit_name(text: str) -> str:
    text = clean_text(text)

    text = re.sub(
        r"^(department|dept\.?)\s*(of|in)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    return text.strip(" -:|")


# ============================================================
# PROGRAM VALIDATION
# ============================================================

def looks_like_program(text: str) -> bool:
    text = clean_text(text)

    if not text:
        return False

    if len(text) < 3 or len(text) > 180:
        return False

    if is_bad_text(text):
        return False

    normalized = normalize_name(text)

    bad_exact = {
        "admissions",
        "requirements",
        "curriculum",
        "faculty",
        "people",
        "contact",
        "overview",
        "about",
        "news",
        "events",
        "research",
        "academics",
        "courses",
        "apply",
        "application",
        "tuition",
        "financial aid",
        "student resources",
        "career services",
    }

    if normalized in bad_exact:
        return False

    # Obvious navigation strings.
    if normalized.startswith("click here"):
        return False

    if normalized.startswith("learn more"):
        return False

    # URLs / emails are not programs.
    if "http://" in text.lower():
        return False

    if "https://" in text.lower():
        return False

    if "@" in text:
        return False

    # Require meaningful alphabetic content.
    alpha_count = len(re.findall(r"[A-Za-z]", text))

    if alpha_count < 4:
        return False

    return True


# ============================================================
# STRUCTURAL EXTRACTION
# ============================================================

def nearby_heading(element) -> Optional[str]:
    """
    Find the closest meaningful heading ABOVE an element.
    """
    for previous in element.find_all_previous(
        ["h1", "h2", "h3", "h4", "h5", "h6"],
        limit=8,
    ):
        text = clean_text(previous.get_text(" ", strip=True))

        if looks_like_academic_unit(text):
            return clean_unit_name(text)

    return None


def extract_from_tables(
    main,
    source_url: str,
) -> List[Dict]:

    results: List[Dict] = []

    for table in main.find_all("table"):

        rows = table.find_all("tr")

        if not rows:
            continue

        headers: List[str] = []

        first_cells = rows[0].find_all(
            ["th", "td"]
        )

        candidate_headers = [
            clean_text(cell.get_text(" ", strip=True))
            for cell in first_cells
        ]

        header_lower = [
            normalize_name(h)
            for h in candidate_headers
        ]

        has_program_column = any(
            "program" in h
            or "degree" in h
            or "major" in h
            or "field of study" in h
            or "area of study" in h
            for h in header_lower
        )

        if has_program_column:
            headers = candidate_headers

        for row in rows[1:]:

            cells = row.find_all(["td", "th"])

            if not cells:
                continue

            values = [
                clean_text(
                    cell.get_text(
                        " ",
                        strip=True,
                    )
                )
                for cell in cells
            ]

            if not any(values):
                continue

            row_text = " | ".join(values)

            department = nearby_heading(row)

            program = None
            degrees: List[Tuple[str, str]] = []

            for index, value in enumerate(values):

                low = normalize_name(
                    headers[index]
                    if index < len(headers)
                    else ""
                )

                if (
                    "program" in low
                    or "major" in low
                    or "field of study" in low
                    or "area of study" in low
                ):
                    if looks_like_program(value):
                        program = value

                if "degree" in low:
                    degrees.extend(
                        detect_degrees(value)
                    )

            if program is None:
                # Look for a link in the row whose text resembles
                # an actual academic program.
                links = row.find_all("a")

                for link in links:
                    link_text = clean_text(
                        link.get_text(
                            " ",
                            strip=True,
                        )
                    )

                    if looks_like_program(link_text):
                        program = link_text
                        break

            if program is None:
                continue

            if not degrees:
                degrees = detect_degrees(row_text)

            # Critical rule:
            # no degree = do not fabricate.
            if not degrees:
                continue

            program_url = source_url

            for link in row.find_all("a"):
                link_text = clean_text(
                    link.get_text(
                        " ",
                        strip=True,
                    )
                )

                if normalize_name(link_text) == normalize_name(program):
                    href = link.get("href")

                    absolute = make_absolute(
                        source_url,
                        href or "",
                    )

                    if absolute:
                        program_url = normalize_url(
                            absolute
                        )

                    break

            for degree_level, degree_name in degrees:
                results.append(
                    {
                        "school_name": "",
                        "department_name": department or "",
                        "program_name": program,
                        "degree_level": degree_level,
                        "degree_name": degree_name,
                        "program_url": program_url,
                        "source_url": source_url,
                        "evidence": row_text[:1000],
                        "confidence": "high",
                    }
                )

    return results


def extract_from_cards(
    main,
    source_url: str,
) -> List[Dict]:

    results: List[Dict] = []

    # Cards are often represented by article, li, or div elements.
    containers = main.find_all(
        ["article", "li"]
    )

    for container in containers:

        text = clean_text(
            container.get_text(
                " ",
                strip=True,
            )
        )

        if len(text) < 10 or len(text) > 1200:
            continue

        degrees = detect_degrees(text)

        # Important:
        # The degree must be in this same container.
        if not degrees:
            continue

        links = container.find_all("a")

        if not links:
            continue

        program = None
        program_url = source_url

        for link in links:

            link_text = clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            href = link.get("href")

            if not looks_like_program(link_text):
                continue

            if href and is_bad_url(href):
                continue

            if (
                len(link_text) <= 140
                and link_text not in {
                    "Learn More",
                    "Read More",
                    "View",
                    "Details",
                    "Explore",
                }
            ):
                program = link_text

                absolute = make_absolute(
                    source_url,
                    href or "",
                )

                if absolute:
                    program_url = normalize_url(
                        absolute
                    )

                break

        if not program:
            continue

        department = nearby_heading(container)

        for degree_level, degree_name in degrees:
            results.append(
                {
                    "school_name": "",
                    "department_name": department or "",
                    "program_name": program,
                    "degree_level": degree_level,
                    "degree_name": degree_name,
                    "program_url": program_url,
                    "source_url": source_url,
                    "evidence": text[:1000],
                    "confidence": "high",
                }
            )

    return results


def extract_from_lists(
    main,
    source_url: str,
) -> List[Dict]:

    results: List[Dict] = []

    for element in main.find_all(
        ["div", "section"]
    ):

        text = clean_text(
            element.get_text(
                " ",
                strip=True,
            )
        )

        if len(text) < 10 or len(text) > 1500:
            continue

        degrees = detect_degrees(text)

        if not degrees:
            continue

        links = element.find_all("a")

        good_links = []

        for link in links:
            link_text = clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            if looks_like_program(link_text):
                good_links.append(link)

        # Avoid large navigation blocks.
        if len(good_links) == 0:
            continue

        if len(good_links) > 15:
            continue

        for link in good_links:

            program = clean_text(
                link.get_text(
                    " ",
                    strip=True,
                )
            )

            href = link.get("href")

            if not href:
                continue

            if is_bad_url(href):
                continue

            program_url = make_absolute(
                source_url,
                href,
            )

            if not program_url:
                continue

            program_url = normalize_url(
                program_url
            )

            department = nearby_heading(
                element
            )

            for degree_level, degree_name in degrees:
                results.append(
                    {
                        "school_name": "",
                        "department_name": department or "",
                        "program_name": program,
                        "degree_level": degree_level,
                        "degree_name": degree_name,
                        "program_url": program_url,
                        "source_url": source_url,
                        "evidence": text[:1000],
                        "confidence": "medium",
                    }
                )

    return results


# ============================================================
# SEMANTIC ACADEMIC PAGE CHECK
# ============================================================

def is_academic_page(
    url: str,
    title: str,
    text: str,
) -> bool:

    score = page_keyword_score(
        url,
        title,
        text,
    )

    low_text = text.lower()

    # Reject obviously non-academic pages.
    if sum(
        1
        for term in [
            "housing",
            "campus map",
            "alumni",
            "donate",
            "athletics",
            "events",
            "news",
        ]
        if term in low_text[:15000]
    ) >= 3:
        return False

    academic_signal = sum(
        1
        for term in ACADEMIC_TERMS
        if term in low_text[:30000]
    )

    return score >= 8 and academic_signal >= 2


# ============================================================
# RECORD CLEANING
# ============================================================

def deduplicate_records(
    records: List[Dict],
) -> List[Dict]:

    unique: OrderedDict[str, Dict] = OrderedDict()

    for record in records:

        key = "|".join(
            [
                normalize_name(
                    record.get("university_name", "")
                ),
                normalize_name(
                    record.get("school_name", "")
                ),
                normalize_name(
                    record.get("department_name", "")
                ),
                normalize_name(
                    record.get("program_name", "")
                ),
                normalize_name(
                    record.get("degree_name", "")
                ),
            ]
        )

        if not key:
            continue

        if key not in unique:
            unique[key] = record

    return list(unique.values())


def finalize_program_records(
    university: Dict[str, str],
    records: List[Dict],
) -> List[Dict]:

    finalized: List[Dict] = []

    for record in records:

        program_name = clean_text(
            record.get("program_name", "")
        )

        department_name = clean_text(
            record.get("department_name", "")
        )

        school_name = clean_text(
            record.get("school_name", "")
        )

        degree_level = clean_text(
            record.get("degree_level", "")
        )

        degree_name = clean_text(
            record.get("degree_name", "")
        )

        if not program_name:
            continue

        if not looks_like_program(program_name):
            continue

        if not degree_name:
            continue

        # Remove garbage department labels.
        if normalize_name(
            department_name
        ) in GENERIC_DEPARTMENT_NAMES:
            department_name = ""

        # Program ID is deterministic.
        base = "|".join(
            [
                university["university_id"],
                school_name,
                department_name,
                program_name,
                degree_name,
            ]
        )

        import hashlib

        program_id = (
            "PROG-"
            + hashlib.sha1(
                base.encode(
                    "utf-8"
                )
            ).hexdigest()[:16]
        )

        finalized.append(
            {
                "program_id": program_id,
                "university_id": university[
                    "university_id"
                ],
                "university_name": university[
                    "university_name"
                ],
                "school_name": school_name,
                "department_name": department_name,
                "program_name": program_name,
                "degree_level": degree_level,
                "degree_name": degree_name,
                "program_url": clean_text(
                    record.get(
                        "program_url",
                        "",
                    )
                ),
                "source_url": clean_text(
                    record.get(
                        "source_url",
                        "",
                    )
                ),
                "evidence": clean_text(
                    record.get(
                        "evidence",
                        "",
                    )
                )[:1000],
                "confidence": record.get(
                    "confidence",
                    "medium",
                ),
                "status": "verified",
                "agent_version": AGENT_VERSION,
            }
        )

    return deduplicate_records(
        finalized
    )


# ============================================================
# UNIVERSITY PROCESSING
# ============================================================

def process_university(
    university: Dict[str, str],
) -> Tuple[List[Dict], Dict]:

    university_name = university[
        "university_name"
    ]

    domain = university[
        "official_domain"
    ]

    website = university[
        "official_website"
    ]

    print()
    print("=" * 70)
    print(f"{university_name}")
    print(f"Domain: {domain}")
    print("=" * 70)

    # --------------------------------------------------------
    # 1. Search official pages
    # --------------------------------------------------------

    candidate_pages = search_official_pages(
        university_name,
        domain,
    )

    # --------------------------------------------------------
    # 2. Add sitemap academic candidates
    #    ONLY when search results are weak.
    # --------------------------------------------------------

    if len(candidate_pages) < 3:

        sitemap_urls = sitemap_candidates(
            domain
        )

        sitemap_urls = [
            url
            for url in sitemap_urls
            if not is_bad_url(url)
        ]

        sitemap_urls = rank_candidate_pages(
            sitemap_urls,
            university_name,
            domain,
        )

        for url in sitemap_urls:

            if url not in candidate_pages:
                candidate_pages.append(url)

            if len(candidate_pages) >= MAX_CANDIDATE_PAGES:
                break

    candidate_pages = rank_candidate_pages(
        candidate_pages,
        university_name,
        domain,
    )[:MAX_CANDIDATE_PAGES]

    print(
        f"Candidate academic pages: "
        f"{len(candidate_pages)}"
    )

    # --------------------------------------------------------
    # 3. Fetch + parse pages
    # --------------------------------------------------------

    all_records: List[Dict] = []

    pages_checked = 0
    academic_pages = 0

    for index, page_url in enumerate(
        candidate_pages,
        start=1,
    ):

        html = fetch(page_url)

        if not html:
            continue

        pages_checked += 1

        main, main_text = extract_main_content(
            html
        )

        if main is None:
            continue

        soup_for_title = BeautifulSoup(
            html,
            "html.parser",
        )

        title_tag = soup_for_title.find("title")

        title = clean_text(
            title_tag.get_text(
                " ",
                strip=True,
            )
            if title_tag
            else ""
        )

        if not is_academic_page(
            page_url,
            title,
            main_text,
        ):
            continue

        academic_pages += 1

        print(
            f"  [{index}] academic page:"
            f" {page_url}"
        )

        # Structured extraction first.
        table_records = extract_from_tables(
            main,
            page_url,
        )

        card_records = extract_from_cards(
            main,
            page_url,
        )

        list_records = extract_from_lists(
            main,
            page_url,
        )

        page_records = (
            table_records
            + card_records
            + list_records
        )

        all_records.extend(
            page_records
        )

        print(
            f"      structured records: "
            f"{len(page_records)}"
        )

    # --------------------------------------------------------
    # 4. Deduplicate
    # --------------------------------------------------------

    all_records = deduplicate_records(
        all_records
    )

    finalized = finalize_program_records(
        university,
        all_records,
    )

    # --------------------------------------------------------
    # Review status
    # --------------------------------------------------------

    if finalized:

        status = "completed"

        reason = (
            f"Found {len(finalized)} "
            "program-degree records from "
            "official academic pages."
        )

    elif academic_pages == 0:

        status = "needs_review"

        reason = (
            "Official academic pages could not "
            "be confidently identified."
        )

    else:

        status = "no_programs_found"

        reason = (
            "Academic pages were found, but no "
            "program-degree pair met structural "
            "validation rules."
        )

    review = {
        "university_id": university[
            "university_id"
        ],
        "university_name": university[
            "university_name"
        ],
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
    existing: List[Dict],
    new_rows: List[Dict],
    university_id: str,
) -> List[Dict]:

    kept = [
        row
        for row in existing
        if row.get("university_id")
        != university_id
    ]

    combined = kept + new_rows

    return deduplicate_records(
        combined
    )


# ============================================================
# MAIN
# ============================================================

def main() -> None:

    parser = argparse.ArgumentParser(
        description="Univora Program Discovery Agent v2.2.0"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=184,
        help="Number of universities to process.",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Reprocess already completed universities.",
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # Banner
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print(
        "UNIVORA - PROGRAM DISCOVERY AGENT "
        f"v{AGENT_VERSION}"
    )
    print("=" * 70)
    print("Strategy: Official University Pages")
    print("Structure: Department -> Program -> Degree")
    print("LLM: OFF")
    print("Ollama: OFF")
    print("Gemini: OFF")
    print("OpenAI: OFF")
    print("IPEDS: OFF")
    print("=" * 70)

    # --------------------------------------------------------
    # Load data
    # --------------------------------------------------------

    universities = load_universities()
    registry = load_registry()
    existing_programs = load_programs()

    selected = universities[
        :args.limit
    ]

    if args.force:
        print("Mode: FORCE REPROCESS")
    else:
        print("Mode: PERSISTENT SKIP")

    print(
        f"Universities available: "
        f"{len(universities)}"
    )

    print(
        f"Universities selected: "
        f"{len(selected)}"
    )

    print(
        f"Existing program rows: "
        f"{len(existing_programs)}"
    )

    # --------------------------------------------------------
    # Summary counters
    # --------------------------------------------------------

    processed = 0
    skipped = 0
    completed = 0
    needs_review = 0
    no_programs = 0
    total_programs_added = 0

    review_rows: List[Dict] = []

    # --------------------------------------------------------
    # Process
    # --------------------------------------------------------

    for position, university in enumerate(
        selected,
        start=1,
    ):

        university_id = university[
            "university_id"
        ]

        university_name = university[
            "university_name"
        ]

        if (
            not args.force
            and already_processed(
                registry,
                university_id,
            )
        ):
            skipped += 1

            print()
            print(
                f"[{position}/{len(selected)}] "
                f"SKIP: {university_name}"
            )

            continue

        print()
        print(
            f"[{position}/{len(selected)}] "
            f"PROCESSING"
        )

        try:

            program_rows, review = process_university(
                university
            )

            existing_programs = (
                upsert_university_programs(
                    existing_programs,
                    program_rows,
                    university_id,
                )
            )

            # Save immediately after every university.
            save_programs(
                existing_programs
            )

            review_rows.append(
                review
            )

            registry[
                university_id
            ] = {
                "university_id": university_id,
                "university_name": university_name,
                "status": review["status"],
                "programs_found": review[
                    "programs_found"
                ],
                "pages_checked": review[
                    "pages_checked"
                ],
                "last_run_agent_version": AGENT_VERSION,
            }

            save_registry(
                registry
            )

            processed += 1
            total_programs_added += len(
                program_rows
            )

            if review["status"] == "completed":
                completed += 1

            elif review["status"] == "needs_review":
                needs_review += 1

            else:
                no_programs += 1

            print()
            print(
                f"  Programs found: "
                f"{len(program_rows)}"
            )

            print(
                f"  Status: "
                f"{review['status']}"
            )

        except Exception as exc:

            processed += 1
            needs_review += 1

            error_review = {
                "university_id": university_id,
                "university_name": university_name,
                "official_domain": university[
                    "official_domain"
                ],
                "official_website": university[
                    "official_website"
                ],
                "status": "needs_review",
                "reason": (
                    "Runtime error: "
                    + str(exc)
                ),
                "pages_checked": 0,
                "programs_found": 0,
                "agent_version": AGENT_VERSION,
            }

            review_rows.append(
                error_review
            )

            registry[
                university_id
            ] = {
                "university_id": university_id,
                "university_name": university_name,
                "status": "needs_review",
                "programs_found": 0,
                "pages_checked": 0,
                "last_run_agent_version": AGENT_VERSION,
                "error": str(exc),
            }

            save_registry(
                registry
            )

            print(
                f"  ERROR: {exc}"
            )

    # --------------------------------------------------------
    # Save review
    # --------------------------------------------------------

    if review_rows:
        save_review(
            review_rows
        )

    # --------------------------------------------------------
    # Final report
    # --------------------------------------------------------

    print()
    print("=" * 70)
    print("RUN COMPLETE")
    print("=" * 70)

    print(
        f"Processed this run: "
        f"{processed}"
    )

    print(
        f"Skipped by registry: "
        f"{skipped}"
    )

    print(
        f"Completed universities: "
        f"{completed}"
    )

    print(
        f"No programs found: "
        f"{no_programs}"
    )

    print(
        f"Needs review: "
        f"{needs_review}"
    )

    print(
        f"Program rows discovered this run: "
        f"{total_programs_added}"
    )

    print(
        f"Total program rows saved: "
        f"{len(existing_programs)}"
    )

    print()
    print(
        f"Programs file: "
        f"{PROGRAM_FILE}"
    )

    print(
        f"Registry file: "
        f"{REGISTRY_FILE}"
    )

    print(
        f"Review file: "
        f"{REVIEW_FILE}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()