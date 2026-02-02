
const API_BASE = "http://127.0.0.1:8000/api";
const WS_URL = "ws://127.0.0.1:8000/ws";

let selectedSymbol = null;
let marketData = {};
let chart = null;
let candleSeries = null;
let activeTimeframe = "M5";
let chartDataInterval = null;
let pnlChartInstance = null;
let socket = null;

// --- WebSocket Init ---
function initWebSocket() {
    socket = new WebSocket(WS_URL);

    socket.onopen = () => {
        console.log("WebSocket Connected");
        document.getElementById('conn-status').innerText = "Connected";
        document.getElementById('conn-status').style.color = "var(--success)";
        document.getElementById('conn-status').style.background = "rgba(16, 185, 129, 0.2)";
    };

    socket.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        if (msg.type === "MARKET_DATA") {
            // Merge update
            marketData = { ...marketData, ...msg.data };
            updateUI();
        } else if (msg.type === "STATUS") {
            updateStatusUI(msg.data);
        }
    };

    socket.onclose = () => {
        console.log("WebSocket Disconnected. Reconnecting...");
        document.getElementById('conn-status').innerText = "Disconnected";
        document.getElementById('conn-status').style.color = "var(--danger)";
        setTimeout(initWebSocket, 3000);
    };

    socket.onerror = (error) => {
        console.error("WebSocket Error", error);
    };
}

function updateStatusUI(data) {
    document.getElementById('acc-balance').innerText = `$${data.balance.toLocaleString()}`;
    document.getElementById('acc-equity').innerText = `$${data.equity.toLocaleString()}`;
    document.getElementById('clock-broker').innerText = data.broker_time_str || "--:--:--";
}

function updateUI() {
    // 1. Update Grid if visible
    if (!document.getElementById('market-grid-container').classList.contains('hidden')) {
        renderGrid();
    }

    // 2. Update Side Panel if visible
    if (selectedSymbol && !document.getElementById('workspace-container').classList.contains('hidden')) {
        if (marketData[selectedSymbol]) {
            const d = marketData[selectedSymbol];
            document.getElementById('lp-bid').innerText = d.bid.toFixed(5);
            document.getElementById('lp-ask').innerText = d.ask.toFixed(5);
        }
    }
}

// --- Navigation ---
function switchView(viewName) {
    if (viewName === 'analytics') loadAnalytics();

    // Default hiding
    document.querySelectorAll('.view-section').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.nav-btn').forEach(el => el.classList.remove('active'));

    // Workspce logic
    if (viewName === 'dashboard') {
        document.getElementById('view-dashboard').classList.remove('hidden');
        if (selectedSymbol) {
            // Ideally we stay in workspace if already there?
            // Or user clicked "Market Overview" explicitly to go back?
            // Usually clicking the Tab means "Go to Overview"
            closeWorkspace();
        } else {
            document.getElementById('market-grid-container').classList.remove('hidden');
            document.getElementById('workspace-container').classList.add('hidden');
        }
    } else {
        const target = document.getElementById(`view-${viewName}`);
        if (target) target.classList.remove('hidden');
    }

    const btn = Array.from(document.querySelectorAll('.nav-btn')).find(b => b.onclick && b.onclick.toString().includes(viewName));
    if (btn) btn.classList.add('active');
}

// --- Chart Logic ---
function initChart() {
    if (chart) return;
    const chartContainer = document.getElementById('tv-chart');
    if (!chartContainer) return;

    chart = LightweightCharts.createChart(chartContainer, {
        width: chartContainer.clientWidth,
        height: chartContainer.clientHeight,
        layout: { background: { color: '#09090b' }, textColor: '#a1a1aa' },
        grid: { vertLines: { color: '#18181b' }, horzLines: { color: '#18181b' } },
        timeScale: { timeVisible: true, secondsVisible: false, borderColor: '#27272a' },
        rightPriceScale: { borderColor: '#27272a' }
    });

    candleSeries = chart.addCandlestickSeries({
        upColor: '#10b981', downColor: '#ef4444', borderVisible: false, wickUpColor: '#10b981', wickDownColor: '#ef4444',
    });

    new ResizeObserver(entries => {
        if (entries.length === 0 || !entries[0].contentRect) return;
        chart.applyOptions({ width: entries[0].contentRect.width, height: entries[0].contentRect.height });
    }).observe(chartContainer);
}

async function loadChartData(symbol, tf) {
    try {
        const res = await fetch(`${API_BASE}/chart_data?symbol=${symbol}&timeframe=${tf}`);
        const data = await res.json();
        if (candleSeries) candleSeries.setData(data);
    } catch (e) { console.error("Chart load error", e); }
}

