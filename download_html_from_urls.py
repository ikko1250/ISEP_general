#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Download HTML pages from urls_2014.csv ... urls_2023.csv.

Capabilities:
- Analyze URL field formats across years (--analyze)
- Robustly extract HTML URLs from messy cells (quotes, [ ], markdown-like, multiple URLs)
- Download only HTML pages found in Ordinance_HTML / Regulation_HTML columns
- Skip municipalities with no HTML URL (no file generated)

Output layout:
  out_html_<YEAR>/<Municipality>_Ordinance_HTML.html
  out_html_<YEAR>/<Municipality>_Regulation_HTML.html
If multiple URLs exist for a field, add numeric suffixes: _1, _2, ...

Usage examples:
  python3 download_html_from_urls.py --analyze
  python3 download_html_from_urls.py --download
  python3 download_html_from_urls.py --years 2018-2023 --download
"""

import argparse
import csv
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


YEARS_DEFAULT = list(range(2014, 2024))
CSV_PREFIX = "urls_"


def sniff_dialect(fp) -> csv.Dialect:
    pos = fp.tell()
    sample = fp.read(4096)
    fp.seek(pos)
    try:
        return csv.Sniffer().sniff(sample)
    except Exception:
        return csv.excel


def normalize_fieldnames(fns: List[str]) -> List[str]:
    out = []
    for fn in fns or []:
        if fn is None:
            out.append(fn)
            continue
        s = fn.strip()
        # strip extra embedded quotes seen in 2023 header like """Ordinance_HTML"""
        s = s.strip('"')
        s = s.strip("'")
        out.append(s)
    return out


def detect_format_cell(val: Optional[str]) -> str:
    if val is None:
        return "missing"
    t = val.strip()
    if t == "" or t.lower() in {"na", "none", "nan", "null", "-"}:
        return "empty"
    fmt: List[str] = []
    if t.startswith("[") and t.endswith("]"):
        fmt.append("list_like")
    if (t.startswith('"') and t.endswith('"')) or (t.startswith("'") and t.endswith("'")):
        fmt.append("quoted")
    if "](" in t and ")" in t:
        fmt.append("markdown_link_like")
    if t.count("http") > 1:
        fmt.append("multi_urls")
    if "," in t:
        fmt.append("comma_sep")
    if ";" in t:
        fmt.append("semicolon_sep")
    if "http" in t:
        fmt.append("contains_http")
    return "+".join(fmt) if fmt else "other"


URL_RE = re.compile(r"https?://[^\s\]\"',)]+", re.I)


def extract_urls_from_cell(val: Optional[str]) -> List[str]:
    """Extract one or more URLs from a messy cell.

    Handles cases like:
    - "https://example" (simple)
    - "[https://a]" or "[https://a](https://b)" (markdown-like)
    - over-quoted values with repeated quotes
    - multiple URLs separated by comma/semicolon
    """
    if not val:
        return []
    s = val.strip().strip("\u200b")  # remove zero-width spaces if any
    # remove outer quotes if entire cell is quoted
    if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
        s = s[1:-1]
    # drop stray leading/trailing brackets
    s = s.strip().lstrip("[").rstrip("]").strip()
    # Replace markdown "](url)" style with a separator
    s = s.replace("](", ",")
    # Collapse repeated quotes seen in 2023 sample
    s = s.replace('"""', '"').replace("'''", "'")
    # Now regex-extract all http(s) URLs
    urls = URL_RE.findall(s)
    # Clean common trailing artifacts (encoded quotes, stray brackets/parentheses)
    def _clean(u: str) -> str:
        u2 = u
        # remove repeated encoded quotes at end
        while u2.endswith('%22') or u2.endswith('%27'):
            u2 = u2[:-3]
        # strip stray trailing punctuation
        u2 = u2.rstrip(")]\"'")
        return u2
    # Dedup while preserving order
    seen = set()
    out: List[str] = []
    for u in urls:
        u = _clean(u)
        if u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out


def looks_like_html_url(url: str) -> bool:
    u = url.lower()
    # Exclude pdf links
    if u.endswith(".pdf") or ".pdf?" in u or "/pdf" in u:
        return False
    # Many ordinance pages end with .html; some are HTML endpoints without extension
    return True


@dataclass
class RowItem:
    municipality: str
    prefecture: str
    doc_field: str  # 'Ordinance_HTML' or 'Regulation_HTML'
    urls: List[str]


def read_items_for_year(year: int) -> Tuple[List[RowItem], List[str]]:
    fname = f"{CSV_PREFIX}{year}.csv"
    p = Path(fname)
    errors: List[str] = []
    items: List[RowItem] = []
    if not p.exists():
        errors.append(f"Missing file: {fname}")
        return items, errors
    with p.open("r", encoding="utf-8", errors="ignore") as fp:
        dialect = sniff_dialect(fp)
        reader = csv.DictReader(fp, dialect=dialect)
        reader.fieldnames = normalize_fieldnames(reader.fieldnames or [])
        fns = reader.fieldnames or []
        # Find key fields
        muni_key = "Municipality" if "Municipality" in fns else None
        pref_key = "Prefecture" if "Prefecture" in fns else None
        ord_key = "Ordinance_HTML" if "Ordinance_HTML" in fns else None
        reg_key = "Regulation_HTML" if "Regulation_HTML" in fns else None
        if not ord_key and not reg_key:
            errors.append(f"{fname}: target fields not found (fields={fns})")
            return items, errors
        for row in reader:
            muni = (row.get(muni_key) or "").strip() if muni_key else ""
            pref = (row.get(pref_key) or "").strip() if pref_key else ""
            for key in (ord_key, reg_key):
                if not key:
                    continue
                urls = [u for u in extract_urls_from_cell(row.get(key)) if looks_like_html_url(u)]
                items.append(RowItem(municipality=muni, prefecture=pref, doc_field=key, urls=urls))
    return items, errors


def analyze(years: Iterable[int]) -> None:
    print("Detected URL formats and samples:")
    for y in years:
        items, errors = read_items_for_year(y)
        if errors:
            for e in errors:
                print(f"[WARN] {e}")
            continue
        # Collect format counts
        counts: Dict[str, int] = {}
        samples: Dict[str, List[str]] = {}
        total = 0
        for it in items:
            total += 1
            # Examine the raw cell format via detect_format_cell on the joined raw string
            cell_raw = ",".join(it.urls) if it.urls else ""
            fmt = "has_html_url" if it.urls else "empty_or_non_html"
            counts[fmt] = counts.get(fmt, 0) + 1
            if fmt not in samples:
                samples[fmt] = []
            if it.urls and len(samples[fmt]) < 3:
                samples[fmt].append(it.urls[0])
        print(f"\n=== {CSV_PREFIX}{y}.csv ===")
        print(f"Rows x fields checked: {len(items)}")
        for k, v in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
            print(f"  {k}: {v}")
        for k, vals in samples.items():
            if vals:
                print("  Samples:")
                for s in vals:
                    print(f"    - {s}")


def make_session() -> requests.Session:
    s = requests.Session()
    retries = Retry(total=3, connect=3, read=3, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; ISEPDownloader/1.0)"
    })
    return s


def download(years: Iterable[int], overwrite: bool = False, dry_run: bool = False) -> None:
    sess = make_session()
    for y in years:
        items, errors = read_items_for_year(y)
        if errors:
            for e in errors:
                print(f"[WARN] {e}")
            continue
        outdir = Path(f"out_html_{y}")
        outdir.mkdir(parents=True, exist_ok=True)
        print(f"\n# Year {y}: writing to {outdir}")
        for it in items:
            if not it.urls:
                # No HTML URL present; skip
                continue
            # Prefer to download all URLs in the cell; number them
            for idx, url in enumerate(it.urls, start=1):
                base_name = f"{it.municipality}_{it.doc_field}"
                base_name = re.sub(r"[^\w\-.]", "_", base_name).strip("_")
                suffix = "" if len(it.urls) == 1 else f"_{idx}"
                outpath = outdir / f"{base_name}{suffix}.html"
                if outpath.exists() and not overwrite:
                    print(f"[SKIP] exists: {outpath}")
                    continue
                if dry_run:
                    print(f"[DRYRUN] Would fetch {url} -> {outpath}")
                    continue
                try:
                    resp = sess.get(url, timeout=30, allow_redirects=True)
                    ct = resp.headers.get("content-type", "").lower()
                    # Only save if looks like HTML
                    if "html" not in ct and not url.lower().endswith(".html"):
                        print(f"[SKIP] Non-HTML content-type for {url}: {ct}")
                        continue
                    data = resp.content
                    outpath.write_bytes(data)
                    print(f"[OK] {url} -> {outpath} ({len(data)} bytes)")
                except Exception as e:
                    print(f"[ERR] {url}: {e}")


def parse_years_arg(arg: Optional[str]) -> List[int]:
    if not arg:
        return YEARS_DEFAULT
    if "," in arg:
        ys = []
        for part in arg.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                a, b = part.split("-", 1)
                ys.extend(range(int(a), int(b) + 1))
            else:
                ys.append(int(part))
        return sorted(set(ys))
    if "-" in arg:
        a, b = arg.split("-", 1)
        return list(range(int(a), int(b) + 1))
    return [int(arg)]


def main():
    ap = argparse.ArgumentParser(description="Download HTML pages from urls_YYYY.csv files (2014-2023)")
    ap.add_argument("--years", help="Years, e.g., 2014-2023 or 2018,2020,2023", default=None)
    ap.add_argument("--analyze", action="store_true", help="Analyze cell formats and URL presence")
    ap.add_argument("--download", action="store_true", help="Download HTML pages")
    ap.add_argument("--overwrite", action="store_true", help="Overwrite existing files")
    ap.add_argument("--dry-run", action="store_true", help="Print intended downloads without fetching")
    args = ap.parse_args()

    years = parse_years_arg(args.years)
    if args.analyze or not args.download:
        analyze(years)
    if args.download:
        download(years, overwrite=args.overwrite, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
