window.arbInterval = window.arbInterval || null;
window.detailInterval = window.detailInterval || null;

function showTool(toolId) {
    const contentArea = document.getElementById('content-area');
    const toolTitle = document.getElementById('tool-title');
    
    // Сонгогдсон линкийг идэвхжүүлэх
    document.querySelectorAll('.sidebar-item').forEach(el => el.classList.remove('active-link'));
    const activeLink = document.getElementById(`link-${toolId}`);
    if (activeLink) activeLink.classList.add('active-link');

    // Хуучин интервалыг цэвэрлэх
    if (window.arbInterval) clearInterval(window.arbInterval);
    if (window.detailInterval) clearInterval(window.detailInterval);

    if (toolId === 'arbitrage') {
        toolTitle.innerHTML = 'Arbitrage <span class="text-brand-gold">Scanner</span>';
        contentArea.innerHTML = `
            <!-- Search Section -->
            <div class="mb-4 glass-card p-4 rounded-xl border border-brand-border flex flex-col md:flex-row md:items-center justify-between gap-4">
                <div class="relative w-full max-w-md">
                    <i class="fas fa-search absolute left-3 top-1/2 -translate-y-1/2 text-gray-500 text-xs"></i>
                    <input type="text" id="arb-search" oninput="updateArbSearch(this.value)" placeholder="Search Asset (e.g. BTC)..." 
                        class="w-full bg-brand-dark border border-brand-border text-white text-xs rounded-lg pl-9 pr-4 py-2 focus:border-brand-gold outline-none transition-all uppercase font-bold tracking-wider">
                </div>
                <div class="flex items-center gap-2">
                    <label class="text-[9px] text-gray-500 font-black uppercase tracking-wider">Min Vol:</label>
                    <select onchange="updateMinVolFilter(this.value)" class="bg-brand-dark border border-brand-border text-white text-[10px] rounded-lg px-2 py-1.5 focus:border-brand-gold outline-none font-bold">
                        <option value="0">No Limit</option>
                        <option value="5000">$5K+</option>
                        <option value="20000">$20K+</option>
                        <option value="100000">$100K+</option>
                    </select>
                </div>
                <div class="text-[10px] text-gray-500 font-black uppercase tracking-[0.2em] hidden md:block">Real-time Multi-Exchange Spread</div>
            </div>

            <div class="glass-card rounded-2xl overflow-hidden shadow-2xl">
                <table class="w-full text-left">
                    <thead class="bg-black/40 text-[10px] font-black uppercase tracking-widest text-gray-500 border-b border-brand-border">
                        <tr>
                            <th class="p-4">Asset (USDT)</th>
                            <th class="p-4">Binance</th>
                            <th class="p-4">MEXC</th>
                            <th class="p-4">Bybit</th>
                            <th class="p-4">KuCoin</th>
                            <th class="p-4">Spread</th>
                            <th class="p-4 text-right">Action</th>
                        </tr>
                    </thead>
                    <tbody id="arbitrage-table-body" class="text-xs">
                        <tr>
                            <td colspan="7" class="p-4 text-center text-gray-500 italic">
                                <i class="fas fa-spinner fa-spin mr-2"></i> Loading arbitrage data... Please wait.
                            </td>
                        </tr>
                        <!-- Data loaded via JS -->
                    </tbody>
                </table>
            </div>
        `;
        fetchArbitrageData();
        if (window.arbInterval) clearInterval(window.arbInterval);
        window.arbInterval = setInterval(fetchArbitrageData, 15000);
    }
}

