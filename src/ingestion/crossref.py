"""CP0 — Ingestion owner (VAI TRÒ 2, nhóm 5 người)

Nhiệm vụ CP0:
1. Đọc Crossref payload và PaperRecord; xác định field tạo stable paper_id.
2. Implement parse_crossref_payload và fetch/load theo contract Settings.
3. Lưu raw API response trước parse; thêm retry/backoff cho 429/503.

Source: Crossref REST API  https://api.crossref.org/works
paper_id: DOI slugified — dùng DOI vì là global unique ID học thuật,
          replace '/', '.' → '-', strip leading/trailing '-', lowercase.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import requests

from core.config import Settings

logger = logging.getLogger(__name__)

CROSSREF_API_URL = "https://api.crossref.org/works"

# User-Agent theo yêu cầu "polite pool" của Crossref
_USER_AGENT = (
    "Day10DataPipelineLab/0.1 "
    "(mailto:student@example.com; educational-use)"
)

# Retry config
_MAX_RETRIES = 5
_RETRY_STATUSES = {429, 500, 503}
_BACKOFF_BASE = 2.0  # giây


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PaperRecord:
    """Schema nhất quán cho một bài báo học thuật từ Crossref.

    paper_id: stable unique ID tạo từ DOI (không thay đổi theo thời gian).
    """

    paper_id: str         # slug của DOI, ví dụ: "10-1145-3442188-3445922"
    title: str
    summary: str          # abstract của paper
    authors: list[str]    # dạng "Họ Tên"
    categories: list[str] # subject / subject-area từ Crossref
    primary_category: str
    published: str        # ISO date: "YYYY-MM-DD" hoặc "YYYY-MM"
    updated: str          # ngày deposited / indexed, dạng ISO
    abs_url: str          # URL DOI dạng https://doi.org/...
    pdf_url: str          # URL PDF nếu có, hoặc chuỗi rỗng
    comment: str          # thông tin thêm (số trang, issue, v.v.)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _doi_to_paper_id(doi: str) -> str:
    """Chuyển DOI thành stable paper_id (lowercase slug).

    Ví dụ: "10.1145/3442188.3445922" -> "10-1145-3442188-3445922"
    """
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", doi)
    return slug.strip("-").lower()


def _extract_date(date_parts: list | None) -> str:
    """Parse date-parts của Crossref thành chuỗi ISO.

    date_parts: [[2024, 6, 15]] → "2024-06-15"
                [[2024, 6]]     → "2024-06"
                [[2024]]        → "2024"
    """
    if not date_parts or not date_parts[0]:
        return ""
    parts = date_parts[0]
    if len(parts) >= 3:
        return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
    if len(parts) == 2:
        return f"{parts[0]:04d}-{parts[1]:02d}"
    return str(parts[0])


def _clean_text(text: str | None) -> str:
    """Xoá HTML tags, whitespace thừa; trả về chuỗi rỗng nếu None."""
    if not text:
        return ""
    # xoá HTML tags đơn giản
    cleaned = re.sub(r"<[^>]+>", " ", str(text))
    # chuẩn hoá whitespace
    return " ".join(cleaned.split()).strip()


def _extract_authors(item: dict) -> list[str]:
    """Trích tên tác giả từ item Crossref."""
    authors = []
    for a in item.get("author", []):
        given = a.get("given", "").strip()
        family = a.get("family", "").strip()
        if family:
            name = f"{given} {family}".strip() if given else family
            authors.append(name)
    return authors


def _extract_url(item: dict) -> tuple[str, str]:
    """Trả về (abs_url, pdf_url) từ item Crossref."""
    doi = item.get("DOI", "")
    abs_url = f"https://doi.org/{doi}" if doi else ""

    pdf_url = ""
    for link in item.get("link", []):
        if link.get("content-type") == "application/pdf":
            pdf_url = link.get("URL", "")
            break

    return abs_url, pdf_url


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thành list PaperRecord.

    Bước:
    1. Duyệt payload["message"]["items"].
    2. Lấy DOI → paper_id, title, abstract, authors, subject, dates, URLs.
    3. Chuẩn hoá text và bỏ record không hợp lệ (thiếu DOI, title hoặc abstract).
    4. Trả về list PaperRecord.
    """
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []
    skipped = 0

    for item in items:
        doi = item.get("DOI", "").strip()
        if not doi:
            logger.debug("Bỏ qua item không có DOI.")
            skipped += 1
            continue

        # --- title ---
        raw_titles = item.get("title", [])
        title = _clean_text(raw_titles[0] if raw_titles else "")
        if not title:
            logger.debug("Bỏ qua DOI=%s: title rỗng.", doi)
            skipped += 1
            continue

        # --- abstract (summary) ---
        summary = _clean_text(item.get("abstract", ""))
        if not summary:
            logger.debug("Bỏ qua DOI=%s: abstract rỗng.", doi)
            skipped += 1
            continue

        # --- paper_id ---
        paper_id = _doi_to_paper_id(doi)

        # --- authors ---
        authors = _extract_authors(item)

        # --- categories / subjects ---
        categories = [s.strip() for s in item.get("subject", []) if s.strip()]
        primary_category = categories[0] if categories else ""

        # --- dates ---
        pub_date = (
            _extract_date(item.get("published", {}).get("date-parts"))
            or _extract_date(item.get("published-print", {}).get("date-parts"))
            or _extract_date(item.get("published-online", {}).get("date-parts"))
            or _extract_date(item.get("created", {}).get("date-parts"))
        )
        updated_date = (
            _extract_date(item.get("deposited", {}).get("date-parts"))
            or _extract_date(item.get("indexed", {}).get("date-parts"))
            or pub_date
        )

        # --- URLs ---
        abs_url, pdf_url = _extract_url(item)

        # --- comment (thông tin bổ sung: trang, volume, issue) ---
        parts = []
        if item.get("volume"):
            parts.append(f"vol.{item['volume']}")
        if item.get("issue"):
            parts.append(f"no.{item['issue']}")
        if item.get("page"):
            parts.append(f"pp.{item['page']}")
        comment = " ".join(parts)

        records.append(
            PaperRecord(
                paper_id=paper_id,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=pub_date,
                updated=updated_date,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )

    logger.info(
        "parse_crossref_payload: %d records parsed, %d skipped (no DOI/title/abstract).",
        len(records),
        skipped,
    )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Gọi Crossref API, lưu raw response, parse thành records.

    Bước:
    1. Tạo params từ settings.source_query, settings.source_filter, settings.max_results.
    2. Gọi API với retry/backoff cho 429/503 (tối đa _MAX_RETRIES lần).
    3. Lưu raw response vào settings.paths.raw_api_response (trước khi parse).
    4. Parse payload bằng parse_crossref_payload.
    5. Lưu records vào settings.paths.raw_records_json.
    6. Trả về list[PaperRecord].
    """
    # --- Kiểm tra: nếu đã có raw và không yêu cầu refresh, load lại ---
    raw_resp_path = settings.paths.raw_api_response
    raw_rec_path = settings.paths.raw_records_json

    if (
        not settings.refresh_source
        and raw_resp_path.exists()
        and raw_rec_path.exists()
    ):
        logger.info(
            "Raw artifacts already exist and REFRESH_SOURCE=false -> loading from snapshot."
        )
        return load_raw_records(raw_rec_path)

    # --- Tạo request params ---
    params: dict[str, str | int] = {
        "query": settings.source_query,
        "rows": settings.max_results,
        "select": (
            "DOI,title,abstract,author,subject,"
            "published,published-print,published-online,"
            "created,deposited,indexed,link,volume,issue,page"
        ),
    }
    if settings.source_filter:
        params["filter"] = settings.source_filter

    headers = {"User-Agent": _USER_AGENT}

    # --- Gọi API với retry/backoff ---
    payload: dict = {}
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            logger.info(
                "Crossref API request attempt %d/%d: query=%r rows=%d",
                attempt,
                _MAX_RETRIES,
                settings.source_query,
                settings.max_results,
            )
            response = requests.get(
                CROSSREF_API_URL,
                params=params,
                headers=headers,
                timeout=30,
            )

            if response.status_code == 200:
                payload = response.json()
                logger.info("Crossref API 200 OK: %d bytes received.", len(response.content))
                break

            if response.status_code in _RETRY_STATUSES:
                wait = _BACKOFF_BASE ** attempt
                logger.warning(
                    "Crossref API HTTP %d -> retry %d/%d after %.1fs.",
                    response.status_code,
                    attempt,
                    _MAX_RETRIES,
                    wait,
                )
                time.sleep(wait)
                continue

            # Lỗi không retry được
            response.raise_for_status()

        except requests.exceptions.Timeout:
            wait = _BACKOFF_BASE ** attempt
            logger.warning("Crossref API timeout -> retry %d/%d after %.1fs.", attempt, _MAX_RETRIES, wait)
            time.sleep(wait)
        except requests.exceptions.ConnectionError as exc:
            wait = _BACKOFF_BASE ** attempt
            logger.warning("Crossref API connection error (%s) -> retry %d/%d after %.1fs.", exc, attempt, _MAX_RETRIES, wait)
            time.sleep(wait)
    else:
        raise RuntimeError(
            f"Crossref API: failed after {_MAX_RETRIES} attempts. "
            "Check network connection or try again later."
        )

    # --- Lưu raw API response TRƯỚC KHI parse ---
    raw_resp_path.parent.mkdir(parents=True, exist_ok=True)
    with open(raw_resp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    logger.info("Raw API response saved: %s", raw_resp_path)

    # --- Parse ---
    records = parse_crossref_payload(payload)

    # --- Lưu records JSON ---
    raw_rec_path.parent.mkdir(parents=True, exist_ok=True)
    records_as_dicts = [asdict(r) for r in records]
    with open(raw_rec_path, "w", encoding="utf-8") as f:
        json.dump(records_as_dicts, f, ensure_ascii=False, indent=2)
    logger.info(
        "Raw records saved: %s (%d records)", raw_rec_path, len(records)
    )

    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Đọc JSON snapshot và map thành list[PaperRecord].

    Dùng khi raw records đã tồn tại để tránh gọi lại API.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Raw records file not found: {path}\n"
            "Run fetch_source_records() first."
        )

    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    records = [PaperRecord(**item) for item in data]
    logger.info("Loaded %d records from snapshot: %s", len(records), path)

    return records
