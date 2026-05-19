// Энэ файл заавал /api/ хавтас дотор байх ёстой
// Зам: g:\mglsignal.com\api\forgot-password.js

import { createClient } from '@supabase/supabase-js';

export default async function handler(req, res) {
  // Зөвхөн POST хүсэлтийг зөвшөөрнө
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method Not Allowed' });
  }

  const { email, redirectTo } = req.body;

  // Vercel Environment Variables-аас утгуудыг авна
  const supabase = createClient(
    process.env.SUPABASE_URL,
    process.env.SUPABASE_SERVICE_ROLE_KEY
  );

  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: redirectTo,
  });

  if (error) {
    return res.status(400).json({ message: error.message });
  }

  return res.status(200).json({ message: 'Нууц үг сэргээх холбоос имэйл рүү илгээгдлээ.' });
}