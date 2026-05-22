const express = require('express');
const cors = require('cors');
const marketService = require('./market_service');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());

// Зах зээлийн датаг татаж, Supabase руу шидэх процессыг эхлүүлэх
marketService.start();

app.get('/', (req, res) => {
    const data = marketService.getMarketData();
    res.json({ 
        status: "Market Service is Online", 
        lastUpdate: data.lastUpdate 
    });
});

app.listen(port, () => {
    console.log(`Backend server listening on port ${port}`);
});