function changeTimeframe(tf) {
    activeTimeframe = tf;
    document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
    const btn = Array.from(document.querySelectorAll('.tf-btn')).find(b => b.innerText === tf);
    if (btn) btn.classList.add('active');

    if (selectedSymbol) loadChartData(selectedSymbol, activeTimeframe);
}

// --- Workspace Logic ---
function openWorkspace(symbol) {
    selectedSymbol = symbol;

    // UI Switch
    document.getElementById('market-grid-container').classList.add('hidden');
    document.getElementById('workspace-container').classList.remove('hidden');

    document.getElementById('chart-symbol-name').innerText = symbol;

    // Slight delay to allow DOM to calculate layout dimensions before Chart Init
    requestAnimationFrame(() => {
        if (!chart) initChart();

        // Force Resize
        const container = document.getElementById('tv-chart');
        if (chart && container) {
            chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
        }

        loadChartData(symbol, activeTimeframe);
    });

    // Poll Chart Data separately (since WS sends only tick/indicators, usually chart needs full OHLC history update)
    if (chartDataInterval) clearInterval(chartDataInterval);
    chartDataInterval = setInterval(() => {
        if (selectedSymbol && !document.getElementById('workspace-container').classList.contains('hidden')) {
            loadChartData(selectedSymbol, activeTimeframe);
        }
    }, 5000);

    // Reset Panel
    document.getElementById('ai-content').innerText = "Ready. Click Analyze.";
    document.getElementById('lp-bid').innerText = "...";
    document.getElementById('lp-ask').innerText = "...";
}

function closeWorkspace() {
    selectedSymbol = null;
    document.getElementById('workspace-container').classList.add('hidden');
    document.getElementById('market-grid-container').classList.remove('hidden');
    renderGrid(); // Force re-render immediately
    if (chartDataInterval) clearInterval(chartDataInterval);
}

// --- Grid Renderer ---
function renderGrid() {
    const grid = document.getElementById('ticker-grid');
    if (!grid) return;

    // Simple Diff Logic: Clear and rebuild is easiest, but heavy. 
    // Optimization: Check if card exists.

    Object.keys(marketData).forEach(symbol => {
        const data = marketData[symbol];
        let card = document.getElementById(`card-${symbol}`);

        if (!card) {
            card = document.createElement('div');
            card.id = `card-${symbol}`;
            card.className = "card";
            card.onclick = () => openWorkspace(symbol);
            grid.appendChild(card);
        }

        // Update Inner HTML
        card.innerHTML = `
            <div class="card-header">
                <span class="symbol-name">${symbol}</span>
                <span class="bias-tag bias-${data.bias}" onmouseenter="showTooltip(event, 'Bias: Xu hướng (EMA Trend)')" onmouseleave="hideTooltip()">${data.bias}</span>
            </div>
            <div class="price-display">${data.close.toFixed(2)}</div>
            <div class="indicators">
                <span class="indicator-item" onmouseenter="showTooltip(event, 'RSI: >70 (Bán) / <30 (Mua)')" onmouseleave="hideTooltip()">RSI: ${data.rsi ? data.rsi.toFixed(1) : '-'}</span>
                <span class="indicator-item" onmouseenter="showTooltip(event, 'ATR: Độ biến động giá')" onmouseleave="hideTooltip()">ATR: ${data.atr ? data.atr.toFixed(2) : '-'}</span>
            </div>
        `;
    });
}

// --- Analytics ---
async function loadAnalytics() {
    try {
        const res = await fetch(`${API_BASE}/history?days=30`);
        const deals = await res.json();

        let totalPnL = 0;
        let wins = 0;
        let count = 0;
        let pnlCurve = [];
        let cumPnL = 0;
        const tableBody = document.getElementById('history-rows');
        tableBody.innerHTML = "";

        const reversed = [...deals].reverse();
        reversed.forEach(d => {
            if (d.profit !== 0) {
                // Simple trade counting logic
                count++;
                totalPnL += d.profit;
                if (d.profit > 0) wins++;
                cumPnL += d.profit;
                pnlCurve.push({ x: new Date(d.time * 1000).toLocaleString(), y: cumPnL });
            }
        });

        // Update Stats
        document.getElementById('stat-pnl').innerText = `$${totalPnL.toFixed(2)}`;
        document.getElementById('stat-pnl').className = totalPnL >= 0 ? 'success-text' : 'danger-text';
        document.getElementById('stat-count').innerText = count;
        document.getElementById('stat-winrate').innerText = count > 0 ? ((wins / count) * 100).toFixed(1) + '%' : "0%";

        // Table
        reversed.slice(0, 50).forEach(d => {
            if (d.profit === 0) return;
            const tr = document.createElement('tr');
            tr.innerHTML = `<td>${new Date(d.time * 1000).toLocaleString()}</td><td>${d.symbol}</td><td>${d.type === 0 ? 'BUY' : d.type === 1 ? 'SELL' : '..'}</td><td>${d.volume}</td><td class="${d.profit >= 0 ? 'success-text' : 'danger-text'}">${d.profit.toFixed(2)}</td>`;
            tableBody.appendChild(tr);
        });

        // Chart
        const ctx = document.getElementById('pnlChart').getContext('2d');
        if (pnlChartInstance) pnlChartInstance.destroy();
        pnlChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: pnlCurve.map(d => d.x),
                datasets: [{ label: 'PnL', data: pnlCurve.map(d => d.y), borderColor: '#10b981', backgroundColor: 'rgba(16,185,129,0.1)', fill: true }]
            },
            options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { x: { display: false }, y: { grid: { color: '#333' } } } }
        });

    } catch (e) { console.error(e); }
}

