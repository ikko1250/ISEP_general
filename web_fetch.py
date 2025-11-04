#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, csv, json, time, hashlib, mimetypes, subprocess, tempfile
from pathlib import Path
from urllib.parse import urlparse
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.ssl_ import create_urllib3_context
import chardet
from bs4 import BeautifulSoup

# Optional but recommended: fast main-content extractor
try:
    import trafilatura
    HAS_TRA = True
except Exception:
    HAS_TRA = False

# PDF text extractors
from pdfminer.high_level import extract_text as pdf_extract_text
import fitz  # PyMuPDF

OUT_DIR = Path("out_2020")
OUT_DIR.mkdir(exist_ok=True)

PDF_DIR = Path("out_pdf_2020")
PDF_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; OrdinanceTextBot/1.0; +https://example.invalid)"
}

# Custom SSL adapter for compatibility with problematic servers
class SSLAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        ctx = create_urllib3_context()
        ctx.set_ciphers('DEFAULT@SECLEVEL=1')
        kwargs['ssl_context'] = ctx
        return super().init_poolmanager(*args, **kwargs)

def create_session():
    """Create a requests session with custom SSL adapter."""
    s = requests.Session()
    s.mount('https://', SSLAdapter())
    s.headers.update(HEADERS)
    return s

def sha256_of_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def fetch(url: str, timeout=30):
    """Fetch with HEAD fallback to GET if HEAD not allowed."""
    s = create_session()
    try:
        r = s.head(url, allow_redirects=True, timeout=timeout)
        if r.status_code >= 400 or ("text/html" in r.headers.get("content-type","").lower() and int(r.headers.get("content-length","0") or 0) == 0):
            raise Exception("HEAD not usable, try GET")
        return r, None
    except Exception:
        r = s.get(url, allow_redirects=True, timeout=timeout)
        return r, r.content  # when GET was used, return content too

def guess_filename(url: str) -> str:
    name = os.path.basename(urlparse(url).path) or "index"
    # Remove query parameters if present
    name = name.split("?")[0]
    return name

def safe_filename(text: str) -> str:
    """Convert text to safe filename by removing/replacing problematic characters."""
    # Replace spaces and problematic characters with underscore
    text = re.sub(r'[^\w\-.]', '_', text)
    # Remove consecutive underscores
    text = re.sub(r'_+', '_', text)
    return text.strip('_')

def normalize_text(txt: str) -> str:
    # heuristic cleanups for Japanese legal text
    txt = txt.replace("\u3000", " ")            # full-width space -> half
    txt = re.sub(r"[ \t]+", " ", txt)
    txt = re.sub(r"\n{3,}", "\n\n", txt)
    return txt.strip()

def extract_html_text(html_bytes: bytes, url: str) -> str:
    # encoding detection
    enc = chardet.detect(html_bytes).get("encoding") or "utf-8"
    html = html_bytes.decode(enc, errors="replace")

    if HAS_TRA:
        try:
            main = trafilatura.extract(html, url=url, include_comments=False, include_links=False)
            if main and len(main) > 200:
                return normalize_text(main)
        except Exception:
            pass

    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script","style","noscript","header","footer","nav"]):
        tag.decompose()
    text = soup.get_text("\n")
    # collapse menu-like very short lines heuristic
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln for ln in lines if ln]
    text = "\n".join(lines)
    return normalize_text(text)

def pdf_text_fast(path: Path) -> str:
    """Try pdfminer first; if too short, try PyMuPDF blocks with sort."""
    try:
        t = pdf_extract_text(str(path)) or ""
    except Exception:
        t = ""
    if len(t.strip()) >= 200:
        return normalize_text(t)
    # try PyMuPDF
    try:
        doc = fitz.open(path)
        blocks = []
        for page in doc:
            blocks.append(page.get_text("text", sort=True))
        t2 = "\n".join(blocks)
        return normalize_text(t2)
    except Exception:
        return normalize_text(t)