// Шинэ: Койны нарийвчилсан мэдээллийг харуулах
function showCoinDetail(symbol) {
    const contentArea = document.getElementById('content-area');
    const toolTitle = document.getElementById('tool-title');
    
    toolTitle.innerHTML = `${symbol} <span class="text-brand-gold italic text-sm tracking-widest ml-2">Market Intelligence</span>`;
    
    // Сканнерын интервалыг зогсоох (дата ачаалал багасгах)
    if (window.arbInterval) clearInterval(window.arbInterval);
    if (window.detailInterval) clearInterval(window.detailInterval);

    // 5 секунд тутамд датаг шинээр татаж, хүснэгтийг дахин зурах
    window.detailInterval = setInterval(async () => {
        await fetchArbitrageData();
        renderDetailTable(symbol);
    }, 15000);

    // Одоо байгаа датаг олох
    const coinData = lastArbData.find(item => item.symbol === symbol);

    contentArea.innerHTML = `
        <div class="flex flex-col gap-6 animate-in fade-in duration-500">
            <div class="flex items-center gap-4">
                <button onclick="showTool('arbitrage')" class="bg-brand-border hover:bg-brand-gold hover:text-black text-gray-400 text-[10px] font-black py-2 px-4 rounded-lg transition-all uppercase tracking-widest">
                    <i class="fas fa-arrow-left mr-2"></i> Back to Scanner
                </a>
            </div>

            <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
                <!-- Left: Profile & Arbitrage Opportunity -->
                <div class="lg:col-span-1 space-y-6">
                    <div class="glass-card p-6 rounded-2xl border border-brand-border">
                        <h3 class="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-6 border-b border-brand-border pb-2">Opportunity Rank</h3>
                        <div class="flex flex-col items-center py-4">
                            <div class="text-4xl font-black text-brand-gold italic mb-1">${coinData ? coinData.diff.toFixed(2) : '0.00'}%</div>
                            <div class="text-[10px] text-gray-500 font-bold uppercase tracking-widest">Potential Spread</div>
                        </div>
                    </div>

                    <div class="glass-card p-6 rounded-2xl border border-brand-border">
                        <h3 class="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-4 border-b border-brand-border pb-2">Execution Route</h3>
                        <div id="detail-route-container" class="space-y-3">
                            <!-- Route logic can be expanded here -->
                            <p class="text-[11px] text-gray-400 leading-relaxed italic">
                                Сканнерын мэдээллээр энэ койн дээр арилжаа хийхэд хамгийн ашигтай маршрут болон сүлжээний төлвийг шалгана уу.
                            </p>
                        </div>
                    </div>
                </div>

                <!-- Right: Exchange Comparison Table -->
                <div class="lg:col-span-2 glass-card p-6 rounded-2xl border border-brand-border shadow-2xl">
                    <h3 class="text-[10px] font-black text-gray-500 uppercase tracking-widest mb-6 border-b border-brand-border pb-2">Real-time Exchange Comparison</h3>
                    <div class="overflow-x-auto">
                        <table class="w-full text-left">
                            <thead class="text-gray-600 text-[9px] font-black uppercase tracking-tighter border-b border-brand-border">
                                <tr>
                                    <th class="py-3">Exchange</th>
                                    <th class="py-3">Price (USDT)</th>
                                    <th class="py-3">24h Vol</th>
                                    <th class="py-3 text-right">Action</th>
                                </tr>
                            </thead>
                            <tbody id="detail-exchange-body" class="text-xs">
                                <!-- Dynamically filled -->
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    `;

    renderDetailTable(symbol);
}

