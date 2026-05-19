(function() {
    const currentScript = document.currentScript;
    if (!currentScript) return;

    const controlHTML = `
    <div class="controls-container flex flex-wrap items-center gap-4 p-4 bg-brand-dark-blue border border-brand-border rounded-xl shadow-lg">
        <!-- Market -->
        <div class="control-item flex items-center space-x-2">
            <label class="text-gray-500 font-bold uppercase text-[10px]">Market:</label>
            <select id="market" class="bg-brand-dark border border-brand-border text-white rounded px-3 py-1.5 text-xs shadow-inner">
                <option value="spot">Spot</option>
                <option value="futures">Futures</option>
            </select>
        </div>

        <!-- Timeframe -->
        <div class="control-item flex items-center space-x-2">
            <label class="text-gray-500 font-bold uppercase text-[10px]">Time:</label>
            <select id="interval" class="bg-brand-dark border border-brand-border text-white rounded px-3 py-1.5 text-xs shadow-inner">
                <option value="1s">1s</option>
                <option value="1m" selected>1m</option>
                <option value="3m">3m</option>
                <option value="5m">5m</option>
                <option value="15m">15m</option>
                <option value="30m">30m</option>
                <option value="1h">1h</option>
                <option value="2h">2h</option>
                <option value="4h">4h</option>
                <option value="6h">6h</option>
                <option value="8h">8h</option>
                <option value="12h">12h</option>
                <option value="1d">1d</option>
                <option value="3d">3d</option>
                <option value="1w">1w</option>
                <option value="1M">1M</option>
            </select>
        </div>

        <!-- Ticker -->
        <div id="pair-container" class="control-item flex items-center space-x-2">
            <label class="text-gray-500 font-bold uppercase text-[10px]">Pair:</label>
            <input type="text" id="coin" value="BTCUSDT" list="coin-list" placeholder="Search..." class="bg-brand-dark border border-brand-border text-white rounded px-3 py-1.5 w-32 uppercase font-bold text-xs shadow-inner transition-colors" />
            <datalist id="coin-list"></datalist>
        </div>

        <!-- RSI Input -->
        <div id="rsi-control" class="control-item flex items-center space-x-2">
            <label class="text-gray-500 font-bold uppercase text-[10px]">RSI Len:</label>
            <input type="number" id="rsi-period" value="14" min="1" max="100" class="bg-brand-dark border border-brand-border text-white rounded px-3 py-1.5 w-16 text-xs shadow-inner transition-colors" />
        </div>

        <!-- Amount -->
        <div class="control-item flex items-center space-x-2">
            <label class="text-gray-500 font-bold uppercase text-[10px]">Amount:</label>
            <input type="number" id="amount" value="100" class="bg-brand-dark border border-brand-border text-white rounded px-3 py-1.5 w-24 text-xs shadow-inner" />
        </div>

        <!-- Leverage -->
        <div class="control-item flex items-center space-x-2">
            <label class="text-gray-500 font-bold uppercase text-[10px]">Leverage:</label>
            <input type="number" id="leverage" value="10" min="1" max="125" class="bg-brand-dark border border-brand-border text-white rounded px-3 py-1.5 w-16 text-xs shadow-inner" />
        </div>

        <!-- Date Range -->
        <div class="control-item flex items-center space-x-2">
            <label class="text-gray-500 font-bold uppercase text-[10px]">Range:</label>
            <select id="range-select" class="bg-brand-dark border border-brand-border text-white rounded px-3 py-1.5 text-xs shadow-inner">
                <option value="1">1 Month</option>
                <option value="3">3 Months</option>
                <option value="6">6 Months</option>
                <option value="12" selected>1 Year</option>
                <option value="all">All</option>
            </select>
        </div>
    </div>
    `;

    currentScript.insertAdjacentHTML('beforebegin', controlHTML);

    // Logic from ticker.js to populate symbols
    async function fetchAndPopulateSymbols() {
        const marketEl = document.getElementById("market");
        const coinList = document.getElementById('coin-list');
        
        if (coinList) coinList.innerHTML = '';

        const market = marketEl ? marketEl.value : 'spot';
        
        const url = market === 'futures' 
            ? 'https://fapi.binance.com/fapi/v1/exchangeInfo' 
            : 'https://api.binance.com/api/v3/exchangeInfo';
        
        try {
            const response = await fetch(url);
            const data = await response.json();
            if (!document.getElementById('coin-list')) return;

            const symbols = data.symbols || [];
            let usdtSymbols = [];

            if (market === 'futures') {
                usdtSymbols = symbols.filter(s => s.quoteAsset === 'USDT' && s.status === 'TRADING' && s.contractType === 'PERPETUAL').map(s => s.symbol);
            } else {
                usdtSymbols = symbols.filter(s => s.quoteAsset === 'USDT' && s.status === 'TRADING' && !s.symbol.endsWith('UP') && !s.symbol.endsWith('DOWN') && !s.symbol.endsWith('BEAR') && !s.symbol.endsWith('BULL')).map(s => s.symbol);
            }

            usdtSymbols.sort().forEach(symbol => {
                const option = document.createElement('option');
                option.value = symbol;
                coinList.appendChild(option);
            });
        } catch (error) {
            console.error("Failed to fetch symbol list:", error);
        }
    }

    // Run logic after DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        const marketEl = document.getElementById("market");
        if (marketEl) {
            marketEl.addEventListener('change', fetchAndPopulateSymbols);
        }
        fetchAndPopulateSymbols();

        // Logic from amount.js & laverage.js
        const amountInput = document.getElementById('amount');
        if(amountInput) {
            amountInput.addEventListener('change', () => {
                if (parseInt(amountInput.value) < 1) amountInput.value = 1;
            });
        }

        const leverageInput = document.getElementById('leverage');
        if(leverageInput) {
            leverageInput.addEventListener('change', () => {
                let val = parseInt(leverageInput.value);
                if (val < 1) leverageInput.value = 1;
                if (val > 125) leverageInput.value = 125;
            });
            leverageInput.addEventListener('input', () => {
                if (parseInt(leverageInput.value) > 125) leverageInput.value = 125;
            });
        }
    });
})();