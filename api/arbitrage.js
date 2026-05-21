export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET, OPTIONS');

    const EXCHANGES = {
        binance: 'https://api.binance.com/api/v3/ticker/24hr',
        mexc: 'https://api.mexc.com/api/v3/ticker/24hr',
        bybit: 'https://api.bybit.com/v5/market/tickers?category=spot',
        kucoin: 'https://api.kucoin.com/api/v1/market/allTickers'
    };

    try {
        // Бүх биржээс датаг зэрэг татах (Parallel fetch)
        const [bRes, mRes, byRes, kRes] = await Promise.all([
            fetch(EXCHANGES.binance).then(r => r.json()).catch(() => []),
            fetch(EXCHANGES.mexc).then(r => r.json()).catch(() => []),
            fetch(EXCHANGES.bybit).then(r => r.json()).catch(() => ({ result: { list: [] } })),
            fetch(EXCHANGES.kucoin).then(r => r.json()).catch(() => ({ data: { ticker: [] } }))
        ]);

        // Форматлах (Чиний frontend-ийн хүлээж авдаг бүтэц)
        const marketData = {
            binance: bRes || [],
            mexc: mRes || [],
            bybit: byRes.result?.list || [],
            kucoin: kRes.data?.ticker || [],
            lastUpdate: new Date()
        };

        // Binance-ийн USDT хослолууд дээр суурилж жагсаалт үүсгэх
        const symbols = marketData.binance
            .filter(t => t.symbol.endsWith('USDT'))
            .map(t => t.symbol);

        const formatted = symbols.map(symbol => {
            const b = marketData.binance.find(t => t.symbol === symbol);
            const m = marketData.mexc.find(t => t.symbol === symbol);
            const by = marketData.bybit.find(t => t.symbol === symbol);
            const k = marketData.kucoin.find(t => t.symbol === symbol.replace('USDT', '-USDT'));

            const prices = [];
            if (b) prices.push(parseFloat(b.lastPrice));
            if (m) prices.push(parseFloat(m.lastPrice));
            if (by) prices.push(parseFloat(by.lastPrice));
            if (k) prices.push(parseFloat(k.last));

            let diff = 0;
            if (prices.length > 1) {
                diff = ((Math.max(...prices) - Math.min(...prices)) / Math.min(...prices)) * 100;
            }

            const createData = (t, type) => {
                if (!t) return null;
                if (type === 'k') return { p: parseFloat(t.last), bp: parseFloat(t.buy), ap: parseFloat(t.sell), v: parseFloat(t.vol), q: parseFloat(t.volValue) };
                if (type === 'by') return { p: parseFloat(t.lastPrice), bp: parseFloat(t.bid1Price), ap: parseFloat(t.ask1Price), v: parseFloat(t.volume24h), q: parseFloat(t.turnover24h) };
                return { p: parseFloat(t.lastPrice), bp: parseFloat(t.bidPrice), ap: parseFloat(t.askPrice), v: parseFloat(t.volume), q: parseFloat(t.quoteVolume) };
            };

            return {
                symbol,
                b: createData(b, 'b'),
                m: createData(m, 'm'),
                by: createData(by, 'by'),
                k: createData(k, 'k'),
                diff: diff.toFixed(2)
            };
        }).filter(item => item.diff > 0); // Зөвхөн үнийн зөрүүтэйг нь харуулах

        // Эрэмбэлэх: Хамгийн өндөр spread-тэй нь дээрээ
        formatted.sort((a, b) => b.diff - a.diff);

        return res.status(200).json({ data: formatted });
    } catch (error) {
        return res.status(500).json({ error: error.message });
    }
}