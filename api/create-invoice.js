// api/create-invoice.js
// Төлбөрийн хуудас дээр USDT (BEP20)-ийг default-аар харуулах тохиргоотой код

export default async function handler(req, res) {
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const { userId } = req.body;

    if (!userId) {
      return res.status(400).json({ error: 'User ID is required' });
    }

    // NOWPayments API руу хүсэлт шиднэ
    const response = await fetch('https://api.nowpayments.io/v1/invoice', {
      method: 'POST',
      headers: {
        'x-api-key': process.env.NOWPAYMENTS_API_KEY,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        price_amount: 20, // $20 доллар
        price_currency: 'usd',
        
        // 🚨 МАШ ЧУХАЛ: USDT (BEP20)-ийг default болгож байна
        // NOWPayments дээр USDT BEP20-ийн кодоор 'usdtbsc' гэж бичдэг шүү!
        pay_currency: 'usdtbsc', 
        
        order_id: userId, // Хэрэглэгчийн Supabase UUID
        order_description: 'MGL Signal Alpha Plan 1-Month Subscription',
        success_url: 'https://mglsignal.com/dashboard?payment=success',
        cancel_url: 'https://mglsignal.com/pricing'
      })
    });

    const data = await response.json();

    if (data.invoice_url) {
      return res.status(200).json({ invoiceUrl: data.invoice_url });
    } else {
      console.error('NOWPayments Error response:', data);
      return res.status(500).json({ error: data.message || 'Failed to create invoice' });
    }

  } catch (error) {
    console.error('Invoice creation crash:', error.message);
    return res.status(500).json({ error: 'Internal Server Error' });
  }
}