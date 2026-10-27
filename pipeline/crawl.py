"""Crawl a news URL and extract the article: title, sapo, body text, publish date.

Strategies, in order, each checked for quality before it is accepted:
  1. JSON-LD NewsArticle.articleBody
  2. Next.js / Nuxt embedded state (JS-rendered sites)
  3. trafilatura (precision mode, then recall mode)
  4. the page's AMP version
  5. text-based PDF attachment (disclosure pages)
A result that fails every check is returned with status "needs_manual" and a
reason, never with somebody else's text.
"""

from __future__ import annotations

import html as htmllib
import io
import json
import re
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from urllib.parse import urljoin, urlparse

import httpx
import trafilatura

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0.0.0 Safari/537.36")
HEADERS = {
    "User-Agent": UA,
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "vi-VN,vi;q=0.9,en;q=0.7",
    "Cache-Control": "no-cache",
}
RETRY_STATUS = {408, 425, 429, 500, 502, 503, 504}
MIN_CHARS = 400

STOPWORDS = set("""của và các cho với trong từ được này đến một những không khi theo tại về là có đã sẽ hơn sau
trước năm tháng ngày đồng tỷ triệu nghìn cổ phiếu đông công ty thời gian mới bán mua tin tức the and for""".split())
BOILERPLATE = re.compile(
    r"^(xem thêm|tin liên quan|bài liên quan|đọc thêm|>>|tags?:|từ khóa|chia sẻ|theo dõi .* trên|"
    r"(videos? )?mới nhất$|đọc nhiều( nhất)?$|tin nổi bật$|cùng chuyên mục$|"
    r"bạn đọc .*|mời quý độc giả|© |copyright|liên hệ quảng cáo|ảnh:|nguồn:\s*$)", re.IGNORECASE)


@dataclass
class CrawlResult:
    url: str
    status: str = "failed"                 # ok | needs_manual | failed
    final_url: str = ""
    title: str = ""
    sapo: str = ""
    text: str = ""
    published_at: date | None = None
    method: str = ""
    error: str = ""
    attachments: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def to_json(self) -> str:
        d = asdict(self)
        d["published_at"] = self.published_at.isoformat() if self.published_at else None
        return json.dumps(d, ensure_ascii=False, indent=1)

    @classmethod
    def from_json(cls, raw: str) -> "CrawlResult":
        d = json.loads(raw)
        d["published_at"] = date.fromisoformat(d["published_at"]) if d.get("published_at") else None
        return cls(**d)


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

def http_get(url: str, *, retries: int = 3, timeout: float = 25.0) -> httpx.Response:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            with httpx.Client(headers=HEADERS, timeout=timeout, follow_redirects=True, http2=False) as c:
                resp = c.get(url)
            if resp.status_code in RETRY_STATUS and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            return resp
        except (httpx.TransportError, httpx.DecodingError) as exc:
            last = exc
            time.sleep(1.5 * (attempt + 1))
    raise last or RuntimeError("request failed")


def decode(resp: httpx.Response) -> str:
    """Decode HTML, trusting a <meta charset> over a wrong/missing HTTP header."""
    raw = resp.content
    m = re.search(rb'<meta[^>]+charset=["\']?([\w-]+)', raw[:4000], re.IGNORECASE)
    for enc in [m.group(1).decode() if m else None, resp.encoding, "utf-8"]:
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (LookupError, UnicodeDecodeError):
            continue
    return raw.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------

def drop_link_lists(text: str, title: str) -> str:
    """Remove runs of >=3 '- headline' lines that share no word with the article title (related-link lists)."""
    words = keywords(title)
    lines, out, run = text.splitlines(), [], []
    for line in lines + [""]:
        if line.startswith("- ") and len(line) < 200:
            run.append(line)
            continue
        related = sum(len(keywords(r) & words) >= 2 for r in run)
        if run and not (len(run) >= 3 and related * 2 < len(run)):
            out.extend(run)
        run = []
        out.append(line)
    return "\n".join(out[:-1]).strip()


