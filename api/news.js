// Node.js 18+ хувилбарт fetch нь native болсон тул node-fetch шаардлагагүй

export default async function handler(req, res) {
  // Vercel-ийн Environment Variables хэсэгт CRYPTOCOMPARE_API_KEY-г тохируулаарай
  const apiKey = process.env.CRYPTOCOMPARE_API_KEY;

  if (!apiKey) {
    return res.status(500).json({ error: "API Key тохируулагдаагүй байна" });
  }
  
  try {
    const response = await fetch(`https://min-api.cryptocompare.com/data/v2/news/?lang=EN&api_key=${apiKey}`);
    const data = await response.json();
    res.status(200).json(data);
  } catch (error) {
    res.status(500).json({ error: "Мэдээ татахад алдаа гарлаа" });
  }
}