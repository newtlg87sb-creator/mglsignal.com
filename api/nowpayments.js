// api/nowpayments.js
// Чиний "User control" хүснэгтийн бүтцэд 100% тааруулсан ES Module бэкенд код

import crypto from 'crypto';
import { createClient } from '@supabase/supabase-js';

// 1. Supabase бэкенд клайент (SERVICE_ROLE_KEY ашиглаж байгаа тул RLS-ийг алгасна)
const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_SERVICE_ROLE_KEY
);

export default async function handler(req, res) {
  // Зөвхөн POST хүсэлт хүлээж авна
  if (req.method !== 'POST') {
    return res.status(405).json({ error: 'Method not allowed' });
  }

  try {
    const ipnSignature = req.headers['x-nowpayments-sig'];
    const ipnSecret = process.env.NOWPAYMENTS_IPN_SECRET;

    if (!ipnSignature || !ipnSecret) {
      return res.status(400).send('Missing signature or secret');
    }

    // 2. NOWPayments-аас ирсэн өгөгдлийг эрэмбэлж кодлох (Хамгаалалт)
    const sortedData = Object.keys(req.body)
      .sort()
      .reduce((obj, key) => {
        obj[key] = req.body[key];
        return obj;
      }, {});

    const hmac = crypto.createHmac('sha512', ipnSecret);
    hmac.update(JSON.stringify(sortedData));
    const signature = hmac.digest('hex');

    // 3. Хэрэв гарын үсэг зөрвөл хакер гэж үзнэ
    if (signature !== ipnSignature) {
      console.error('⚠️ Анхаар! Баталгаагүй Webhook илэрлээ!');
      return res.status(401).send('Invalid signature');
    }

    // 4. Төлбөрийн мэдээллийг хүлээж авах
    const { payment_status, order_id } = req.body;

    console.log(`Төлбөрийн статус: ${order_id} -> ${payment_status}`);

    // 5. Төлбөр амжилттай 'finished' болсон үед Supabase-ийг шинэчлэх
    if (payment_status === 'finished') {
      
      // 🚨 ШИНЭЧЛЭЛТ: Чиний "User control" хүснэгт болон баганын нэрнүүдтэй яг таг нийцүүлсэн хэсэг
      const { error } = await supabase
        .from('User control') // Чиний хүснэгтийн нэр
        .update({ 
          membership_type: 'alpha', // Эрхийг нь 'alpha' болгох
          membership_expires_at: new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString(), // 30 хоног нэмэх (ISO формат)
          updated_at: new Date().toISOString()
        }) 
        .eq('id', order_id); // Төлбөр үүсгэхдээ шидсэн Хэрэглэгчийн ID (UUID)

      if (error) {
        console.error('Supabase шинэчлэхэд алдаа гарлаа:', error.message);
        return res.status(500).send('Database update failed');
      }

      console.log(`🎉 Хэрэглэгч ${order_id}-ийн Alpha эрх Supabase дээр амжилттай идэвхжлээ!`);
      return res.status(200).send('OK');
    }

    // Хэрэв төлбөр хараахан батлагдаж дуусаагүй (confirming, waiting) бол
    return res.status(200).send('Waiting for confirmation');

  } catch (err) {
    console.error('Webhook алдаа:', err.message);
    return res.status(500).send('Internal Server Error');
  }
}