def clean(text: str) -> str:
    text = unicodedata.normalize("NFC", htmllib.unescape(text)).replace("\xa0", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if not line or BOILERPLATE.match(line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def keywords(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", unicodedata.normalize("NFC", text).casefold())
            if len(w) > 1 and w not in STOPWORDS and not w.isdigit()}


def title_overlap(text: str, title: str) -> float:
    words = keywords(re.split(r"\s[|\-–]\s", title)[0])
    return len(words & keywords(text[:2000])) / len(words) if words else 1.0


def ascii_fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.replace("đ", "d").replace("Đ", "D"))
    return "".join(c for c in text if not unicodedata.combining(c)).casefold()


def looks_like_code(text: str) -> bool:
    if "_next/static" in text or "function(" in text or '["$"' in text or text.count('":') > 20:
        return True
    code_chars = sum(text.count(c) for c in "{}[]<>\\=;")
    return code_chars / max(len(text), 1) > 0.015


def looks_like_listing(text: str) -> bool:
    """Teaser lists ("...") from sidebars: many short lines ending in an ellipsis."""
    lines = [l for l in text.splitlines() if l.strip()]
    teaser = sum(l.rstrip().endswith(("...", "…")) for l in lines)
    return len(lines) >= 4 and teaser / len(lines) > 0.4


def quality(text: str, titles: list[str], sapo: str = "") -> str:
    """'' if acceptable, else the reason it is not."""
    if len(text) < MIN_CHARS:
        return f"nội dung quá ngắn ({len(text)} ký tự)"
    if looks_like_code(text):
        return "nội dung là mã nguồn trang, không phải bài"
    if looks_like_listing(text):
        return "nội dung là danh sách tin, không phải bài"
    if titles and max(title_overlap(f"{sapo}\n{text}", t) for t in titles) < 0.35:
        return "nội dung không khớp tiêu đề"
    return ""


# ---------------------------------------------------------------------------
# metadata
# ---------------------------------------------------------------------------

META_DATE = re.compile(
    r'<meta[^>]+(?:property|name|itemprop)=["\'](?:article:published_time|datePublished|pubdate|'
    r'og:published_time|publishdate|date|dc.date.issued)["\'][^>]*content=["\']([^"\']+)'
    r'|<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name|itemprop)=["\'](?:article:published_time|'
    r'datePublished|pubdate|og:published_time|publishdate)["\']', re.IGNORECASE)
VN_DATE = re.compile(r"\b(\d{1,2})[/-](\d{1,2})[/-](20\d{2})\b")


def parse_date(raw: str) -> date | None:
    raw = raw.strip()
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")[:25]).date()
    except ValueError:
        pass
    if m := re.match(r"(\d{4})-(\d{2})-(\d{2})", raw):
        return date(int(m[1]), int(m[2]), int(m[3]))
    if m := VN_DATE.search(raw):
        try:
            return date(int(m[3]), int(m[2]), int(m[1]))
        except ValueError:
            return None
    return None


def published_date(html: str, jsonld: list[dict], url: str) -> date | None:
    candidates: list[str] = [d.get("datePublished", "") for d in jsonld]
    candidates += [a or b for a, b in META_DATE.findall(html)]
    meta = trafilatura.extract_metadata(html)
    if meta and meta.date:
        candidates.append(meta.date)
    for raw in candidates:
        if raw and (d := parse_date(raw)) and 2015 <= d.year <= date.today().year + 1:
            return d
    # cafef/cafebiz-style ids: ...-188261021093213162.chn -> 26-10-21
    if m := re.search(r"-1\d{2}(\d{2})(\d{2})(\d{2})\d{6,}\.chn", url):
        try:
            return date(2000 + int(m[1]), int(m[2]), int(m[3]))
        except ValueError:
            pass
    return None


def page_title(html: str, jsonld: list[dict]) -> str:
    for d in jsonld:
        if d.get("headline"):
            return clean(d["headline"])
    if m := re.search(r'<meta[^>]+property=["\']og:title["\'][^>]*content=["\']([^"\']+)', html, re.IGNORECASE):
        return clean(m.group(1))
    if m := re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL):
        return clean(m.group(1))
    return ""


def page_sapo(html: str, jsonld: list[dict]) -> str:
    for d in jsonld:
        if d.get("description"):
            return clean(d["description"])
    if m := re.search(r'<meta[^>]+(?:name|property)=["\'](?:description|og:description)["\'][^>]*content=["\']([^"\']+)',
                      html, re.IGNORECASE):
        return clean(m.group(1))
    return ""


# ---------------------------------------------------------------------------
# extraction strategies
# ---------------------------------------------------------------------------

