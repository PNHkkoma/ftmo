
const API_BASE = "http://127.0.0.1:8000/api";

let selectedSymbol = null;
let marketData = {};

function formatPrice(price) {
    if (!price) return "0.00";
    return price.toFixed(2); // crypto/fx logic can be complex, sticking to 2-5
}

async function fetchStatus() {
    try {
        const res = await fetch(`${API_BASE}/status`);
        const data = await res.json();
        
        document.getElementById('acc-balance').innerText = `$${data.balance.toLocaleString()}`;
        document.getElementById('acc-equity').innerText = `$${data.equity.toLocaleString()}`;
        
        const badge = document.getElementById('conn-status');
        if (data.connected) {
            badge.innerText = "Connected";
            badge.style.color = "var(--success)";
            badge.style.background = "rgba(16, 185, 129, 0.2)";
        } else {
            badge.innerText = "Disconnected";
            badge.style.color = "var(--danger)";
            badge.style.background = "rgba(239, 68, 68, 0.2)";
        }
    } catch (e) {
        console.error("Status error", e);
    }
}

async function fetchMarketData() {
    try {
        const res = await fetch(`${API_BASE}/market_data`);
        marketData = await res.json();
        renderGrid();
    } catch (e) {
        console.error("Market Data Error", e);
    }
}

function renderGrid() {
    const grid = document.getElementById('ticker-grid');
    grid.innerHTML = ""; // heavy bruteforce, can be optimized if needed

    Object.keys(marketData).forEach(symbol => {
        const data = marketData[symbol];
        const card = document.createElement('div');
        card.className = "card";
        card.onclick = () => openTradePanel(symbol);

        card.innerHTML = `
            <div class="card-header">
                <span class="symbol-name">${symbol}</span>
                <span class="bias-tag bias-${data.bias}">${data.bias}</span>
            </div>
            <div class="price-display">${formatPrice(data.close)}</div>
            <div class="indicators">
                <span>RSI: ${data.rsi ? data.rsi.toFixed(1) : '-'}</span>
                <span>ATR: ${data.atr ? data.atr.toFixed(2) : '-'}</span>
            </div>
        `;
        grid.appendChild(card);
    });
}

function openTradePanel(symbol) {
    selectedSymbol = symbol;
    document.getElementById('trade-panel').classList.remove('hidden');
    document.getElementById('panel-symbol').innerText = symbol;
    document.getElementById('ai-content').innerText = "Click 'Analyze' to get GPT-4o advice.";
    
    // Auto-fill current price
    if (marketData[symbol]) {
        document.getElementById('order-price').value = marketData[symbol].close;
    }
}

function closeTradePanel() {
    document.getElementById('trade-panel').classList.add('hidden');
    selectedSymbol = null;
}

// AI Button
document.getElementById('analyze-btn').addEventListener('click', async () => {
    if (!selectedSymbol) return;
    
    const btn = document.getElementById('analyze-btn');
    const content = document.getElementById('ai-content');
    
    btn.disabled = true;
    btn.innerText = "Analyzing...";
    content.innerText = "Thinking...";
    
    try {
        const res = await fetch(`${API_BASE}/analyze/${selectedSymbol}`, { method: 'POST' });
        const result = await res.json();
        
        // Check for error/wait
        if(result.advice && (result.advice === "WAIT" || result.advice === "ERROR")) {
             content.innerText = `Log: ${result.advice} - ${result.reason}`;
        } else {
            // Pretty print JSON
            content.innerHTML = `
                <strong>Action:</strong> ${result.action} (${result.confidence})<br>
                <strong>Entry:</strong> ${result.entry || 'Market'}<br>
                <strong>SL:</strong> ${result.sl} | <strong>TP:</strong> ${result.tp}<br>
                <em>"${result.reason}"</em>
            `;
            
            // Auto fill form if confident
            if (result.confidence === 'HIGH' || result.confidence === 'MID') {
                if(result.action === 'BUY' || result.action === 'SELL') {
                    document.getElementById('order-type').value = result.action;
                }
                if(result.sl) document.getElementById('order-sl').value = result.sl;
                if(result.tp) document.getElementById('order-tp').value = result.tp;
            }
        }
        
    } catch (e) {
        content.innerText = "Error calling AI.";
    }
    
    btn.disabled = false;
    btn.innerText = "✨ AI Analyze";
});

// Execute Order
document.getElementById('execute-btn').addEventListener('click', async () => {
    if (!selectedSymbol) return;
    
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
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });
        const json = await res.json();
        if(json.status === 'success') {
            alert(`Order Placed! Ticket: ${json.ticket}`);
            closeTradePanel();
        } else {
            alert(`Failed: ${json.message}`);
        }
    } catch (e) {
        alert("Network Error");
    }
});

// Add Symbol
document.getElementById('add-symbol-btn').addEventListener('click', async () => {
    const input = document.getElementById('new-symbol-input');
    const val = input.value.trim().toUpperCase();
    if (!val) return;
    
    try {
        const res = await fetch(`${API_BASE}/symbols?symbol=${val}`, { method: 'POST' });
        if (res.ok) {
            input.value = "";
            fetchMarketData();
        } else {
            alert("Invalid Symbol or MT5 Error");
        }
    } catch(e) {
        console.error(e);
    }
});

// Clock
setInterval(() => {
    document.getElementById('clock').innerText = new Date().toLocaleTimeString();
}, 1000);

// Polling
setInterval(fetchStatus, 3000);
setInterval(fetchMarketData, 2000);

// Init
fetchStatus();
fetchMarketData();
