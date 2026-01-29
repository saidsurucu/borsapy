"""
Düşük F/K ve Yükselen Kar Marjı Web Arayüzü
============================================

Bu örnek, tarama sonuçlarını interaktif bir web arayüzünde gösterir.

Kullanım:
    python examples/web_screener.py

    Tarayıcıda http://localhost:5000 adresine gidin.

Gereksinimler:
    pip install borsapy flask pandas
"""

import json
import threading
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request

import pandas as pd
import borsapy as bp

app = Flask(__name__)

# Global state for scan progress
scan_state = {
    "running": False,
    "progress": 0,
    "total": 0,
    "current_symbol": "",
    "results": [],
    "last_scan": None,
    "error": None,
}

# Banka ve finans sektörü hisseleri
BANK_SYMBOLS = {
    "AKBNK", "GARAN", "ISCTR", "VAKBN", "YKBNK", "HALKB", "SKBNK",
    "TSKB", "ALBRK", "QNBFB", "ICBCT", "KLNMA", "TEKFK", "SEKFK",
    "TURSG", "ANSGR", "AKGRT", "ANHYT", "AGESA", "ISFIN", "GARFA",
    "VAKFA", "ULUFA", "LIDFA", "GLCVY",
}

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BorsaPy - Hisse Tarama</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        * { font-family: 'Inter', sans-serif; }

        .gradient-bg {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }

        .card-hover {
            transition: all 0.3s ease;
        }

        .card-hover:hover {
            transform: translateY(-4px);
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }

        .pulse-dot {
            animation: pulse 2s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .progress-bar {
            transition: width 0.5s ease;
        }

        .fade-in {
            animation: fadeIn 0.5s ease;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .sparkline {
            display: flex;
            align-items: end;
            gap: 2px;
            height: 40px;
        }

        .sparkline-bar {
            flex: 1;
            border-radius: 2px;
            transition: all 0.3s ease;
        }

        .table-row:hover {
            background: linear-gradient(90deg, rgba(102, 126, 234, 0.05) 0%, rgba(118, 75, 162, 0.05) 100%);
        }
    </style>
</head>
<body class="bg-gray-50 min-h-screen">
    <!-- Header -->
    <header class="gradient-bg text-white shadow-lg">
        <div class="max-w-7xl mx-auto px-4 py-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center space-x-3">
                    <div class="bg-white/20 p-2 rounded-lg">
                        <i data-lucide="trending-up" class="w-8 h-8"></i>
                    </div>
                    <div>
                        <h1 class="text-2xl font-bold">BorsaPy Screener</h1>
                        <p class="text-white/80 text-sm">Düşük F/K & Yükselen Kar Marjı Taraması</p>
                    </div>
                </div>
                <div class="text-right text-sm text-white/80">
                    <div id="lastScan"></div>
                </div>
            </div>
        </div>
    </header>

    <main class="max-w-7xl mx-auto px-4 py-8">
        <!-- Filters -->
        <div class="bg-white rounded-2xl shadow-sm p-6 mb-8 card-hover">
            <div class="flex items-center mb-4">
                <i data-lucide="sliders" class="w-5 h-5 text-purple-600 mr-2"></i>
                <h2 class="text-lg font-semibold text-gray-800">Tarama Kriterleri</h2>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-4 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-600 mb-1">Maksimum F/K</label>
                    <input type="number" id="peMax" value="8" step="0.5" min="0" max="50"
                        class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-600 mb-1">Çeyrek Sayısı</label>
                    <select id="quarters" class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition">
                        <option value="2">Son 2 Çeyrek</option>
                        <option value="3" selected>Son 3 Çeyrek</option>
                        <option value="4">Son 4 Çeyrek</option>
                    </select>
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-600 mb-1">Endeks</label>
                    <select id="indexFilter" class="w-full px-4 py-2 border border-gray-200 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-transparent transition">
                        <option value="">Tüm BIST</option>
                        <option value="XU030">BIST 30</option>
                        <option value="XU050">BIST 50</option>
                        <option value="XU100">BIST 100</option>
                    </select>
                </div>
                <div class="flex items-end">
                    <button id="scanBtn" onclick="startScan()"
                        class="w-full bg-gradient-to-r from-purple-600 to-indigo-600 text-white px-6 py-2 rounded-lg font-medium hover:from-purple-700 hover:to-indigo-700 transition flex items-center justify-center space-x-2">
                        <i data-lucide="search" class="w-4 h-4"></i>
                        <span>Taramayı Başlat</span>
                    </button>
                </div>
            </div>
        </div>

        <!-- Progress -->
        <div id="progressSection" class="hidden bg-white rounded-2xl shadow-sm p-6 mb-8">
            <div class="flex items-center justify-between mb-4">
                <div class="flex items-center">
                    <div class="w-3 h-3 bg-purple-600 rounded-full pulse-dot mr-3"></div>
                    <span class="font-medium text-gray-800">Tarama Devam Ediyor</span>
                </div>
                <span id="progressText" class="text-sm text-gray-500">0 / 0</span>
            </div>
            <div class="w-full bg-gray-200 rounded-full h-2 mb-2">
                <div id="progressBar" class="progress-bar bg-gradient-to-r from-purple-600 to-indigo-600 h-2 rounded-full" style="width: 0%"></div>
            </div>
            <p id="currentSymbol" class="text-sm text-gray-500"></p>
        </div>

        <!-- Stats Cards -->
        <div id="statsSection" class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8 hidden">
            <div class="bg-white rounded-xl shadow-sm p-5 card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">Bulunan Hisse</p>
                        <p id="statTotal" class="text-2xl font-bold text-gray-800">0</p>
                    </div>
                    <div class="bg-purple-100 p-3 rounded-lg">
                        <i data-lucide="layers" class="w-6 h-6 text-purple-600"></i>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-xl shadow-sm p-5 card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">Ortalama F/K</p>
                        <p id="statAvgPE" class="text-2xl font-bold text-gray-800">0</p>
                    </div>
                    <div class="bg-blue-100 p-3 rounded-lg">
                        <i data-lucide="calculator" class="w-6 h-6 text-blue-600"></i>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-xl shadow-sm p-5 card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">En Düşük F/K</p>
                        <p id="statMinPE" class="text-2xl font-bold text-gray-800">0</p>
                    </div>
                    <div class="bg-green-100 p-3 rounded-lg">
                        <i data-lucide="trending-down" class="w-6 h-6 text-green-600"></i>
                    </div>
                </div>
            </div>
            <div class="bg-white rounded-xl shadow-sm p-5 card-hover">
                <div class="flex items-center justify-between">
                    <div>
                        <p class="text-sm text-gray-500">En Yüksek Marj Artışı</p>
                        <p id="statMaxGrowth" class="text-2xl font-bold text-gray-800">0%</p>
                    </div>
                    <div class="bg-orange-100 p-3 rounded-lg">
                        <i data-lucide="rocket" class="w-6 h-6 text-orange-600"></i>
                    </div>
                </div>
            </div>
        </div>

        <!-- Results Table -->
        <div id="resultsSection" class="bg-white rounded-2xl shadow-sm overflow-hidden hidden">
            <div class="p-6 border-b border-gray-100">
                <div class="flex items-center justify-between">
                    <div class="flex items-center">
                        <i data-lucide="table" class="w-5 h-5 text-purple-600 mr-2"></i>
                        <h2 class="text-lg font-semibold text-gray-800">Sonuçlar</h2>
                    </div>
                    <button onclick="exportCSV()" class="text-sm text-purple-600 hover:text-purple-700 flex items-center space-x-1">
                        <i data-lucide="download" class="w-4 h-4"></i>
                        <span>CSV İndir</span>
                    </button>
                </div>
            </div>

            <div class="overflow-x-auto">
                <table class="w-full">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Hisse</th>
                            <th class="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">F/K</th>
                            <th class="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Kar Marjı Trendi</th>
                            <th class="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Dönemler</th>
                            <th class="px-6 py-4 text-left text-xs font-semibold text-gray-500 uppercase tracking-wider">Değişim</th>
                        </tr>
                    </thead>
                    <tbody id="resultsBody" class="divide-y divide-gray-100">
                    </tbody>
                </table>
            </div>
        </div>

        <!-- Empty State -->
        <div id="emptyState" class="text-center py-16">
            <div class="bg-gray-100 w-20 h-20 rounded-full flex items-center justify-center mx-auto mb-4">
                <i data-lucide="search" class="w-10 h-10 text-gray-400"></i>
            </div>
            <h3 class="text-lg font-medium text-gray-800 mb-2">Tarama Başlatın</h3>
            <p class="text-gray-500 max-w-md mx-auto">
                Yukarıdaki kriterleri belirleyip taramayı başlatın. Düşük F/K oranına sahip ve kar marjı yükselen hisseleri bulacağız.
            </p>
        </div>
    </main>

    <!-- Footer -->
    <footer class="bg-white border-t border-gray-100 mt-12">
        <div class="max-w-7xl mx-auto px-4 py-6">
            <div class="flex items-center justify-between text-sm text-gray-500">
                <div class="flex items-center space-x-2">
                    <span>Powered by</span>
                    <a href="https://github.com/saidsurucu/borsapy" target="_blank" class="text-purple-600 hover:text-purple-700 font-medium">BorsaPy</a>
                </div>
                <div class="flex items-center space-x-1">
                    <i data-lucide="alert-triangle" class="w-4 h-4"></i>
                    <span>Yalnızca eğitim amaçlıdır. Yatırım tavsiyesi değildir.</span>
                </div>
            </div>
        </div>
    </footer>

    <script>
        // Initialize Lucide icons
        lucide.createIcons();

        let scanResults = [];
        let pollInterval = null;

        function startScan() {
            const peMax = document.getElementById('peMax').value;
            const quarters = document.getElementById('quarters').value;
            const indexFilter = document.getElementById('indexFilter').value;

            // Disable button
            const btn = document.getElementById('scanBtn');
            btn.disabled = true;
            btn.innerHTML = '<i data-lucide="loader" class="w-4 h-4 animate-spin"></i><span>Taranıyor...</span>';
            lucide.createIcons();

            // Show progress
            document.getElementById('progressSection').classList.remove('hidden');
            document.getElementById('emptyState').classList.add('hidden');
            document.getElementById('resultsSection').classList.add('hidden');
            document.getElementById('statsSection').classList.add('hidden');

            // Start scan
            fetch('/api/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pe_max: parseFloat(peMax), quarters: parseInt(quarters), index: indexFilter })
            });

            // Poll for progress
            pollInterval = setInterval(pollProgress, 500);
        }

        function pollProgress() {
            fetch('/api/progress')
                .then(res => res.json())
                .then(data => {
                    if (data.running) {
                        const percent = data.total > 0 ? (data.progress / data.total * 100) : 0;
                        document.getElementById('progressBar').style.width = percent + '%';
                        document.getElementById('progressText').textContent = `${data.progress} / ${data.total}`;
                        document.getElementById('currentSymbol').textContent = `İnceleniyor: ${data.current_symbol}`;
                    } else {
                        clearInterval(pollInterval);

                        // Hide progress
                        document.getElementById('progressSection').classList.add('hidden');

                        // Re-enable button
                        const btn = document.getElementById('scanBtn');
                        btn.disabled = false;
                        btn.innerHTML = '<i data-lucide="search" class="w-4 h-4"></i><span>Taramayı Başlat</span>';
                        lucide.createIcons();

                        // Show results
                        if (data.results && data.results.length > 0) {
                            scanResults = data.results;
                            displayResults(data.results);
                            updateStats(data.results);
                            document.getElementById('resultsSection').classList.remove('hidden');
                            document.getElementById('statsSection').classList.remove('hidden');
                        } else {
                            document.getElementById('emptyState').classList.remove('hidden');
                            document.getElementById('emptyState').querySelector('h3').textContent = 'Sonuç Bulunamadı';
                            document.getElementById('emptyState').querySelector('p').textContent = 'Kriterlere uyan hisse bulunamadı. Filtreleri gevşetmeyi deneyin.';
                        }

                        if (data.last_scan) {
                            document.getElementById('lastScan').textContent = `Son tarama: ${data.last_scan}`;
                        }
                    }
                });
        }

        function displayResults(results) {
            const tbody = document.getElementById('resultsBody');
            tbody.innerHTML = '';

            results.forEach((row, idx) => {
                const margins = [row.margin_q1, row.margin_q2, row.margin_q3].filter(m => m !== null);
                const change = margins.length >= 2 ? margins[margins.length - 1] - margins[0] : 0;
                const changePercent = margins[0] !== 0 ? ((margins[margins.length - 1] - margins[0]) / Math.abs(margins[0]) * 100) : 0;

                const tr = document.createElement('tr');
                tr.className = 'table-row fade-in';
                tr.style.animationDelay = `${idx * 50}ms`;

                tr.innerHTML = `
                    <td class="px-6 py-4">
                        <div class="flex items-center space-x-3">
                            <div class="bg-gradient-to-br from-purple-500 to-indigo-600 text-white w-10 h-10 rounded-lg flex items-center justify-center font-bold text-sm">
                                ${row.symbol.substring(0, 2)}
                            </div>
                            <div>
                                <div class="font-semibold text-gray-800">${row.symbol}</div>
                                <div class="text-sm text-gray-500 truncate max-w-[200px]">${row.name || ''}</div>
                            </div>
                        </div>
                    </td>
                    <td class="px-6 py-4">
                        <span class="inline-flex items-center px-3 py-1 rounded-full text-sm font-medium bg-green-100 text-green-800">
                            ${row.pe ? row.pe.toFixed(2) : 'N/A'}
                        </span>
                    </td>
                    <td class="px-6 py-4">
                        <div class="sparkline">
                            ${margins.map((m, i) => {
                                const height = Math.min(100, Math.max(10, (m + 50) * 0.8));
                                const color = m >= 0 ? 'bg-green-400' : 'bg-red-400';
                                return `<div class="sparkline-bar ${color}" style="height: ${height}%" title="${m.toFixed(1)}%"></div>`;
                            }).join('')}
                        </div>
                        <div class="text-xs text-gray-500 mt-1">
                            ${margins.map(m => m.toFixed(1) + '%').join(' → ')}
                        </div>
                    </td>
                    <td class="px-6 py-4 text-sm text-gray-600">
                        ${row.quarters || ''}
                    </td>
                    <td class="px-6 py-4">
                        <span class="inline-flex items-center text-sm font-medium ${change >= 0 ? 'text-green-600' : 'text-red-600'}">
                            ${change >= 0 ? '↑' : '↓'} ${Math.abs(change).toFixed(1)} puan
                        </span>
                    </td>
                `;

                tbody.appendChild(tr);
            });
        }

        function updateStats(results) {
            document.getElementById('statTotal').textContent = results.length;

            const pes = results.map(r => r.pe).filter(p => p !== null);
            const avgPE = pes.length > 0 ? (pes.reduce((a, b) => a + b, 0) / pes.length).toFixed(2) : '0';
            document.getElementById('statAvgPE').textContent = avgPE;

            const minPE = pes.length > 0 ? Math.min(...pes).toFixed(2) : '0';
            document.getElementById('statMinPE').textContent = minPE;

            let maxGrowth = 0;
            results.forEach(r => {
                const margins = [r.margin_q1, r.margin_q2, r.margin_q3].filter(m => m !== null);
                if (margins.length >= 2) {
                    const growth = margins[margins.length - 1] - margins[0];
                    if (growth > maxGrowth) maxGrowth = growth;
                }
            });
            document.getElementById('statMaxGrowth').textContent = maxGrowth.toFixed(1) + ' puan';
        }

        function exportCSV() {
            if (scanResults.length === 0) return;

            const headers = ['symbol', 'name', 'pe', 'margin_q1', 'margin_q2', 'margin_q3', 'quarters'];
            const rows = scanResults.map(r => headers.map(h => r[h] || '').join(','));
            const csv = [headers.join(','), ...rows].join('\\n');

            const blob = new Blob([csv], { type: 'text/csv' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'tarama_sonuclari.csv';
            a.click();
        }

        // Check for existing results on load
        fetch('/api/progress')
            .then(res => res.json())
            .then(data => {
                if (data.results && data.results.length > 0 && !data.running) {
                    scanResults = data.results;
                    displayResults(data.results);
                    updateStats(data.results);
                    document.getElementById('resultsSection').classList.remove('hidden');
                    document.getElementById('statsSection').classList.remove('hidden');
                    document.getElementById('emptyState').classList.add('hidden');

                    if (data.last_scan) {
                        document.getElementById('lastScan').textContent = `Son tarama: ${data.last_scan}`;
                    }
                }
            });
    </script>
</body>
</html>
"""


def calculate_net_margin(income_stmt: pd.DataFrame) -> pd.Series:
    """Gelir tablosundan net kar marjını hesapla."""
    revenue_keywords = ["Satış Gelirleri", "Hasılat", "Net Satışlar"]
    net_income_keywords = [
        "Ana Ortaklık Payları",
        "SÜRDÜRÜLEN FAALİYETLER DÖNEM KARI",
        "Dönem Net Kar",
        "Net Dönem Karı",
    ]

    index_list = income_stmt.index.tolist()
    revenue_idx = None
    net_income_idx = None

    for keyword in revenue_keywords:
        for idx in index_list:
            if keyword.lower() in str(idx).lower():
                revenue_idx = idx
                break
        if revenue_idx:
            break

    for keyword in net_income_keywords:
        for idx in index_list:
            if keyword.lower() in str(idx).lower():
                net_income_idx = idx
                break
        if net_income_idx:
            break

    if revenue_idx is None or net_income_idx is None:
        return pd.Series(dtype=float)

    quarter_cols = [col for col in income_stmt.columns if "Q" in str(col)]
    margins = {}

    for col in quarter_cols:
        try:
            revenue = float(income_stmt.loc[revenue_idx, col])
            net_income = float(income_stmt.loc[net_income_idx, col])
            if revenue != 0 and pd.notna(revenue) and pd.notna(net_income):
                margins[col] = (net_income / revenue) * 100
        except (ValueError, TypeError, KeyError):
            continue

    return pd.Series(margins)


def is_margin_increasing(margins: pd.Series, last_n: int = 3) -> bool:
    """Son n çeyrekte kar marjının yükselme eğiliminde olup olmadığını kontrol et."""
    if len(margins) < last_n:
        return False

    recent = margins.head(last_n).sort_index()
    values = recent.values

    for i in range(1, len(values)):
        if values[i] <= values[i - 1]:
            return False

    return True


def run_scan(pe_max: float, quarters: int, index: str | None):
    """Taramayı arka planda çalıştır."""
    global scan_state

    scan_state["running"] = True
    scan_state["progress"] = 0
    scan_state["results"] = []
    scan_state["error"] = None

    try:
        # Düşük F/K'lı hisseleri bul
        screener = bp.Screener()
        screener.add_filter("pe", min=0, max=pe_max)

        if index:
            screener.set_index(index)

        low_pe_stocks = screener.run()

        if low_pe_stocks.empty:
            scan_state["running"] = False
            scan_state["last_scan"] = datetime.now().strftime("%H:%M:%S")
            return

        scan_state["total"] = len(low_pe_stocks)
        results = []

        for idx, row in low_pe_stocks.iterrows():
            symbol = row["symbol"]
            name = row.get("name", "")
            pe = row.get("pe") or row.get("criteria_28") or row.get("pe_ratio")

            scan_state["progress"] = idx + 1
            scan_state["current_symbol"] = symbol

            if symbol in BANK_SYMBOLS:
                continue

            try:
                ticker = bp.Ticker(symbol)
                income_stmt = ticker.get_income_stmt(quarterly=True)

                if income_stmt.empty:
                    continue

                margins = calculate_net_margin(income_stmt)

                if margins.empty:
                    continue

                if is_margin_increasing(margins, last_n=quarters):
                    recent_margins = margins.head(quarters).sort_index()
                    margin_values = recent_margins.values
                    margin_quarters = recent_margins.index.tolist()

                    results.append({
                        "symbol": symbol,
                        "name": name,
                        "pe": pe,
                        "margin_q1": margin_values[0] if len(margin_values) > 0 else None,
                        "margin_q2": margin_values[1] if len(margin_values) > 1 else None,
                        "margin_q3": margin_values[2] if len(margin_values) > 2 else None,
                        "quarters": " → ".join(margin_quarters),
                    })

            except Exception:
                continue

        scan_state["results"] = results
        scan_state["last_scan"] = datetime.now().strftime("%H:%M:%S")

    except Exception as e:
        scan_state["error"] = str(e)

    finally:
        scan_state["running"] = False


@app.route("/")
def home():
    return render_template_string(HTML_TEMPLATE)


@app.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.json
    pe_max = data.get("pe_max", 8.0)
    quarters = data.get("quarters", 3)
    index = data.get("index") or None

    # Start scan in background thread
    thread = threading.Thread(target=run_scan, args=(pe_max, quarters, index))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "started"})


@app.route("/api/progress")
def api_progress():
    return jsonify(scan_state)


def main():
    print("=" * 60)
    print("BorsaPy - Web Tarama Arayüzü")
    print("=" * 60)
    print()
    print("🌐 Tarayıcıda açın: http://localhost:8080")
    print()
    print("Durdurmak için Ctrl+C")
    print("=" * 60)

    app.run(debug=False, port=8080)


if __name__ == "__main__":
    main()