def jsonld_objects(html: str) -> list[dict]:
    out: list[dict] = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.DOTALL | re.IGNORECASE):
        try:
            data = json.loads(block.strip(), strict=False)
        except json.JSONDecodeError:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            item = stack.pop()
            if isinstance(item, dict):
                if "@graph" in item and isinstance(item["@graph"], list):
                    stack.extend(item["@graph"])
                kind = item.get("@type", "")
                kinds = kind if isinstance(kind, list) else [kind]
                if any(k in ("NewsArticle", "Article", "ReportageNewsArticle", "BlogPosting") for k in kinds):
                    out.append(item)
    return out


def from_jsonld(html: str, jsonld: list[dict]) -> str:
    bodies = [clean(d.get("articleBody", "")) for d in jsonld]
    return max(bodies, key=len, default="")


def _walk_strings(node, found: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            if isinstance(v, str) and k.lower() in ("content", "body", "articlebody", "description", "detail",
                                                     "contenthtml", "html", "text") and len(v) > 300:
                found.append(v)
            else:
                _walk_strings(v, found)
    elif isinstance(node, list):
        for v in node:
            _walk_strings(v, found)


def from_embedded_state(html: str) -> str:
    """JS-rendered pages often ship the article in __NEXT_DATA__ / __NUXT__ JSON."""
    found: list[str] = []
    for block in re.findall(r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>', html, re.DOTALL):
        try:
            _walk_strings(json.loads(block), found)
        except json.JSONDecodeError:
            pass
    for block in re.findall(r"self\.__next_f\.push\(\[1,\s*\"(.*?)\"\]\)", html, re.DOTALL):
        try:
            decoded = json.loads(f'"{block}"')
        except json.JSONDecodeError:
            continue
        if len(decoded) > 300 and "<p" in decoded:
            found.append(decoded)
    texts = [clean(re.sub(r"</p>|<br\s*/?>", "\n", s)) for s in found]
    return max(texts, key=len, default="")


# Matched against whole class/id tokens (split on space, - and _), never substrings:
# "relative" or "shared-layout" must not match.
NOISE_TOKENS = {
    "related", "realted", "relate", "relates", "lienquan", "tinkhac", "othernews", "newsother", "boxnews",
    "recommend", "recommended", "readmore", "sidebar", "comment", "comments", "social", "share", "sharing",
    "tags", "tag", "banner", "advert", "ads", "quangcao", "footer", "navbar", "menu", "popup", "modal",
}
NOISE_PHRASES = re.compile(r"(lien-?quan|tin-?khac|other-?news|news-?other|box-?news|read-?more|quang-?cao)",
                           re.IGNORECASE)


def is_noise(attr: str) -> bool:
    tokens = {t for t in re.split(r"[\s\-_]+", attr.casefold()) if t}
    return bool(tokens & NOISE_TOKENS) or bool(NOISE_PHRASES.search(attr))


def strip_noise(html: str) -> str:
    """Drop related-news blocks, sidebars, comments, share bars, ads, nav and footers."""
    try:
        import lxml.html
        doc = lxml.html.fromstring(html)
    except Exception:
        return html
    for el in doc.xpath("//aside|//nav|//footer|//script|//style|//noscript|//form"):
        el.drop_tree()
    for el in doc.xpath("//*[@class or @id]"):
        if el.tag in ("html", "body") or el.getparent() is None:
            continue
        if is_noise(f"{el.get('class', '')} {el.get('id', '')}"):
            el.drop_tree()
    return lxml.html.tostring(doc, encoding="unicode")


def from_trafilatura(html: str, url: str) -> str:
    for kwargs in ({"favor_precision": True}, {"favor_recall": True}):
        text = trafilatura.extract(html, url=url, include_comments=False, include_tables=True,
                                   deduplicate=True, **kwargs)
        if text and len(text) >= MIN_CHARS:
            return clean(text)
    return clean(trafilatura.extract(html, url=url) or "")


def amp_url(html: str, base: str) -> str | None:
    m = re.search(r'<link[^>]+rel=["\']amphtml["\'][^>]*href=["\']([^"\']+)', html, re.IGNORECASE)
    return urljoin(base, m.group(1)) if m else None


def pdf_links(html: str, base: str, titles: list[str]) -> list[str]:
    """PDF attachments whose file name shares a word with the headline (skips site-wide PDFs)."""
    words = {ascii_fold(w) for t in titles for w in keywords(t) if len(w) > 2}
    links = []
    for href in re.findall(r'href=["\']([^"\']+\.pdf(?:\?[^"\']*)?)["\']', html, re.IGNORECASE):
        name = set(re.findall(r"[a-z0-9]+", ascii_fold(urlparse(href).path.rsplit("/", 1)[-1])))
        if words & name:
            links.append(urljoin(base, href))
    return list(dict.fromkeys(links))


def from_pdf(url: str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        return ""
    try:
        resp = http_get(url, timeout=40)
        reader = PdfReader(io.BytesIO(resp.content))
        return clean("\n".join(page.extract_text() or "" for page in reader.pages))
    except Exception:  # corrupt / encrypted / scanned PDFs: treated as no text
        return ""


# ---------------------------------------------------------------------------
# main entry
# ---------------------------------------------------------------------------

def crawl(url: str, title_hint: str = "") -> CrawlResult:
    res = CrawlResult(url=url)
    try:
        resp = http_get(url)
    except Exception as exc:
        res.status, res.error = "needs_manual", f"không kết nối được tới máy chủ: {exc!r}"
        return res
    res.final_url = str(resp.url)
    if resp.status_code in (401, 403, 451):
        res.status, res.error = "needs_manual", f"trang chặn truy cập tự động (HTTP {resp.status_code})"
        return res
    if resp.status_code >= 400:
        res.error = f"HTTP {resp.status_code}"
        return res

    html = decode(resp)
    jsonld = jsonld_objects(html)
    res.title = page_title(html, jsonld) or title_hint
    res.sapo = page_sapo(html, jsonld)
    res.published_at = published_date(html, jsonld, url)
    titles = [t for t in (res.title, title_hint) if t]
    res.attachments = pdf_links(html, res.final_url, titles)

    reasons = []
    strategies = [
        ("jsonld", lambda: from_jsonld(html, jsonld)),
        ("embedded_state", lambda: from_embedded_state(html)),
        ("trafilatura_clean", lambda: from_trafilatura(strip_noise(html), res.final_url)),
        ("trafilatura", lambda: from_trafilatura(html, res.final_url)),
    ]
    if amp := amp_url(html, res.final_url):
        def via_amp(amp=amp):
            amp_html = decode(http_get(amp))
            return from_trafilatura(strip_noise(amp_html), amp) or from_trafilatura(amp_html, amp)
        strategies.append(("amp", via_amp))
    for pdf in res.attachments[:2]:
        strategies.append((f"pdf:{pdf}", lambda pdf=pdf: from_pdf(pdf)))

    for name, run in strategies:
        try:
            text = run()
        except Exception as exc:
            reasons.append(f"{name}: lỗi {exc!r}")
            continue
        problem = quality(text, titles, res.sapo) if not name.startswith("pdf") else ("" if len(text) >= MIN_CHARS else "PDF không có lớp chữ")
        if not problem:
            text = drop_link_lists(text, res.title or title_hint)
            res.text, res.method, res.status = text, name, "ok"
            if res.sapo and res.sapo[:60] not in text:
                res.text = f"{res.sapo}\n{text}"
            if len(res.text) < 1000 and res.attachments and not name.startswith("pdf"):
                # disclosure/data pages: the figures often live in the attached PDF
                if extra := from_pdf(res.attachments[0]):
                    res.text += f"\n\n[Tệp đính kèm]\n{extra}"
                    res.method += "+pdf"
                else:
                    res.warnings.append(f"nội dung chi tiết có thể nằm trong PDF scan: {res.attachments[0]}")
            return res
        reasons.append(f"{name}: {problem}")

    res.status = "needs_manual"
    res.error = "; ".join(reasons)
    if res.attachments:
        res.error += f" | nội dung có thể nằm trong file đính kèm: {res.attachments[0]}"
    return res


class CrawlError(RuntimeError):
    def __init__(self, result: CrawlResult):
        self.result = result
        super().__init__(f"{result.status}: {result.error}")


def article_from_url(url: str, title_hint: str = "", watchlist: list[str] | None = None):
    """Crawl `url` and build a pipeline Article. Raises CrawlError instead of returning wrong text."""
    from .schemas import Article

    res = crawl(url, title_hint)
    if not res.ok:
        raise CrawlError(res)
    kwargs = {"watchlist": watchlist} if watchlist else {}
    return Article(title=res.title or title_hint, url=res.final_url or url,
                   published_at=res.published_at or date.today(), content=res.text, **kwargs)
