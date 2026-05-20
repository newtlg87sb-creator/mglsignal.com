// Энэ файл заавал /api/ хавтас дотор байх ёстой
// Зам: g:\mglsignal.com\api\forgot-password.js

import { createClient } from '@supabase/supabase-js';

export default async function handler(req, res) {
  // Зөвхөн POST хүсэлтийг зөвшөөрнө
  if (req.method !== 'POST') {
    return res.status(405).json({ message: 'Method Not Allowed' });
  }

  const { email, redirectTo } = req.body;

  const supabaseUrl = process.env.SUPABASE_URL;
  const supabaseServiceKey = process.env.SUPABASE_SERVICE_ROLE_KEY || process.env.SUPABASE_KEY;

  if (!supabaseUrl || !supabaseServiceKey) {
    return res.status(500).json({ message: 'Серверийн тохиргоо дутуу байна (API Keys missing).' });
  }

  const supabase = createClient(
    supabaseUrl,
    supabaseServiceKey
  );

  const { error } = await supabase.auth.resetPasswordForEmail(email, {
    redirectTo: redirectTo,
  });

  if (error) {
    return res.status(400).json({ message: error.message });
  }

  return res.status(200).json({ message: 'Нууц үг сэргээх холбоос имэйл рүү илгээгдлээ.' });
}