function renderDetailTable(symbol) {
    const container = document.getElementById('detail-exchange-body');
    if (!container) return;

    const item = lastArbData.find(i => i.symbol === symbol);
    if (!item) return;

    const exchanges = [
        { name: 'Binance', data: item.b, url: `https://www.binance.com/en/trade/${symbol.replace('USDT','_USDT')}` },
        { name: 'MEXC', data: item.m, url: `https://www.mexc.com/exchange/${symbol.replace('USDT','_USDT')}` },
        { name: 'Bybit', data: item.by, url: `https://www.bybit.com/en/trade/spot/${symbol.replace('USDT','')}/USDT` },
        { name: 'KuCoin', data: item.k, url: `https://www.kucoin.com/trade/${symbol.replace('USDT','-USDT')}` }
    ];

    const validExchs = exchanges.filter(ex => ex.data && ex.data.bp > 0 && ex.data.ap > 0);
    const asks = validExchs.map(ex => ex.data.ap);
    const bids = validExchs.map(ex => ex.data.bp);
    
    const minAsk = Math.min(...asks);
    const maxBid = Math.max(...bids);

    // Update Route Container
    const routeContainer = document.getElementById('detail-route-container');
    if (routeContainer) {
        const buyEx = exchanges.find(x => x.data && x.data.ap === minAsk)?.name;
        const sellEx = exchanges.find(x => x.data && x.data.bp === maxBid)?.name;
        routeContainer.innerHTML = `
            <div class="flex flex-col gap-4 p-5 bg-black/40 border border-brand-border rounded-xl shadow-inner">
                <div class="flex items-center justify-between bg-green-500/10 p-3 rounded-lg border border-green-500/20">
                    <span class="text-[10px] font-black text-green-400 uppercase tracking-widest">Buy on:</span>
                    <span class="text-sm font-black text-white italic tracking-tighter">${buyEx} <i class="fab fa-binance ml-1 text-green-400"></i></span>
                </div>
                <div class="flex justify-center py-1">
                    <i class="fas fa-arrow-down text-brand-gold animate-bounce"></i>
                </div>
                <div class="flex items-center justify-between bg-red-500/10 p-3 rounded-lg border border-red-500/20">
                    <span class="text-[10px] font-black text-red-400 uppercase tracking-widest">Sell on:</span>
                    <span class="text-sm font-black text-white italic tracking-tighter">${sellEx} <i class="fas fa-chart-line ml-1 text-red-400"></i></span>
                </div>
            </div>
        `;
    }

    container.innerHTML = exchanges.map(ex => `
        <tr class="border-b border-brand-border/30 last:border-0 hover:bg-white/5 transition animate-in fade-in duration-300 ${ex.data && ex.data.ap === minAsk ? 'bg-green-500/10' : ''} ${ex.data && ex.data.bp === maxBid ? 'bg-red-500/10' : ''}">
            <td class="py-4 font-bold text-gray-300 flex items-center gap-2">
                <span class="w-1.5 h-1.5 rounded-full ${ex.data && ex.data.ap === minAsk ? 'bg-green-400' : ex.data && ex.data.bp === maxBid ? 'bg-red-400' : 'bg-brand-gold'} animate-pulse"></span> 
                ${ex.name}
                ${ex.data && ex.data.ap === minAsk ? '<span class="ml-2 text-[8px] bg-green-500 text-black px-1.5 py-0.5 rounded font-black uppercase">Buy</span>' : ''}
                ${ex.data && ex.data.bp === maxBid ? '<span class="ml-2 text-[8px] bg-red-500 text-white px-1.5 py-0.5 rounded font-black uppercase">Sell</span>' : ''}
            </td>
            <td class="py-4 font-mono font-black tracking-tighter">
                <div class="flex flex-col">
                    <span class="${ex.data && ex.data.ap === minAsk ? 'text-green-400 text-[11px]' : 'text-gray-400 text-[10px]'}">Ask: $${ex.data ? formatArbPrice(ex.data.ap) : '---'}</span>
                    <span class="${ex.data && ex.data.bp === maxBid ? 'text-red-400 text-[11px]' : 'text-gray-500 text-[10px]'}">Bid: $${ex.data ? formatArbPrice(ex.data.bp) : '---'}</span>
                </div>
            </td>
            <td class="py-4 text-[10px] text-gray-400 font-bold">
                <div class="flex flex-col">
                    <span>${ex.data ? formatVol(ex.data.q) : '0'} USDT</span>
                    <span class="text-[8px] text-gray-600">${ex.data ? formatVol(ex.data.v) : '0'} Units</span>
                </div>
            </td>
            <td class="py-4 text-right">
                <a href="${ex.url}" target="_blank" class="text-[9px] font-black text-brand-gold hover:text-white transition uppercase tracking-widest">Trade Now <i class="fas fa-external-link-alt ml-1"></i></a>
            </td>
        </tr>
    `).join('');
}

// Хэрэглэгчийн мэдээллийг харуулах
function updateUserInfo() {
    const userStr = localStorage.getItem('user');
    const userInfo = document.getElementById('user-info');
    if (userStr && userInfo) {
        const user = JSON.parse(userStr);
        userInfo.innerHTML = `
            <div class="flex items-center">
                <span class="w-2 h-2 bg-green-500 rounded-full mr-2"></span>
                ${user.username.toUpperCase()} (${user.membership_type})
            </div>
        `;
    }
}
updateUserInfo();