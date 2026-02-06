
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
        } else if (msg.type === "POSITIONS") {
            updatePositionsUI(msg.data);
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
    if (viewName === 'positions') loadPositions();

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
    renderGrid();
    if (chartDataInterval) clearInterval(chartDataInterval);
    // Optional: cleanup chart to save memory if needed, but keeping it alive for quick re-open
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
                <div style="display:flex; gap:6px; align-items:center;">
                     <button class="action-btn" onclick="openSinglePiP(event, '${symbol}')" title="Chart PiP">
                        <!-- Chart Icon -->
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                             <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                             <line x1="8" y1="12" x2="16" y2="12" />
                             <polyline points="8 16 12 12 16 16" />
                        </svg>
                     </button>
                     <button class="action-btn" onclick="openInfoPiP(event, '${symbol}')" title="Info Card PiP">
                        <!-- Card Icon -->
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                             <rect x="2" y="5" width="20" height="14" rx="2" />
                             <line x1="2" y1="10" x2="22" y2="10" />
                        </svg>
                     </button>
                    <span class="bias-tag bias-${data.bias}" onmouseenter="showTooltip(event, 'Bias: Xu hướng (EMA Trend)')" onmouseleave="hideTooltip()">${data.bias}</span>
                </div>
            </div>
            <div class="price-display">${data.close.toFixed(2)}</div>
            <div class="indicators">
                <span class="indicator-item" onmouseenter="showTooltip(event, 'RSI: >70 (Bán) / <30 (Mua)')" onmouseleave="hideTooltip()">RSI: ${data.rsi ? data.rsi.toFixed(1) : '-'}</span>
                <span class="indicator-item" onmouseenter="showTooltip(event, 'ATR: Độ biến động giá')" onmouseleave="hideTooltip()">ATR: ${data.atr ? data.atr.toFixed(2) : '-'}</span>
            </div>
        `;
    });
}

function openSinglePiP(e, symbol) {
    if (e) e.stopPropagation();
    const pipUrl = `pip_chart.html?symbol=${symbol}&timeframe=M5`;
    const win = window.open(pipUrl, `ChartPiP_${symbol}`, 'width=450,height=300,resizable=yes,scrollbars=no,status=no,toolbar=no');
    if (win) win.focus();
}

function openInfoPiP(e, symbol) {
    if (e) e.stopPropagation();
    const pipUrl = `pip_info.html?symbol=${symbol}`;
    const win = window.open(pipUrl, `InfoPiP_${symbol}`, 'width=260,height=160,resizable=yes,scrollbars=no,status=no,toolbar=no');
    if (win) win.focus();
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

// --- Positions Logic ---
let currentPositions = [];

async function loadPositions() {
    try {
        const res = await fetch(`${API_BASE}/positions`);
        const data = await res.json();
        updatePositionsUI(data);

        // Load order history
        const resH = await fetch(`${API_BASE}/orders/history?days=30`);
        const dataH = await resH.json();
        updateOrdersHistoryUI(dataH);

    } catch (e) {
        console.error("Error loading positions:", e);
    }
}

function updatePositionsUI(data) {
    currentPositions = data;
    // Only render if view is active to save DOM ops
    if (document.getElementById('view-positions').classList.contains('hidden')) return;

    const tbody = document.getElementById('position-rows');
    tbody.innerHTML = '';

    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:#666">No open positions. (Check History below)</td></tr>';
    }

    data.forEach(p => {
        const tr = document.createElement('tr');
        // Determine Type Color/Badge
        const isPending = p.status === 'PENDING';
        const typeColor = isPending ? 'var(--text-muted)' : (p.type.includes('BUY') ? 'var(--success)' : 'var(--danger)');
        const profitClass = p.profit >= 0 ? 'success-text' : 'danger-text';
        const displayProfit = isPending ? '-' : p.profit.toFixed(2);

        tr.innerHTML = `
            <td>${p.ticket}</td>
            <td>${p.symbol}</td>
            <td style="color:${typeColor}">${p.type} <span style="font-size:0.7em; opacity:0.7">${isPending ? '(PENDING)' : ''}</span></td>
            <td>${p.volume}</td>
            <td>${p.price_open}</td>
            <td>${p.sl}</td>
            <td>${p.tp}</td>
            <td class="${profitClass}">${displayProfit}</td>
            <td>
                <button class="action-btn edit-pos" onclick="openModifyModal(${p.ticket}, ${p.sl}, ${p.tp}, '${p.status}')" title="Edit SL/TP">✏️</button>
                <button class="action-btn close-pos" onclick="closePosition(${p.ticket})" title="${isPending ? 'Cancel Order' : 'Close Position'}">✖</button>
            </td>
        `;
        tbody.appendChild(tr);
    });
}

function updateOrdersHistoryUI(data) {
    const tbody = document.getElementById('order-history-rows');
    if (!tbody) return;
    tbody.innerHTML = '';
    if (data.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:#666">No recent order history (24h)</td></tr>';
        return;
    }

    data.forEach(o => {
        const tr = document.createElement('tr');
        let stateColor = '#fff';
        if (o.state === 'FILLED') stateColor = 'var(--success)';
        else if (o.state === 'CANCELED' || o.state === 'REJECTED') stateColor = 'var(--danger)';
        else if (o.state === 'PLACED') stateColor = 'var(--accent)';

        tr.innerHTML = `
            <td>${new Date(o.time * 1000).toLocaleString()}</td>
            <td>${o.ticket}</td>
            <td>${o.symbol}</td>
            <td>${o.type}</td>
            <td>${o.volume}</td>
            <td>${o.price}</td>
            <td style="color:${stateColor}">${o.state}</td>
            <td style="font-size:0.8em; color:#888">${o.comment}</td>
        `;
        tbody.appendChild(tr);
    });
}


async function closePosition(ticket) {
    if (!confirm("Close position #" + ticket + "?")) return;
    try {
        const res = await fetch(`${API_BASE}/positions/close`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket: ticket })
        });
        const json = await res.json();
        if (json.status === 'success') {
            // UI update will happen via WebSocket
        } else {
            alert("Failed:" + json.message || json.detail);
        }
    } catch (e) { alert("Error"); }
}

// --- Modal Logic ---
function openModifyModal(ticket, sl, tp) {
    document.getElementById('mod-ticket').value = ticket;
    document.getElementById('mod-sl').value = sl;
    document.getElementById('mod-tp').value = tp;
    document.getElementById('modify-modal').classList.remove('hidden');
}

function closeModal() {
    document.getElementById('modify-modal').classList.add('hidden');
}

async function submitModify() {
    const ticket = parseInt(document.getElementById('mod-ticket').value);
    const sl = parseFloat(document.getElementById('mod-sl').value) || 0;
    const tp = parseFloat(document.getElementById('mod-tp').value) || 0;

    try {
        const res = await fetch(`${API_BASE}/positions/modify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ticket, sl, tp })
        });
        const json = await res.json();
        if (json.status === 'success') {
            closeModal();
        } else {
            alert("Failed: " + json.message || json.detail);
        }
    } catch (e) { alert("Error"); }
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
    btn.disabled = true; content.innerHTML = "<span class='loader'></span> Analyzing...";

    try {
        const res = await fetch(`${API_BASE}/analyze/${selectedSymbol}`, { method: 'POST' });
        const result = await res.json();
        console.log("AI Result:", result);

        // Handle ERROR or WAIT strictly
        if (result.action === "WAIT" || result.advice === "WAIT" || result.advice === "ERROR") {
            let reasonHtml = `<div style="text-align:left; font-size: 0.9em;">`;

            // Reasons List
            if (result.wait_reasons && Array.isArray(result.wait_reasons)) {
                reasonHtml += `<strong style="color:var(--text-muted)">WAIT REASONS:</strong><ul style="margin:4px 0 8px 16px; color:#fbbf24">`;
                result.wait_reasons.forEach(r => reasonHtml += `<li>${r}</li>`);
                reasonHtml += `</ul>`;
            } else if (result.reason) {
                reasonHtml += `<div style="color:#fbbf24">Reason: ${result.reason}</div>`;
            }

            // Rationale
            if (result.professional_rationale) {
                reasonHtml += `<div style="margin-top:4px; font-style:italic; color:#9ca3af">"${result.professional_rationale}"</div>`;
            }

            reasonHtml += `</div>`;
            content.innerHTML = `<span style="font-size:1.1em; font-weight:bold; color:var(--text-muted)">STANDBY (WAIT)</span>${reasonHtml}`;

        } else {
            // BUY / SELL
            const riskInfo = result.risk_calc ? `<br><span style="font-size:0.8em; color:#EAB308">${result.risk_calc}</span>` : '';
            const rationale = result.professional_rationale ? `<div style="font-size:0.8em; color:#ddd; margin-top:5px; font-style:italic">"${result.professional_rationale}"</div>` : '';

            content.innerHTML = `
                <div style="text-align:left">
                    <span style="font-size:1.2em; font-weight:bold; color:var(--primary)">${result.action}</span> 
                    <span style="font-size:0.8em; background:#333; padding:2px 6px; border-radius:4px">${result.setup_quality || 'A'} Quality</span>
                    <div style="margin: 5px 0;">
                        Entry: <span style="color:white">${result.entry || 'Market'}</span> | 
                        SL: <span style="color:#ef4444">${result.sl}</span> | 
                        TP: <span style="color:#10b981">${result.tp}</span>
                    </div>
                    ${rationale}
                    ${riskInfo}
                </div>`;

            // Auto-fill Form
            let uiAction = result.action.toUpperCase(); // Ensure upper
            if (uiAction.includes('BUY')) uiAction = 'BUY';
            if (uiAction.includes('SELL')) uiAction = 'SELL';

            const typeSelect = document.getElementById('order-type');
            if (typeSelect) typeSelect.value = uiAction;

            if (result.suggested_volume) document.getElementById('order-vol').value = result.suggested_volume;
            if (result.entry) document.getElementById('order-price').value = result.entry;
            if (result.sl) document.getElementById('order-sl').value = result.sl;
            if (result.tp) document.getElementById('order-tp').value = result.tp;
        }
    } catch (e) {
        console.error(e);
        content.innerText = "Error contacting AI Adviser.";
    }
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

// --- Picture-in-Picture ---
window.openPiP = () => {
    if (!selectedSymbol) {
        alert('Please select a symbol first');
        return;
    }

    const pipUrl = `pip_chart.html?symbol=${selectedSymbol}&timeframe=${activeTimeframe}`;
    const pipWindow = window.open(
        pipUrl,
        'ChartPiP',
        'width=400,height=300,resizable=yes,scrollbars=no,status=no,location=no,toolbar=no,menubar=no'
    );

    if (pipWindow) {
        pipWindow.focus();
    } else {
        alert('Please allow pop-ups for this site to use Picture-in-Picture mode');
    }
};

// --- Utils ---
const tooltip = document.getElementById('tooltip');
window.showTooltip = (e, text) => {
    tooltip.innerText = text; tooltip.style.left = (e.pageX + 10) + 'px'; tooltip.style.top = (e.pageY + 10) + 'px'; tooltip.classList.remove('hidden');
};
window.hideTooltip = () => { tooltip.classList.add('hidden'); };

setInterval(() => { document.getElementById('clock-local').innerText = new Date().toLocaleTimeString(); }, 1000);

// Init
initWebSocket();
