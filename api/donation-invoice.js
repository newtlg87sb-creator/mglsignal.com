// api/donation-invoice.js
// Динамик дүнтэй хандив үүсгэх бэкенд код

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { userId, price_amount } = req.body;

    if (!userId || !price_amount) {
      return res.status(400).json({ error: 'User ID and Amount are required' });
    }

    // NOWPayments API руу хүсэлт шиднэ
    const response = await fetch('https://api.nowpayments.io/v1/invoice', {
      method: 'POST',
      headers: {
        'x-api-key': process.env.NOWPAYMENTS_API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        price_amount: parseFloat(price_amount), // Хэрэглэгчийн сонгосон дүн (5, 10, 30 гэх мэт)
        price_currency: 'usd',
        pay_currency: 'usdtbsc', // USDT (BEP20) default
        
        order_id: userId, 
        order_description: `MGL Signal Donation - $${price_amount}`,
        success_url: 'https://mglsignal.com/main_about.html?payment=success',
        cancel_url: 'https://mglsignal.com/main_about.html'
      })
    });

    const data = await response.json();

    if (data.invoice_url) {
      return res.status(200).json({ invoiceUrl: data.invoice_url });
    } else {
      console.error('NOWPayments Error response:', data);
      return res.status(500).json({ error: data.message || 'Failed to create donation invoice' });
    }

  } catch (error) {
    console.error('Donation Invoice crash:', error.message);
    return res.status(500).json({ error: 'Internal Server Error' });
  }
}