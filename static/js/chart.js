(function() {
    const currentScript = document.currentScript;
    if (!currentScript) return;

    const chartHTML = `
    <div id="chart-wrapper" class="relative w-full h-[600px] bg-[#05070a] border-y border-brand-border overflow-hidden">
        <canvas id="chart" class="block w-full h-full cursor-crosshair"></canvas>
    </div>
    `;
    currentScript.insertAdjacentHTML('beforebegin', chartHTML);
})();

document.addEventListener('DOMContentLoaded', () => {
    const canvas = document.getElementById("chart");
    if (!canvas) return;
    
    const ctx = canvas.getContext("2d");
    let socket;
    
    // DOM Elements form Controls
    const marketEl = document.getElementById("market");
    const intervalEl = document.getElementById("interval");
    const coinEl = document.getElementById("coin");
    const rangeEl = document.getElementById("range-select");
    const rsiEl = document.getElementById("rsi-period");
    const amountEl = document.getElementById("amount");
    const leverageEl = document.getElementById("leverage");

    // State
    let symbol = coinEl && coinEl.value ? coinEl.value.toUpperCase() : "BTCUSDT";
    let interval = intervalEl ? intervalEl.value : "1m";
    let allData = [];
    let visibleCount = 80;
    let offset = 0; // pan offset
    const minVisible = 20;
    const maxVisible = 200;
    let mouse = { x:null, y:null };
    let dragging = false;
    let lastX = 0;
    
    // Price Scale State
    let priceScale = 1;
    let priceOffset = 0;
    let draggingPrice = false;
    let lastY = 0;
    let lastPriceRange = 0;
    let lastChartHeight = 0;

    function resize() {
        if (canvas.parentElement) {
            canvas.width = canvas.parentElement.clientWidth;
            canvas.height = canvas.parentElement.clientHeight;
        } else {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
        }
        draw();
    }
    
    window.addEventListener("resize", resize);
    // Initial resize after a short delay to ensure container is rendered
    setTimeout(resize, 100);

    function formatPrice(price) {
        if (price >= 100) return price.toFixed(2);
        if (price >= 1) return price.toFixed(4);
        if (price >= 0.001) return price.toFixed(6);
        return price.toPrecision(4);
    }

    async function fetchCandles() {
        if (!marketEl || !coinEl) return;

        // Ensure symbol is valid
        if (!symbol) symbol = "BTCUSDT";
        
        let url;
        if (marketEl.value === "futures") {
            url = `https://fapi.binance.com/fapi/v1/klines?symbol=${symbol}&interval=${interval}&limit=500`;
        } else {
            url = `https://api.binance.com/api/v3/klines?symbol=${symbol}&interval=${interval}&limit=500`;
        }

        try {
            const res = await fetch(url);
            allData = await res.json();
            draw();
            dispatchChartUpdate();
            startWebSocket();
        } catch (e) {
            console.error("Error fetching candles:", e);
        }
    }

    function draw() {
        if (!allData || !allData.length) return;
        
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        const padding = 40;
        const priceScaleWidth = 80;
        const timeScaleHeight = 30;
        const chartHeight = canvas.height - padding * 2 - timeScaleHeight;
        lastChartHeight = chartHeight;
        const chartWidth = canvas.width - padding * 2 - priceScaleWidth;

        const end = allData.length - offset;
        const start = Math.max(0, end - visibleCount);
        const data = allData.slice(start, end);
        if (!data.length) return;

        const prices = data.flatMap(d => [+d[2], +d[3]]);
        let maxPrice = Math.max(...prices);
        let minPrice = Math.min(...prices);

        if (maxPrice === minPrice) {
            const pricePadding = maxPrice > 1 ? maxPrice * 0.001 : 0.001;
            maxPrice += pricePadding;
            minPrice -= pricePadding;
        }
        if (maxPrice === minPrice) maxPrice += 1;

        // Apply Price Scaling (Zoom Y)
        if (priceScale !== 1) {
            const mid = (maxPrice + minPrice) / 2;
            const halfRange = (maxPrice - minPrice) / 2;
            const scaledHalf = halfRange * priceScale;
            maxPrice = mid + scaledHalf;
            minPrice = mid - scaledHalf;
        }

        lastPriceRange = maxPrice - minPrice;

        // Apply Price Offset (Pan Y)
        maxPrice += priceOffset;
        minPrice += priceOffset;

        const priceToY = p => padding + (maxPrice - p) / (maxPrice - minPrice) * chartHeight;
        const yToPrice = y => maxPrice - ((y - padding) / chartHeight) * (maxPrice - minPrice);
        const candleWidth = chartWidth / data.length;

        // Price grid
        ctx.font = "12px Arial";
        ctx.strokeStyle = "#1f2630";
        ctx.fillStyle = "#aaa";

        for (let i = 0; i <= 6; i++) {
            const price = minPrice + (i / 6) * (maxPrice - minPrice);
            const y = priceToY(price);
            ctx.beginPath(); ctx.moveTo(padding, y); ctx.lineTo(padding + chartWidth, y); ctx.stroke();
            ctx.fillText(formatPrice(price), padding + chartWidth + 5, y + 4);
        }
        
        // Time grid
        const numTicks = Math.max(2, Math.floor(chartWidth / 100));
        const step = Math.ceil(data.length / numTicks);
        ctx.textAlign = "center";

        for (let i = 0; i < data.length; i += step) {
            const x = padding + i * candleWidth + candleWidth / 2;
            const ts = data[i][0];
            const date = new Date(ts);
            
            let label;
            if (interval.endsWith('d') || interval.endsWith('w') || interval.endsWith('M')) {
                label = date.toLocaleDateString(undefined, { year: 'numeric', month: 'numeric', day: 'numeric' });
            } else {
                label = date.getHours().toString().padStart(2, '0') + ':' + date.getMinutes().toString().padStart(2, '0');
            }

            ctx.strokeStyle = "#1f2630";
            ctx.beginPath(); ctx.moveTo(x, padding); ctx.lineTo(x, padding + chartHeight); ctx.stroke();
            
            ctx.fillStyle = "#aaa";
            ctx.fillText(label, x, padding + chartHeight + 20);
        }
        ctx.textAlign = "left";

        // Candles
        data.forEach((d, i) => {
            const open = +d[1], high = +d[2], low = +d[3], close = +d[4];
            const x = padding + i * candleWidth;
            const yO = priceToY(open);
            const yC = priceToY(close);
            const yH = priceToY(high);
            const yL = priceToY(low);
            const bull = close >= open;

            const grd = ctx.createLinearGradient(x, yH, x, yL);
            if (bull) {
                grd.addColorStop(0, "#3ee69b");
                grd.addColorStop(1, "#0ecb81");
            } else {
                grd.addColorStop(0, "#ffffff");
                grd.addColorStop(1, "#ffffff");
            }

            ctx.fillStyle = grd;
            ctx.strokeStyle = bull ? "#0ecb81" : "#ffffff";
            ctx.shadowColor = bull ? "#0ecb81" : "#ffffff";
            ctx.shadowBlur = 1;
            
            ctx.beginPath(); ctx.moveTo(x + candleWidth / 2, yH); ctx.lineTo(x + candleWidth / 2, yL); ctx.stroke();
            ctx.fillRect(x + candleWidth * 0.2, Math.min(yO, yC), candleWidth * 0.6, Math.max(1, Math.abs(yO - yC)));
            
            ctx.shadowBlur = 0;
        });

        // Current price line
        const lastClose = +data[data.length - 1][4];
        const yLast = priceToY(lastClose);
        ctx.setLineDash([5, 5]);
        ctx.strokeStyle = "#f0b90b";
        ctx.beginPath();
        ctx.moveTo(padding, yLast);
        ctx.lineTo(padding + chartWidth, yLast);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = "#f0b90b";
        ctx.fillText(formatPrice(lastClose), padding + chartWidth + 5, yLast - 4);

        // Crosshair
        if (mouse.x && mouse.y && mouse.x > padding && mouse.x < padding + chartWidth && mouse.y > padding && mouse.y < padding + chartHeight) {
            const index = Math.floor((mouse.x - padding) / candleWidth);
            const candle = data[index];
            if (candle) {
                const candleX = padding + index * candleWidth + candleWidth / 2;
                ctx.strokeStyle = "#888";
                ctx.beginPath(); ctx.moveTo(candleX, padding); ctx.lineTo(candleX, padding + chartHeight); ctx.stroke();
                ctx.beginPath(); ctx.moveTo(padding, mouse.y); ctx.lineTo(padding + chartWidth, mouse.y); ctx.stroke();

                const price = yToPrice(mouse.y);
                ctx.fillStyle = "#111"; ctx.fillRect(padding + chartWidth, mouse.y - 10, priceScaleWidth, 20);
                ctx.fillStyle = "#fff"; ctx.fillText(formatPrice(price), padding + chartWidth + 5, mouse.y + 4);
            }
        }
    }

    const triggerAutoUpdate = () => {
        if (!coinEl || !intervalEl) return;
        interval = intervalEl.value;
        symbol = coinEl.value.toUpperCase();
        if (socket) { socket.onclose = null; socket.close(); }
        fetchCandles();
    };

    // Бүх удирдлагын элементүүд дээр өөрчлөлт сонсогч нэмэх
    if (marketEl) marketEl.addEventListener("change", triggerAutoUpdate);
    if (intervalEl) intervalEl.addEventListener("change", triggerAutoUpdate);
    if (rangeEl) rangeEl.addEventListener("change", triggerAutoUpdate);
    if (rsiEl) rsiEl.addEventListener("change", triggerAutoUpdate);
    if (amountEl) amountEl.addEventListener("change", triggerAutoUpdate);
    if (leverageEl) leverageEl.addEventListener("change", triggerAutoUpdate);
    if (coinEl) {
        coinEl.addEventListener("change", triggerAutoUpdate);
        coinEl.addEventListener("keydown", (e) => { if (e.key === "Enter") triggerAutoUpdate(); });
    }

    canvas.addEventListener("mousemove", e => {
        const rect = canvas.getBoundingClientRect();
        mouse.x = e.clientX - rect.left;
        mouse.y = e.clientY - rect.top;
        
        // Handle Price Scale Dragging
        if (draggingPrice) {
            const dy = e.clientY - lastY;
            lastY = e.clientY;
            // Drag down (+) -> Zoom out (increase range) -> scale increases
            // Drag up (-) -> Zoom in (decrease range) -> scale decreases
            priceScale *= (1 + dy * 0.005);
            priceScale = Math.max(0.1, Math.min(priceScale, 10)); // Limits
            draw();
            return;
        }

        if (dragging) {
            const dx = e.clientX - lastX;
            const move = Math.round(dx / 10);
            offset = Math.max(0, Math.min(allData.length - visibleCount, offset + move));
            lastX = e.clientX;
            
            // Y Pan (Vertical Drag)
            const dy = e.clientY - lastY;
            if (lastChartHeight > 0) {
                const pricePerPixel = lastPriceRange / lastChartHeight;
                priceOffset += dy * pricePerPixel;
            }
            lastY = e.clientY;
        }
        
        // Change cursor if hovering over price scale
        const padding = 40;
        const priceScaleWidth = 80;
        if (mouse.x > canvas.width - padding - priceScaleWidth) {
            canvas.style.cursor = "ns-resize";
        } else if (dragging) {
            canvas.style.cursor = "grabbing";
        } else {
            canvas.style.cursor = "crosshair";
        }
        
        draw();
    });

    canvas.addEventListener("mousedown", e => { 
        const padding = 40;
        const priceScaleWidth = 80;
        const scaleStartX = canvas.width - padding - priceScaleWidth;
        
        if (mouse.x > scaleStartX) {
            draggingPrice = true;
            lastY = e.clientY;
        } else {
            dragging = true; 
            lastX = e.clientX; 
            lastY = e.clientY;
        }
    });
    
    canvas.addEventListener("mouseup", () => { 
        dragging = false; 
        draggingPrice = false; 
    });
    
    canvas.addEventListener("mouseleave", () => { 
        dragging = false; 
        draggingPrice = false;
        mouse.x = null; 
        draw(); 
    });

    // Double click to reset price scale
    canvas.addEventListener("dblclick", () => {
        priceScale = 1;
        priceOffset = 0;
        draw();
    });
    
    canvas.addEventListener("wheel", e => {
        e.preventDefault();
        visibleCount += e.deltaY > 0 ? 10 : -10;
        visibleCount = Math.max(minVisible, Math.min(maxVisible, visibleCount));
        offset = Math.min(offset, allData.length - visibleCount);
        draw();
    }, { passive:false });

    function startWebSocket() {
        const wsMarket = marketEl.value === "futures" ? "fstream" : "stream";
        const wsUrl = `wss://${wsMarket}.binance.com/ws/${symbol.toLowerCase()}@kline_${interval}`;
        socket = new WebSocket(wsUrl);
        socket.onmessage = e => { 
            const msg = JSON.parse(e.data); 
            if(msg.k) { 
                const c = [msg.k.t, msg.k.o, msg.k.h, msg.k.l, msg.k.c, msg.k.v]; 
                const last = allData[allData.length-1]; 
                if(last && last[0]===c[0]) allData[allData.length-1]=c; 
                else { allData.push(c); if(allData.length>500) allData.shift(); } 
                draw();
                dispatchChartUpdate();
            } 
        };
    }

    // Initial Load
    fetchCandles();
});