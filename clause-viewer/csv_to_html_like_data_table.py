import csv
import json
from pathlib import Path


TEMPLATE = """<!DOCTYPE html>
<html lang=\"ja\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>環境許可データテーブル</title>
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
    </style>
    </head>
    <body>
    <div class=\"container\">
        <div class=\"header\">
            <h1>環境許可データテーブル</h1>
            <p>太陽光発電施設に関する条例・許可情報（混合型 × 許可条項）</p>
        </div>
        <div class=\"controls\">
            <div class=\"search-box\">
                <input type=\"text\" id=\"searchInput\" placeholder=\"テーブル内を検索...\" />
            </div>
            <div class=\"stats\">表示中: <span id=\"displayCount\">0</span> / <span id=\"totalCount\">0</span> 件</div>
        </div>
        <div class=\"table-wrapper\">
            <table id=\"dataTable\">
                <thead>
                    <tr>
                        <th class=\"sortable\" data-column=\"paragraph_id\">段落ID</th>
                        <th class=\"sortable\" data-column=\"municipality\">市区町村</th>
                        <th class=\"sortable\" data-column=\"year\">年度</th>
                        <th class=\"sortable\" data-column=\"category\">カテゴリ</th>
                        <th class=\"sortable\" data-column=\"dan_number\">段番号</th>
                        <th class=\"sortable\" data-column=\"text\">テキスト</th>
                        <th class=\"sortable\" data-column=\"code\">コード</th>
                        <th class=\"sortable\" data-column=\"code_description\">コード説明</th>
                    </tr>
                </thead>
                <tbody id=\"tableBody\"></tbody>
            </table>
        </div>
        <div class=\"footer\"><p>データは CSV ファイルから自動生成されました。</p></div>
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
                    <td style="text-align:left;">${row.code ?? ''}</td>
                    <td style="text-align:left;">${row.code_description ?? ''}</td>
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


def convert_csv_to_html(csv_path: Path, out_path: Path):
    rows = []
    with csv_path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({
                'paragraph_id': safe_int(r.get('paragraph_id')),
                'municipality': r.get('municipality_name') or r.get('municipality') or '',
                'year': safe_int(r.get('year')) if str(r.get('year') or '').isdigit() else r.get('year'),
                'category': r.get('category'),
                'dan_number': safe_int(r.get('dan_number')),
                'text': r.get('text'),
                'code': '*CLAUSE_POSITIVE_PERMISSION_CONSENT',
                'code_description': None,
            })

    data_json = json.dumps(rows, ensure_ascii=False)
    html = TEMPLATE.replace('__DATA_JSON__', data_json)
    out_path.write_text(html, encoding='utf-8')


def safe_int(v):
    try:
        if v is None or v == '':
            return None
        return int(str(v).strip())
    except Exception:
        return v


if __name__ == '__main__':
    in_csv = Path('clause-viewer/mixed_regulation_positive_permission_paragraphs.csv')
    out_html = Path('clause-viewer/mixed_regulation_positive_permission_paragraphs.html')
    convert_csv_to_html(in_csv, out_html)
    print(f'Wrote {out_html}')