def is_scanned_pdf(path: Path, char_threshold=200) -> bool:
    """Heuristic: extract text and count; scanned PDFs usually yield near zero."""
    txt = pdf_text_fast(path)
    return len(txt) < char_threshold

def ocrmypdf_available() -> bool:
    try:
        subprocess.run(["ocrmypdf","--version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except Exception:
        return False

def run_ocrmypdf(in_pdf: Path, out_pdf: Path, lang="jpn+eng"):
    cmd = [
        "ocrmypdf",
        "--skip-text",          # do not OCR pages with embedded text
        "--optimize", "3",      # max optimization
        "--language", lang,
        "--output-type","pdf",
        "--jobs", "2",
        str(in_pdf),
        str(out_pdf),
    ]
    subprocess.run(cmd, check=True)

def process_url(url: str, meta: dict, html_completed: set):
    # Use metadata for better filename
    if "municipality" in meta and "doc_type" in meta:
        municipality_safe = safe_filename(meta["municipality"])
        doc_type_safe = safe_filename(meta["doc_type"])
        fname_base = f"{municipality_safe}_{doc_type_safe}"
    else:
        fname_base = safe_filename(guess_filename(url))
    
    # Determine if this is a PDF URL
    r_test, _ = fetch(url)
    ct = r_test.headers.get("content-type","").split(";")[0].lower()
    is_pdf = "pdf" in ct or url.lower().endswith(".pdf")
    
    if is_pdf:
        # Check if HTML versions exist for both Ordinance and Regulation
        municipality = meta.get("municipality", "")
        if municipality:
            municipality_safe = safe_filename(municipality)
            ordinance_html = OUT_DIR / f"{municipality_safe}_Ordinance_HTML.txt"
            regulation_html = OUT_DIR / f"{municipality_safe}_Regulation_HTML.txt"
            
            # Skip PDF if both HTML versions exist
            if ordinance_html.exists() and regulation_html.exists():
                print(f"    [SKIP] HTML versions exist for {municipality}, skipping PDF")
                return {
                    "url": url,
                    "municipality": municipality,
                    "prefecture": meta.get("prefecture", ""),
                    "doc_type": meta.get("doc_type", ""),
                    "status": "skipped",
                    "method": "html_exists",
                    "output_pdf": None
                }
        
        # Check if PDF already downloaded
        out_pdf = PDF_DIR / f"{fname_base}.pdf"
        if out_pdf.exists():
            print(f"    [SKIP] Already exists: {out_pdf}")
            return {
                "url": url,
                "municipality": meta.get("municipality", ""),
                "prefecture": meta.get("prefecture", ""),
                "doc_type": meta.get("doc_type", ""),
                "output_pdf": str(out_pdf),
                "status": "skipped",
                "method": "already_exists"
            }
        
        # Download PDF
        r, body = fetch(url)
        if body is None:
            r_get = create_session().get(url, timeout=30)
            body = r_get.content
        
        pdf_hash = sha256_of_bytes(body)
        out_pdf.write_bytes(body)
        
        now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
        return {
            "url": url,
            "content_type": ct,
            "fetched_at": now,
            "method": "pdf_download",
            "bytes_sha256": pdf_hash,
            "output_pdf": str(out_pdf),
        }
    
    # HTML processing
    out_txt = OUT_DIR / f"{fname_base}.txt"
    if out_txt.exists():
        print(f"    [SKIP] Already exists: {out_txt}")
        return {
            "url": url,
            "municipality": meta.get("municipality", ""),
            "prefecture": meta.get("prefecture", ""),
            "doc_type": meta.get("doc_type", ""),
            "output_txt": str(out_txt),
            "status": "skipped",
            "method": "already_exists"
        }
    
    r, body = fetch(url)
    now = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    
    record = {
        "url": url,
        "content_type": ct,
        "fetched_at": now,
        "method": None,
        "bytes_sha256": None,
        "output_txt": None,
    }

    if body is None:
        r_get = create_session().get(url, timeout=30)
        body = r_get.content
    rec_hash = sha256_of_bytes(body)
    record["bytes_sha256"] = rec_hash
    text = extract_html_text(body, url)
    out_txt.write_text(text, encoding="utf-8")
    record["method"] = "trafilatura/BeautifulSoup"
    record["output_txt"] = str(out_txt)
    return record

def main(urls_path="urls.csv"):
    print(f"Starting web_fetch.py...")
    print(f"Reading CSV from: {urls_path}")
    
    index_path = OUT_DIR / "index.jsonl"
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(PDF_DIR, exist_ok=True)

    # read URLs from CSV with all URL columns
    url_entries = []
    with open(urls_path, newline="", encoding="utf-8") as f:
        # Skip empty lines at the beginning
        lines = f.readlines()
        # Find the first non-empty line as header
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip():
                start_idx = i
                break
        
        # Create a new reader from the valid lines
        from io import StringIO
        valid_csv = "".join(lines[start_idx:])
        reader = csv.DictReader(StringIO(valid_csv))
        
        print(f"CSV Headers: {reader.fieldnames}")
        for row in reader:
            municipality = row.get("Municipality", "").strip()
            prefecture = row.get("Prefecture", "").strip()
            
            # Extract URLs from all URL columns (HTML and PDF)
            url_columns = [
                "Ordinance_HTML",
                "Regulation_HTML",
                "Ordinance_PDF",
                "Regulation_PDF"
            ]
            
            for col_name in url_columns:
                url = row.get(col_name) or ""
                url = url.strip().strip('"')
                
                if url and url.startswith("http"):
                    url_entries.append({
                        "url": url,
                        "municipality": municipality,
                        "prefecture": prefecture,
                        "doc_type": col_name
                    })

    print(f"Total URLs found: {len(url_entries)}")
    
    # Build set of municipalities that have HTML completed
    html_completed = set()
    
    meta = {}
    results = []
    total = len(url_entries)
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for idx, entry in enumerate(url_entries, 1):
        url = entry["url"]
        try:
            # Pass metadata to process_url
            meta_info = {
                "municipality": entry["municipality"],
                "prefecture": entry["prefecture"],
                "doc_type": entry["doc_type"]
            }
            rec = process_url(url, meta_info, html_completed)
            # Add metadata to record
            rec["municipality"] = entry["municipality"]
            rec["prefecture"] = entry["prefecture"]
            rec["doc_type"] = entry["doc_type"]
            results.append(rec)
            
            if rec.get("status") == "skipped":
                skip_count += 1
                skip_reason = rec.get("method", "already_exists")
                if skip_reason == "html_exists":
                    print(f"[{idx}/{total}] [SKIP] {entry['municipality']} ({entry['doc_type']}) -> HTML versions exist")
                else:
                    print(f"[{idx}/{total}] [SKIP] {entry['municipality']} ({entry['doc_type']}) -> Already exists")
            else:
                success_count += 1
                output_file = rec.get('output_pdf') or rec.get('output_txt', 'N/A')
                print(f"[{idx}/{total}] [OK] {entry['municipality']} ({entry['doc_type']}) -> {output_file} ({rec['method']})")
        except Exception as e:
            error_count += 1
            print(f"[{idx}/{total}] [ERR] {entry['municipality']} ({entry['doc_type']}) {url} -> {e}")
            results.append({
                "url": url,
                "municipality": entry["municipality"],
                "prefecture": entry["prefecture"],
                "doc_type": entry["doc_type"],
                "error": str(e)
            })

    with open(index_path, "w", encoding="utf-8") as w:
        for rec in results:
            w.write(json.dumps(rec, ensure_ascii=False) + "\n")
    
    print(f"\n{'='*60}")
    print(f"Completed! Processed {len(results)} URLs")
    print(f"  Success: {success_count}")
    print(f"  Skipped: {skip_count}")
    print(f"  Errors:  {error_count}")
    print(f"Results saved to: {index_path}")
    print(f"{'='*60}")

if __name__ == "__main__":
    # 例: urls.csv（UTF-8, 1列ヘッダ 'url'）を同じフォルダに用意
    main("urls.csv")
