#!/usr/bin/env python3
import json
import sqlite3
from pathlib import Path
try:
    from versioning.filename import make_dated_versioned_path
except ModuleNotFoundError:
    # スクリプト単体実行時にパス解決できない環境のためのフォールバック
    import sys as _sys
    _sys.path.append(str(Path(__file__).resolve().parents[1]))
    from versioning.filename import make_dated_versioned_path


TEMPLATE = """<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>罰則規定データテーブル</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans JP', 'Hiragino Kaku Gothic ProN', 'Yu Gothic', Meiryo, Arial, sans-serif; background: #fff; margin: 24px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: transparent; color: #222; padding: 0; margin-bottom: 8px; text-align: left; }
        .header h1 { font-size: 24px; margin: 0 0 8px 0; }
        .header p { font-size: 0.9em; color: #666; }
        .controls { padding: 0; background: transparent; border: none; display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin: 12px 0; }
        .search-box { flex: 1; min-width: 240px; }
        .search-box input { width: 100%; padding: 6px 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }
        .search-box input:focus { outline: none; border-color: #999; box-shadow: none; }
        .stats { font-size: 0.9em; color: #666; }
        .table-wrapper { overflow-x: auto; }
        table { width: 100%; border-collapse: collapse; margin: 12px 0; font-size: 13px; }
        thead { background: #f7f7f7; position: static; }
        th, td { border: 1px solid #ddd; padding: 6px 8px; }
        th { text-align: center; font-weight: 600; color: #333; cursor: pointer; user-select: none; background: #f7f7f7; }
        th.sortable::after { content: ' \\21C5'; opacity: 0.3; font-size: 12px; }
        td { color: #333; text-align: right; }
        .text-content { max-width: 480px; overflow: hidden; text-overflow: ellipsis; white-space: normal; line-height: 1.4; text-align: left; }
        .hidden { display: none; }
        .footer { font-size: 0.9em; color: #666; margin-top: 12px; }
        /* Narrow the code column */
        th[data-column="code"] { width: 160px; }
        td.code-cell { max-width: 160px; white-space: normal; word-break: break-word; text-align: left; }
    </style>
    </head>
    <body>
    <div class="container">
        <div class="header">
            <h1>罰則規定データテーブル</h1>
            <p>太陽光発電施設に関する条例・許可情報（罰則規定コード）</p>
        </div>
        <div class="controls">
            <div class="search-box">
                <input type="text" id="searchInput" placeholder="テーブル内を検索..." />
            </div>
            <div class="stats">表示中: <span id="displayCount">0</span> / <span id="totalCount">0</span> 件</div>
        </div>
        <div class="table-wrapper">
            <table id="dataTable">
                <thead>
                    <tr>
                        <th class="sortable" data-column="paragraph_id">段落ID</th>
                        <th class="sortable" data-column="municipality">市区町村</th>
                        <th class="sortable" data-column="year">年度</th>
                        <th class="sortable" data-column="category">カテゴリ</th>
                        <th class="sortable" data-column="dan_number">段番号</th>
                        <th class="sortable" data-column="text">テキスト</th>
                        <th class="sortable" data-column="code">コード</th>
                    </tr>
                </thead>
                <tbody id="tableBody"></tbody>
            </table>
        </div>
        <div class="footer"><p>データは SQLite から自動生成されました。</p></div>
    </div>

    <script>
        const data = __DATA_JSON__;
        const tableBody = document.getElementById('tableBody');
        const totalCountEl = document.getElementById('totalCount');
        const displayCountEl = document.getElementById('displayCount');
        const searchInput = document.getElementById('searchInput');
        const thElements = Array.from(document.querySelectorAll('th.sortable'));

        let filteredData = [...data];
        let sortColumn = null;
        let sortAsc = true;

        function renderTable(rows) {
            tableBody.innerHTML = '';
            const fragment = document.createDocumentFragment();
            rows.forEach(row => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>${row.paragraph_id ?? ''}</td>
                    <td style="text-align:left;">${row.municipality ?? ''}</td>
                    <td>${row.year ?? ''}</td>
                    <td style="text-align:left;">${row.category ?? ''}</td>
                    <td>${row.dan_number ?? ''}</td>
                    <td class="text-content">${(row.text ?? '').replace(/</g,'&lt;')}</td>
                    <td class="code-cell">${row.code ?? ''}</td>
                `;
                fragment.appendChild(tr);
            });
            tableBody.appendChild(fragment);
            totalCountEl.textContent = data.length;
            displayCountEl.textContent = rows.length;
        }

        function initTable() { renderTable(filteredData); }

        searchInput.addEventListener('input', () => {
            const term = searchInput.value.trim().toLowerCase();
            filteredData = data.filter(row => {
                return Object.values(row).some(v => String(v || '').toLowerCase().includes(term));
            });
            renderTable(filteredData);
        });

        thElements.forEach(th => {
            th.addEventListener('click', () => {
                const column = th.dataset.column;
                const isAsc = sortColumn === column ? !sortAsc : true;
                filteredData.sort((a, b) => {
                    let aVal = a[column];
                    let bVal = b[column];
                    const aNum = parseFloat(aVal);
                    const bNum = parseFloat(bVal);
                    if (!isNaN(aNum) && !isNaN(bNum)) { aVal = aNum; bVal = bNum; }
                    if (aVal == null && bVal == null) return 0;
                    if (aVal == null) return isAsc ? -1 : 1;
                    if (bVal == null) return isAsc ? 1 : -1;
                    if (aVal < bVal) return isAsc ? -1 : 1;
                    if (aVal > bVal) return isAsc ? 1 : -1;
                    return 0;
                });
                sortColumn = column;
                sortAsc = isAsc;
                renderTable(filteredData);
            });
        });

        initTable();
    </script>
    </body>
    </html>
"""


