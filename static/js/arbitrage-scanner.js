let lastArbData = []; 
let arbSearchQuery = ''; 
let minVolFilter = 0; 

// Хайлт болон Шүүлтүүр
function updateArbSearch(val) {
    arbSearchQuery = val.trim().toUpperCase();
    renderArbTable();
}

function updateMinVolFilter(val) {
    minVolFilter = parseFloat(val);
    renderArbTable();
}

// Үндсэн дата татах функц
async function fetchArbitrageData() {
    const tableBody = document.getElementById('arbitrage-table-body');
    if (!tableBody) return;

    try {
        const response = await fetch('/api/arbitrage');
        const result = await response.json();
        
        if (!result || result.error) return;

        // Серверээс ирсэн бэлэн opportunities-ийг хадгалах
        lastArbData = result.data || [];
        renderArbTable();

    } catch (error) {
        console.error("Critical Connection Error:", error);
    }
}

function renderArbTable() {
    const tableBody = document.getElementById('arbitrage-table-body');
    if (!tableBody) return;

    let filteredData = [...lastArbData];

    // 1. Волюмоор шүүх (Хамгийн багадаа аль нэг бирж дээрх USDT volume)
    if (minVolFilter > 0) {
        filteredData = filteredData.filter(item => {
            const volumes = [item.b?.q, item.m?.q, item.by?.q, item.k?.q].filter(v => v !== undefined);
            return volumes.some(v => v >= minVolFilter);
        });
    }

    // 2. Түлхүүр үгээр хайх
    if (arbSearchQuery) {
        filteredData = filteredData.filter(item => item.symbol.includes(arbSearchQuery));
    }

    if (filteredData.length === 0) {
        tableBody.innerHTML = `<tr><td colspan="7" class="p-8 text-center text-gray-500 italic uppercase text-[10px] font-black">No opportunities found with current filters.</td></tr>`;
        return;
    }

    // Хүснэгтийн мөрүүдийг зурах
    tableBody.innerHTML = filteredData.slice(0, 100).map(item => 
        createArbRowHTML(item.symbol, item.b, item.m, item.by, item.k, item.diff)
    ).join('');
}

// Форматлагч функцүүд (ХАСАГДАХГҮЙ)
window.formatArbPrice = function(price) {
    if (!price || isNaN(price) || price === 0) return '---';
    if (price >= 100) return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    if (price >= 1) return price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 4 });
    return price.toFixed(8);
}

window.formatVol = function(val) {
    if (!val || isNaN(val) || val == 0) return '0';
    if (val >= 1000000) return (val / 1000000).toFixed(1) + 'M';
    if (val >= 1000) return (val / 1000).toFixed(0) + 'K';
    return parseFloat(val).toFixed(0);
}

// ҮНДСЭН ROW РЕНДЕР - ЧИНИЙ БҮХ ЛОГИК ЭНД БАЙНА
function createArbRowHTML(symbol, b, m, by, k, diff) {
    const exchs = [
        { name: 'Binance', data: b, url: `https://www.binance.com/en/trade/${symbol.replace('USDT','_USDT')}` },
        { name: 'MEXC', data: m, url: `https://www.mexc.com/exchange/${symbol.replace('USDT','_USDT')}` },
        { name: 'Bybit', data: by, url: `https://www.bybit.com/en/trade/spot/${symbol.replace('USDT','')}/USDT` },
        { name: 'KuCoin', data: k, url: `https://www.kucoin.com/trade/${symbol.replace('USDT','-USDT')}` }
    ];

    // Хамгийн хямд Ask болон Хамгийн өндөр Bid-ийг олох (Чиний анхны логик)
    const validAsks = exchs.filter(x => x.data && x.data.ap > 0).map(x => x.data.ap);
    const validBids = exchs.filter(x => x.data && x.data.bp > 0).map(x => x.data.bp);
    const minAsk = validAsks.length ? Math.min(...validAsks) : 0;
    const maxBid = validBids.length ? Math.max(...validBids) : 0;

    const badgeClass = diff > 0.5 ? "bg-green-500 text-black animate-pulse" : "bg-gray-800 text-gray-500";

    const renderCell = (exch) => {
        if (!exch.data || !exch.data.p) return `<td class="p-4 font-mono text-[11px] text-gray-700 italic opacity-40">---</td>`;
        return `
            <td class="p-4 font-mono text-[11px]">
                <div class="flex flex-col">
                    <a href="${exch.url}" target="_blank" class="hover:underline transition-all mb-1 font-bold ${exch.data.ap === minAsk ? 'text-green-400' : exch.data.bp === maxBid ? 'text-red-400' : 'text-gray-400'}">
                        $${formatArbPrice(exch.data.p)}
                    </a>
                    <div class="text-[8px] leading-tight text-gray-500 font-bold">
                        <span class="text-brand-gold/80 italic">24h Vol:</span> ${formatVol(exch.data.v)}<br>
                        <span class="text-brand-gold/80 italic">USDT:</span> ${formatVol(exch.data.q)}
                    </div>
                </div>
            </td>
        `;
    };

    const buyExch = exchs.find(x => x.data && x.data.ap === minAsk)?.name || '---';
    const sellExch = exchs.find(x => x.data && x.data.bp === maxBid)?.name || '---';

    return `
        <tr class="border-b border-brand-border hover:bg-white/5 transition-colors">
            <td class="p-4 font-black text-white italic text-xs border-r border-brand-border/30 cursor-pointer hover:text-brand-gold" onclick="showCoinDetail('${symbol}')">${symbol}</td>
            ${renderCell(exchs[0])}
            ${renderCell(exchs[1])}
            ${renderCell(exchs[2])}
            ${renderCell(exchs[3])}
            <td class="p-4 border-l border-brand-border/30">
                <div class="flex flex-col gap-1 items-center">
                    <span class="px-2 py-0.5 rounded text-[10px] font-black ${badgeClass} text-center min-w-[50px]">
                        ${parseFloat(diff).toFixed(3)}%
                    </span>
                </div>
            </td>
            <td class="p-4 text-right">
                <div class="flex flex-col items-end gap-1">
                    <span class="text-[8px] text-green-400 font-black uppercase tracking-tighter">Buy: ${buyExch}</span>
                    <span class="text-[8px] text-red-500 font-black uppercase tracking-tighter">Sell: ${sellExch}</span>
                    <a href="https://www.google.com/search?q=${symbol}+wallet+status+on+${buyExch}+${sellExch}" 
                       target="_blank" class="text-[7px] text-gray-600 hover:text-brand-gold uppercase tracking-tighter mt-1">
                       <i class="fas fa-wallet mr-1"></i> Check Wallet
                    </a>
                </div>
            </td>
        </tr>
    `;
}

// Автоматаар шинэчлэх
setInterval(fetchArbitrageData, 10000);
fetchArbitrageData();