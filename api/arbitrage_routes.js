const express = require('express');
const router = express.Router();
const marketService = require('./market_service');

router.get('/', (req, res) => {
    res.json({ data: marketService.getMarketData() });
});

router.get('/symbols', (req, res) => {
    const symbols = marketService.getSymbols();
    res.json(symbols);
});

router.get('/status', (req, res) => {
    res.json({ status: "Online", timestamp: new Date() });
});

module.exports = router;