// --- Trade & AI ---
document.getElementById('execute-btn').addEventListener('click', async () => {
    if (!selectedSymbol) return;
    const btn = document.getElementById('execute-btn');
    btn.disabled = true;

    // Construct Payload
    const payload = {
        symbol: selectedSymbol,
        action: document.getElementById('order-type').value,
        volume: parseFloat(document.getElementById('order-vol').value),
        price: parseFloat(document.getElementById('order-price').value) || 0,
        sl: parseFloat(document.getElementById('order-sl').value) || 0,
        tp: parseFloat(document.getElementById('order-tp').value) || 0
    };

    try {
        const res = await fetch(`${API_BASE}/trade`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if (res.ok && json.status === 'success') {
            alert(`Order Placed: #${json.ticket}`);
            // Keep workspace open to see result? Yes.
        } else {
            alert(`Failed: ${json.message || json.detail}`);
        }
    } catch (e) { alert("Error connecting to server"); }
    btn.disabled = false;
});

document.getElementById('analyze-btn').addEventListener('click', async () => {
    if (!selectedSymbol) return;
    const btn = document.getElementById('analyze-btn');
    const content = document.getElementById('ai-content');
    btn.disabled = true; content.innerText = "Analyzing...";

    try {
        const res = await fetch(`${API_BASE}/analyze/${selectedSymbol}`, { method: 'POST' });
        const result = await res.json();

        if (result.advice === "WAIT" || result.advice === "ERROR") {
            content.innerText = `Advisor: ${result.reason}`;
        } else {
            content.innerHTML = `<span style="color:var(--primary)">${result.action} (${result.confidence})</span><br>Entry: ${result.entry || 'Market'} | SL: ${result.sl} | TP: ${result.tp}<br><span style="font-size:0.8em; color:#ccc">${result.reason}</span>`;
            if (result.confidence !== 'LOW') {
                if (['BUY', 'SELL'].includes(result.action)) document.getElementById('order-type').value = result.action;
                if (result.sl) document.getElementById('order-sl').value = result.sl;
                if (result.tp) document.getElementById('order-tp').value = result.tp;
            }
        }
    } catch (e) { content.innerText = "Error contacting AI."; }
    btn.disabled = false;
});

// --- Symbol Search ---
let searchTimeout = null;
const searchInput = document.getElementById('new-symbol-input');
const searchDropdown = document.getElementById('symbol-dropdown');

searchInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    if (searchTimeout) clearTimeout(searchTimeout);
    if (val.length < 1) { searchDropdown.classList.add('hidden'); return; }

    searchTimeout = setTimeout(async () => {
        try {
            const res = await fetch(`${API_BASE}/search_symbols?q=${val}`);
            const results = await res.json();
            searchDropdown.innerHTML = '';
            if (results.length > 0) {
                results.forEach(sym => {
                    const d = document.createElement('div'); d.className = 'symbol-option'; d.innerText = sym;
                    d.onclick = () => addSymbol(sym);
                    searchDropdown.appendChild(d);
                });
                searchDropdown.classList.remove('hidden');
            } else { searchDropdown.classList.add('hidden'); }
        } catch (e) { }
    }, 300);
});

async function addSymbol(sym) {
    searchInput.value = sym; searchDropdown.classList.add('hidden');
    await fetch(`${API_BASE}/symbols?symbol=${sym}`, { method: 'POST' });
}

// --- Utils ---
const tooltip = document.getElementById('tooltip');
window.showTooltip = (e, text) => {
    tooltip.innerText = text; tooltip.style.left = (e.pageX + 10) + 'px'; tooltip.style.top = (e.pageY + 10) + 'px'; tooltip.classList.remove('hidden');
};
window.hideTooltip = () => { tooltip.classList.add('hidden'); };

setInterval(() => { document.getElementById('clock-local').innerText = new Date().toLocaleTimeString(); }, 1000);

// Init
initWebSocket();