def safe_int(v):
    try:
        if v is None or v == '':
            return None
        return int(str(v).strip())
    except Exception:
        return v


def fetch_rows(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        sql = """
        WITH target AS (
            SELECT p.id AS paragraph_id,
                   m.name AS municipality,
                   p.year AS year,
                   p.category AS category,
                   p.dan_number AS dan_number,
                   p.text AS text,
                   '*CLAUSE_PENALTY_Lv2' AS code
            FROM paragraphs p
            JOIN paragraph_codings pc ON pc.paragraph_id = p.id
            JOIN coding_types ct ON ct.id = pc.coding_type_id
            JOIN municipalities m ON m.id = p.municipality_id
            WHERE ct.code = '*CLAUSE_PENALTY_Lv2'
        )
        SELECT t.paragraph_id, t.municipality, t.year, t.category, t.dan_number, t.text, t.code
        FROM target t
        ORDER BY t.paragraph_id
        """
        cur = conn.execute(sql)
        for r in cur.fetchall():
            yield {
                'paragraph_id': safe_int(r['paragraph_id']),
                'municipality': r['municipality'],
                'year': r['year'],
                'category': r['category'],
                'dan_number': safe_int(r['dan_number']),
                'text': r['text'],
                # Show all coding codes in the paragraph
                'code': r['code'],
            }
    finally:
        conn.close()


def export_html(db_path: Path, out_path: Path):
    rows = list(fetch_rows(db_path))
    data_json = json.dumps(rows, ensure_ascii=False)
    html = TEMPLATE.replace('__DATA_JSON__', data_json)
    out_path.write_text(html, encoding='utf-8')


if __name__ == '__main__':
    # 入力DB
    db = Path('clause-viewer/clause_data3.db')

    # 出力先ディレクトリとファイル名（バージョニング付き）
    out_dir = Path('clause-viewer')
    versioned_path = make_dated_versioned_path(out_dir, 'penalty_regulation_from_db_', '.html')

    # バージョン付きファイルを出力
    export_html(db, versioned_path)

    # 既存の固定名にも最新を上書き保存（後方互換）
    latest_path = out_dir / 'penalty_regulation_from_db.html'
    export_html(db, latest_path)

    print(f'Wrote versioned: {versioned_path}')
    print(f'Wrote latest:   {latest_path}')
