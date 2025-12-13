import React, { useState, useMemo, useEffect } from 'react';
import { Search, Filter, Upload, FileText, Database, List, Info, AlertCircle, CheckCircle, XCircle } from
'lucide-react';

// 初期サンプルデータは空にしておきます
const SAMPLE_CSV_TEXT = ``;

// CSVパーサー（引用符付きフィールドに対応）
const parseCSV = (text) => {
const rows = [];
let currentRow = [];
let currentCell = '';
let insideQuotes = false;

for (let i = 0; i < text.length; i++) { const char=text[i]; const nextChar=text[i + 1]; if (char==='"' ) { if
    (insideQuotes && nextChar==='"' ) { currentCell +='"' ; i++; // エスケープされた引用符をスキップ } else {
    insideQuotes=!insideQuotes; } } else if (char===',' && !insideQuotes) { currentRow.push(currentCell.trim());
    currentCell='' ; } else if ((char==='\r' || char==='\n' ) && !insideQuotes) { if (currentCell || currentRow.length>
    0) {
    currentRow.push(currentCell.trim());
    rows.push(currentRow);
    currentRow = [];
    currentCell = '';
    }
    if (char === '\r' && nextChar === '\n') i++;
    } else {
    currentCell += char;
    }
    }
    if (currentCell || currentRow.length > 0) {
    currentRow.push(currentCell.trim());
    rows.push(currentRow);
    }
    return rows;
    };

    const App = () => {
    const [csvData, setCsvData] = useState([]);
    // const [headers, setHeaders] = useState([]); // 未使用のためコメントアウト
    const [filterText, setFilterText] = useState('');
    const [selectedCategory, setSelectedCategory] = useState('All');
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    // データ内に特定のカラムが存在するかどうかのフラグ
    const [hasPermissionFileCol, setHasPermissionFileCol] = useState(false);

    // 初期化時は空の状態
    useEffect(() => {
    if (SAMPLE_CSV_TEXT) {
    processCSV(SAMPLE_CSV_TEXT);
    }
    }, []);

    const processCSV = (text) => {
    try {
    setLoading(true);
    setError(null);
    const rows = parseCSV(text);
    if (rows.length < 2) { if (rows.length===0 && !text.trim()) { setLoading(false); return; }
        setError("有効なデータが見つかりません。CSV形式を確認してください。"); setLoading(false); return; } // ヘッダーとボディの分離 const
        headerRow=rows[0].map(h=> h.replace(/^[\uFEFF\s]+|[\s]+$/g, ''));
        const bodyRows = rows.slice(1).filter(r => r.length === headerRow.length);

        // 許可ファイル列があるかチェック (in_permission_file)
        const permissionFileIndex = headerRow.findIndex(h => h === 'in_permission_file');
        setHasPermissionFileCol(permissionFileIndex !== -1);

        const formattedData = bodyRows.map((row, index) => {
        const obj = { id: index };
        headerRow.forEach((header, i) => {
        obj[header] = row[i];
        });

        // カラム名の揺らぎを吸収して標準的なプロパティを追加
        // 自治体名
        obj._municipality = obj.municipality || obj.municipality_name || '';
        // テキスト
        obj._text = obj.text || '';
        // 条件
        obj._conditions = obj.conditions || obj.matched_condition || '';
        // 分類
        obj._category = obj.category || '';
        // 許可ファイルフラグ
        obj._permission = obj.in_permission_file || '';

        return obj;
        });

        // setHeaders(headerRow);
        setCsvData(formattedData);
        setLoading(false);
        } catch (e) {
        console.error(e);
        setError("CSVの解析中にエラーが発生しました。");
        setLoading(false);
        }
        };

        const handleFileUpload = (event) => {
        const file = event.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (e) => {
        processCSV(e.target.result);
        };
        reader.readAsText(file);
        };

        // フィルタリングロジック
        const filteredData = useMemo(() => {
        return csvData.filter(item => {
        const matchText = filterText.toLowerCase();

        const matchesSearch =
        item._municipality.toLowerCase().includes(matchText) ||
        item._text.toLowerCase().includes(matchText);

        const matchesCategory = selectedCategory === 'All' || item._category === selectedCategory;

        return matchesSearch && matchesCategory;
        });
        }, [csvData, filterText, selectedCategory]);

        // ユニークなカテゴリの抽出
        const uniqueCategories = useMemo(() => {
        const categories = new Set(csvData.map(d => d._category).filter(Boolean));
        return Array.from(categories).sort();
        }, [csvData]);

        // 色分けロジック
        const getCategoryColor = (category) => {
        if (!category) return 'bg-gray-100 text-gray-800';

        // 旧データの分類
        if (category.includes('絶対禁止')) return 'bg-red-100 text-red-800 border-red-200';
        if (category.includes('条件付き禁止')) return 'bg-orange-100 text-orange-800 border-orange-200';
        if (category.includes('許可制')) return 'bg-yellow-100 text-yellow-800 border-yellow-200';
        if (category.includes('届出')) return 'bg-blue-100 text-blue-800 border-blue-200';
        if (category.includes('区域指定のみ')) return 'bg-green-100 text-green-800 border-green-200';

        // 新データの分類
        if (category.includes('条例')) return 'bg-indigo-100 text-indigo-800 border-indigo-200';
        if (category.includes('規則') || category.includes('施行規則')) return 'bg-purple-100 text-purple-800 border-purple-200';
        if (category.includes('要綱')) return 'bg-teal-100 text-teal-800 border-teal-200';

        return 'bg-gray-100 text-gray-800 border-gray-200';
        };

        const hasData = csvData.length > 0;

        return (
        <div className="min-h-screen bg-slate-50 text-slate-900 font-sans">
            {/* Header */}
            <header className="bg-white border-b border-slate-200 sticky top-0 z-10 shadow-sm">
                <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
                    <div className="flex items-center gap-2">
                        <Database className="w-6 h-6 text-indigo-600" />
                        <h1 className="text-xl font-bold text-slate-800">自治体条例区分ダッシュボード</h1>
                    </div>
                    <div className="text-sm text-slate-500 hidden sm:block">
                        {hasData ? `${csvData.length} 件のデータ` : 'データ未ロード'}
                    </div>
                </div>
            </header>

            <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

                {/* Controls Section */}
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 mb-8">
                    <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-end">

                        {/* Search Input */}
                        <div className="md:col-span-5 space-y-2">
                            <label className="text-sm font-semibold text-slate-700 flex items-center gap-1">
                                <Search className="w-4 h-4" /> キーワード検索
                            </label>
                            <input type="text" placeholder="自治体名や条文テキストで検索..."
                                className="w-full px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 transition-colors disabled:bg-slate-100 disabled:text-slate-400"
                                value={filterText} onChange={(e)=> setFilterText(e.target.value)}
                            disabled={!hasData}
                            />
                        </div>

                        {/* Category Dropdown */}
                        <div className="md:col-span-4 space-y-2">
                            <label className="text-sm font-semibold text-slate-700 flex items-center gap-1">
                                <Filter className="w-4 h-4" /> 分類で絞り込み
                            </label>
                            <div className="relative">
                                <select
                                    className="w-full appearance-none px-4 py-2 rounded-lg border border-slate-300 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500 bg-white transition-colors cursor-pointer disabled:bg-slate-100 disabled:text-slate-400"
                                    value={selectedCategory} onChange={(e)=> setSelectedCategory(e.target.value)}
                                    disabled={!hasData}
                                    >
                                    <option value="All">すべての分類を表示</option>
                                    {uniqueCategories.map(cat => (
                                    <option key={cat} value={cat}>{cat}</option>
                                    ))}
                                </select>
                                <div
                                    className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-2 text-slate-500">
                                    <svg className="fill-current h-4 w-4" xmlns="http://www.w3.org/2000/svg"
                                        viewBox="0 0 20 20">
                                        <path
                                            d="M9.293 12.95l.707.707L15.657 8l-1.414-1.414L10 10.828 5.757 6.586 4.343 8z" />
                                    </svg>
                                </div>
                            </div>
                        </div>

                        {/* File Upload Button */}
                        <div className="md:col-span-3">
                            <label
                                className="flex items-center justify-center w-full px-4 py-2 bg-indigo-50 text-indigo-700 rounded-lg border border-indigo-200 hover:bg-indigo-100 cursor-pointer transition-colors font-medium text-sm">
                                <Upload className="w-4 h-4 mr-2" />
                                CSVをアップロード
                                <input type="file" accept=".csv" onChange={handleFileUpload} className="hidden" />
                            </label>
                        </div>
                    </div>
                </div>

                {/* Status Messages */}
                {loading && (
                <div className="p-8 text-center text-slate-500">
                    <div
                        className="animate-spin inline-block w-8 h-8 border-4 border-indigo-500 border-t-transparent rounded-full mb-2">
                    </div>
                    <p>データを読み込み中...</p>
                </div>
                )}

                {error && (
                <div
                    className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg flex items-center gap-2 mb-6">
                    <AlertCircle className="w-5 h-5" />
                    {error}
                </div>
                )}

                {!hasData && !loading && !error && (
                <div className="text-center py-12 bg-slate-50 rounded-xl border border-dashed border-slate-300">
                    <Database className="w-12 h-12 mx-auto text-slate-300 mb-4" />
                    <h3 className="text-lg font-medium text-slate-900 mb-1">データが読み込まれていません</h3>
                    <p className="text-slate-500 mb-4">右上のボタンからCSVファイルをアップロードしてください</p>
                </div>
                )}

                {/* Results Info */}
                {hasData && !loading && !error && (
                <div className="flex items-center justify-between mb-4">
                    <h2 className="text-lg font-bold text-slate-800 flex items-center gap-2">
                        <List className="w-5 h-5 text-slate-500" />
                        検索結果
                    </h2>
                    <span className="bg-slate-100 text-slate-600 px-3 py-1 rounded-full text-sm font-medium">
                        {filteredData.length} 件
                    </span>
                </div>
                )}

                {/* Data Table */}
                {hasData && !loading && !error && (
                <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
                    <div className="overflow-x-auto">
                        <table className="w-full text-left border-collapse">
                            <thead>
                                <tr
                                    className="bg-slate-50 border-b border-slate-200 text-slate-500 text-xs uppercase tracking-wider">
                                    <th className="px-6 py-4 font-semibold w-40 min-w-[160px]">自治体名</th>
                                    <th className="px-6 py-4 font-semibold w-32 min-w-[120px]">分類</th>
                                    <th className="px-6 py-4 font-semibold min-w-[400px]">条文 / テキスト</th>
                                    <th className="px-6 py-4 font-semibold min-w-[200px]">条件 (Conditions)</th>
                                    {hasPermissionFileCol && (
                                    <th className="px-6 py-4 font-semibold w-32 text-center">許可ファイル</th>
                                    )}
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-slate-100">
                                {filteredData.length > 0 ? (
                                filteredData.map((row) => (
                                <tr key={row.id} className="hover:bg-slate-50 transition-colors">
                                    <td className="px-6 py-4 align-top">
                                        <div className="font-bold text-slate-900 text-lg sticky left-0">
                                            {row._municipality}
                                        </div>
                                    </td>
                                    <td className="px-6 py-4 align-top">
                                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs
                                            font-medium border ${getCategoryColor(row._category)}`}>
                                            {row._category}
                                        </span>
                                    </td>
                                    <td className="px-6 py-4 align-top">
                                        {/* textカラムがあれば表示、なければプレースホルダー */}
                                        {row._text ? (
                                        <div
                                            className="text-sm text-slate-700 whitespace-pre-wrap leading-relaxed max-h-60 overflow-y-auto pr-2 custom-scrollbar">
                                            {row._text}
                                        </div>
                                        ) : (
                                        <span className="text-slate-400 text-xs italic">テキストなし</span>
                                        )}
                                    </td>
                                    <td className="px-6 py-4 align-top">
                                        <div className="flex flex-wrap gap-2">
                                            {row._conditions && row._conditions.split(/,|、/).map((cond, i) => {
                                            const cleanCond = cond.trim();
                                            // コーディング用タグ（*で始まるもの）を除外して表示する場合
                                            // if (cleanCond.startsWith('*')) return null;
                                            if (!cleanCond) return null;

                                            return (
                                            <span key={i}
                                                className="inline-flex items-center px-2 py-1 rounded text-xs bg-slate-100 text-slate-600 border border-slate-200">
                                                {cleanCond}
                                            </span>
                                            );
                                            })}
                                        </div>
                                    </td>
                                    {hasPermissionFileCol && (
                                    <td className="px-6 py-4 align-top text-center">
                                        {row._permission === 'True' || row._permission === 'TRUE' ? (
                                        <div
                                            className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-teal-50 text-teal-700 border border-teal-200">
                                            <CheckCircle className="w-3 h-3 mr-1" />
                                            あり
                                        </div>
                                        ) : (
                                        <div
                                            className="inline-flex items-center px-2.5 py-1 rounded-full text-xs font-medium bg-slate-100 text-slate-500 border border-slate-200">
                                            <XCircle className="w-3 h-3 mr-1" />
                                            なし
                                        </div>
                                        )}
                                    </td>
                                    )}
                                </tr>
                                ))
                                ) : (
                                <tr>
                                    <td colSpan={hasPermissionFileCol ? 5 : 4}
                                        className="px-6 py-12 text-center text-slate-500">
                                        <FileText className="w-12 h-12 mx-auto mb-3 text-slate-300" />
                                        <p>条件に一致するデータが見つかりませんでした。</p>
                                    </td>
                                </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>
                )}
            </main>

            {/* Scrollbar styling specifically for this component */}
            <style>
                {
                    ` .custom-scrollbar::-webkit-scrollbar {
                        width: 6px;
                    }

                    .custom-scrollbar::-webkit-scrollbar-track {
                        background: #f1f5f9;
                    }

                    .custom-scrollbar::-webkit-scrollbar-thumb {
                        background: #cbd5e1;
                        border-radius: 3px;
                    }

                    .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                        background: #94a3b8;
                    }

                    `
                }
            </style>
        </div>
        );
        };

        export default App;