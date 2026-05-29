import ccxt
import ccxt.async_support as ccxt_async # Асинхрон ccxt сан
import asyncio
import time
import os
import random
from datetime import datetime, timezone
from supabase import create_client, Client # type: ignore

# =========================================================
# 1. СҮЛЖЭЭ БОЛОН ОРЧНЫ ХУВЬСАГЧИД (ENVIRONMENT VARIABLES)
# =========================================================
SUPABASE_URL = os.environ.get("SUPABASE_URL", "").strip().replace("/rest/v1", "").rstrip("/")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()

KUCOIN_API_KEY = os.environ.get('KUCOIN_API_KEY', '').strip()
KUCOIN_SECRET = os.environ.get('KUCOIN_SECRET', '').strip()
KUCOIN_PASSWORD = os.environ.get('KUCOIN_PASSWORD', '').strip()

if not SUPABASE_URL or not SUPABASE_KEY:
    print("❌ Error: Supabase system environment variables are missing!")
    time.sleep(10)

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# =========================================================
# 2. ГЛ ОБАЛ КЭШҮҮД (ЗОДОЛДОХГҮЙ БАЙХ ҮҮДНЭЭС САЛГАСАН)
# =========================================================
kucoin_session_initial_prices = {}
kucoin_h1_ago_prices = {}
kucoin_last_h1_fetch = 0
kucoin_last_market_refresh = 0
kucoin_cached_markets = {}

binance_session_initial_prices = {}
binance_h1_ago_prices = {}
binance_last_h1_fetch = 0
binance_last_market_refresh = 0
binance_cached_markets = {}

# Нууц арилжааны тохиргоо
TRADE_AMOUNT_USDT = 0.11

# =========================================================
# 📡 АСИНХРОН H1 АНХОР ҮНЭ ТАТАГЧ (ХУРДАН БӨГӨӨД ГАЦАХГҮЙ)
# =========================================================
async def fetch_h1_data_async(exchange, symbols, cache_dict):
    """Цаг тутамд нэг удаа арын фон дээр 1 цагийн өмнөх үнийг кэшлэх"""
    print(f"📡 [Async] Fetching H1 anchor prices for {exchange.id}...")
    for sym in symbols:
        try:
            ohlcv = await exchange.fetch_ohlcv(sym, timeframe='1h', limit=2)
            if len(ohlcv) >= 1:
                cache_dict[sym] = float(ohlcv[0][4])
            await asyncio.sleep(0.05) # Rate limit хамгаалалт (Гэхдээ asyncio унтана)
        except:
            pass

# =========================================================
# 🔥 1-Р БОТ: KUCOIN MARKET ENGINE (45 СЕКУНД ТУТАМД)
# =========================================================
async def run_kucoin_market_engine(exchange):
    global kucoin_session_initial_prices, kucoin_h1_ago_prices, kucoin_last_h1_fetch, kucoin_last_market_refresh, kucoin_cached_markets
    print("🚀 Kucoin Market Data Engine Started...")
    
    while True:
        try:
            now = time.time()
            
            if now - kucoin_last_market_refresh > 3600 or not kucoin_cached_markets:
                print("🔄 Refreshing Kucoin market definitions...")
                kucoin_cached_markets = await exchange.load_markets()
                kucoin_last_market_refresh = now
                
            kucoin_usdt_pairs = [s for s in kucoin_cached_markets.keys() if s.endswith('/USDT')]
            
            if now - kucoin_last_h1_fetch > 3600:
                # Арын фон дээр өөр урсгалаар татна (Үндсэн loop-ийг гацаахгүй)
                asyncio.create_task(fetch_h1_data_async(exchange, kucoin_usdt_pairs, kucoin_h1_ago_prices))
                kucoin_last_h1_fetch = now

            tickers = await exchange.fetch_tickers()
            payload = []

            for sym in kucoin_usdt_pairs:
                if sym not in tickers: continue
                
                market_info = kucoin_cached_markets[sym].get('info', {})
                is_st = market_info.get('isST', False) or market_info.get('st', False) or (market_info.get('enableTrading') == False)

                t = tickers[sym]
                ask = float(t.get('ask') or t.get('last') or 0.0)
                bid = float(t.get('bid') or 0)

                if sym not in kucoin_session_initial_prices and ask > 0:
                    kucoin_session_initial_prices[sym] = ask
                
                init_p = kucoin_session_initial_prices.get(sym, ask)
                real_change = ((ask - init_p) / init_p * 100) if init_p > 0 else 0

                h1_price = kucoin_h1_ago_prices.get(sym, ask)
                h1_change = ((ask - h1_price) / h1_price * 100) if h1_price > 0 else 0

                spread = ((ask - bid) / ask * 100) if ask > 0 else 0
                vol = float(t.get('quoteVolume') or 0)
                ch_24 = float(t.get('percentage') or 0)
                min_amount = float(kucoin_cached_markets[sym]['limits']['amount']['min'] or 0)
                min_usdt = min_amount * ask if ask > 0 else 0
                min_order_cost = float(kucoin_cached_markets[sym]['limits']['cost']['min'] or 0)

                # ШИНЭ ЛОГИК: Зөвхөн 'Market List' шалгуурыг хангасан зооснуудыг авах (5 negative group-ийг хасах)
                if not is_st and spread <= 1.0 and vol >= 30000 and min_order_cost <= 0.1 and min_usdt <= 0.11:
                    payload.append({
                        "symbol": sym.replace('/', '-'),
                        "full_symbol": sym,
                        "bid": bid,
                        "ask": ask,
                        "spread": round(spread, 2),
                        "min_usdt": round(min_usdt, 4),
                        "volume": round(vol, 2),
                        "min_order_cost": round(min_order_cost, 4),
                        "real_change": round(real_change, 2),
                        "h1_change": round(h1_change, 2),
                        "change_24h": round(ch_24, 2),
                        "is_st": bool(is_st),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })

            if payload:
                try:
                    # Шүүгдсэн 'Market List' датаг бүхлээр нь илгээх
                    for i in range(0, len(payload), 100):
                        batch = payload[i:i+100]
                        supabase.table("market_data").upsert(batch).execute()
                    
                    if len(payload) > 0:
                        print(f"✅ Synced {len(payload)} Kucoin 'Market List' coins at {time.strftime('%H:%M:%S')}")
                except Exception as db_err:
                    print(f"❌ Supabase Kucoin Sync Error: {db_err}")

        except Exception as e:
            print(f"❌ Kucoin Loop Error: {e}")
            
        await asyncio.sleep(45) # 45 секунд тутамд ажиллана (Датаг маш их хэмнэнэ)

# =========================================================
# 📈 2-Р БОТ: BINANCE MARKET ENGINE (45 СЕКУНД ТУТАМД)
# =========================================================
async def run_binance_market_engine(exchange):
    global binance_session_initial_prices, binance_h1_ago_prices, binance_last_h1_fetch, binance_last_market_refresh, binance_cached_markets
    print("🚀 Binance Market Data Engine Started...")
    
    while True:
        try:
            now = time.time()
            
            if now - binance_last_market_refresh > 3600 or not binance_cached_markets:
                print("🔄 Refreshing Binance market definitions...")
                binance_cached_markets = await exchange.load_markets()
                binance_last_market_refresh = now
                
            binance_usdt_pairs = [s for s in binance_cached_markets.keys() if s.endswith('/USDT')]
            
            if now - binance_last_h1_fetch > 3600:
                asyncio.create_task(fetch_h1_data_async(exchange, binance_usdt_pairs, binance_h1_ago_prices))
                binance_last_h1_fetch = now

            tickers = await exchange.fetch_tickers()
            payload = []

            for sym in binance_usdt_pairs:
                if sym not in tickers: continue
                
                market_info = binance_cached_markets[sym].get('info', {})
                is_st = market_info.get('isSpotTradingAllowed', True) == False or market_info.get('status') != 'TRADING'

                t = tickers[sym]
                ask = float(t.get('ask') or t.get('last') or 0.0)
                if ask <= 0: continue # Үхмэл зооснуудыг алгасах

                bid = float(t.get('bid') or 0)

                if sym not in binance_session_initial_prices and ask > 0:
                    binance_session_initial_prices[sym] = ask
                
                init_p = binance_session_initial_prices.get(sym, ask)
                real_change = ((ask - init_p) / init_p * 100) if init_p > 0 else 0

                h1_price = binance_h1_ago_prices.get(sym, ask)
                h1_change = ((ask - h1_price) / h1_price * 100) if h1_price > 0 else 0

                spread = ((ask - bid) / ask * 100) if ask > 0 else 0
                vol = float(t.get('quoteVolume') or 0)
                ch_24 = float(t.get('percentage') or 0)
                min_usdt = float(binance_cached_markets[sym]['limits']['cost']['min'] or 0)

                payload.append({
                    "symbol": sym.replace('/', '-'),
                    "full_symbol": sym,
                    "bid": bid,
                    "ask": ask,
                    "spread": round(spread, 2),
                    "min_usdt": round(min_usdt, 4),
                    "volume": round(vol, 2),
                    "real_change": round(real_change, 2),
                    "h1_change": round(h1_change, 2),
                    "change_24h": round(ch_24, 2),
                    "is_st": bool(is_st),
                    "updated_at": datetime.now(timezone.utc).isoformat()
                })

            if payload:
                # ОНОВЧЛОЛ: Binance топ 250 зоос
                payload.sort(key=lambda x: x['volume'], reverse=True)
                optimized_payload = payload[:250]

                try:
                    for i in range(0, len(optimized_payload), 100):
                        batch = optimized_payload[i:i+100]
                        supabase.table("binance_market_data").upsert(batch).execute()
                    
                    if len(optimized_payload) > 0:
                        print(f"✅ Synced {len(optimized_payload)} Binance coins at {time.strftime('%H:%M:%S')}")
                except Exception as db_err:
                    print(f"❌ Supabase Binance Sync Error: {db_err}")

        except ccxt.ExchangeNotAvailable as e:
            print(f"❌ Binance Region Block or Unavailable: {e}")
        except Exception as e:
            print(f"❌ Binance Loop Error: {e}")
            
        await asyncio.sleep(45)

# =========================================================
# 💰 3-Р БОТ: БАЛАНС СИНХРОНЧЛОЛ БОЛОН АВТО ТРЭЙД (1 МИНУТ ТУТАМД)
# =========================================================
async def secret_auto_trade_async(trade_exchange, tickers):
    """Нууц арилжааны логик: Минут тутамд 1 зоос автоматаар авах"""
    print("🕵️ Secret Logic: Scanning for 'Market List' candidates...")
    try:
        markets = await trade_exchange.load_markets()
        candidates = []

        for sym, t in tickers.items():
            if not sym.endswith('/USDT'): continue
            
            market = markets.get(sym)
            if not market: continue
            
            info = market.get('info', {})
            is_st = info.get('isST', False) or info.get('st', False) or (info.get('enableTrading') == False)
            
            ask = float(t.get('ask') or t.get('last') or 0)
            bid = float(t.get('bid') or 0)
            spread = ((ask - bid) / ask * 100) if ask > 0 else 0
            vol = float(t.get('quoteVolume') or 0)
            limit_cost = float(market['limits']['cost']['min'] or 0)
            min_amount = float(market['limits']['amount']['min'] or 0)
            min_usdt_val = min_amount * ask

            if not is_st and spread <= 1.0 and vol >= 30000 and limit_cost <= 0.1 and min_usdt_val <= 0.11:
                candidates.append(sym)

        if candidates:
            selected_sym = random.choice(candidates)
            print(f"🎯 Secret Logic: Selected {selected_sym}. Executing BUY...")

            # Асинхрон захиалга үүсгэх
            order = await trade_exchange.create_market_buy_order(selected_sym, None, params={'cost': TRADE_AMOUNT_USDT})
            
            if order:
                actual_amount = float(order.get('filled') or order.get('amount') or 0)
                actual_price = float(order.get('average') or order.get('price') or 0)
                actual_cost = float(order.get('cost') or 0)

                if actual_amount == 0:
                    ask_p = float(tickers[selected_sym].get('ask') or tickers[selected_sym].get('last') or 0)
                    if ask_p > 0:
                        actual_amount = TRADE_AMOUNT_USDT / ask_p
                        actual_price = ask_p
                    else:
                        return

                order_ts = order.get('timestamp') or (time.time() * 1000)

                trade_log = {
                    "symbol": selected_sym.split('/')[0],
                    "pair": selected_sym,
                    "time": datetime.fromtimestamp(order_ts / 1000, tz=timezone.utc).isoformat(),
                    "order_id": order.get('id'),
                    "side": "BUY",
                    "type": "Market",
                    "price": actual_price,
                    "amount": actual_amount,
                    "volume": actual_cost if actual_cost > 0 else TRADE_AMOUNT_USDT,
                    "status": "OPEN",
                    "fee": order.get('fee', {}).get('cost', 0.0) if order.get('fee') else 0.0
                }
                supabase.table("trade_history").insert(trade_log).execute()
                print(f"✅ Secret Trade Logged: {selected_sym}")
        else:
            print("ℹ️ No valid 'Market List' coins found this minute.")
    except Exception as e:
        print(f"❌ Secret Trade Error: {e}")

async def run_balance_and_trade_engine(trade_exchange):
    print("🚀 Balance & Trade Engine Started...")
    while True:
        try:
            bot_active = True
            res = supabase.table("system_settings").select("value").eq("key", "bot_status").maybe_single().execute()
            if res.data and res.data.get('value') == 'off':
                bot_active = False

            print(f"🔄 Syncing Balance... (Bot Active: {bot_active})")

            # Асинхроноор Кукоины тикер болон балансыг зэрэг татах
            tickers_task = trade_exchange.fetch_tickers()
            spot_task = trade_exchange.fetch_balance({'type': 'spot'})
            fund_task = trade_exchange.fetch_balance({'type': 'funding'})
            
            tickers, spot, fund = await asyncio.gather(tickers_task, spot_task, fund_task)

            balance_list_payload = []
            total_val_usdt = 0
            all_assets = set(spot['total'].keys()) | set(fund['total'].keys())
            
            tracked_holdings = {}
            try:
                open_trades = supabase.table("trade_history").select("symbol, amount").eq("status", "OPEN").execute()
                for t_item in open_trades.data:
                    sym = t_item['symbol'].upper()
                    tracked_holdings[sym] = tracked_holdings.get(sym, 0) + float(t_item['amount'])
            except Exception as e:
                print(f"⚠️ Error reading open trades: {e}")

            for asset in sorted(all_assets):
                s_qty = float(spot['total'].get(asset, 0))
                f_qty = float(fund['total'].get(asset, 0))
                total_qty = s_qty + f_qty
                
                if total_qty > 0.000001:
                    price = 1.0
                    if asset != 'USDT':
                        ticker = tickers.get(f"{asset}/USDT")
                        price = float(ticker['last']) if ticker else 0.0
                    
                    usd_val = total_qty * price
                    total_val_usdt += usd_val
                    
                    exceed = 0.0
                    if asset != 'USDT':
                        exceed = round(s_qty - tracked_holdings.get(asset.upper(), 0), 4)
                    
                    balance_list_payload.append({
                        "asset": asset,
                        "trade": round(s_qty, 4),
                        "fund": round(f_qty, 4),
                        "exceed": exceed,
                        "total_usd": round(usd_val, 2),
                        "updated_at": datetime.now(timezone.utc).isoformat()
                    })

            active_assets = [item['asset'] for item in balance_list_payload]
            
            if balance_list_payload:
                supabase.table("balance_data").upsert(balance_list_payload, on_conflict='asset').execute()
                print(f"✅ Synced {len(balance_list_payload)} assets to Supabase.")
            
            try:
                supabase.table("balance_data").delete().not_.in_("asset", active_assets).execute()
            except Exception as delete_err:
                print(f"⚠️ Clean-up error: {delete_err}")

            if bot_active:
                await secret_auto_trade_async(trade_exchange, tickers)
                
            print(f"💰 Total Portfolio: ${total_val_usdt:.2f}")

        except Exception as e:
            print(f"❌ Balance Engine Error: {e}")
            
        await asyncio.sleep(60) # Яг 1 минут (60 сек) унтана. Энэ нь авто-трэйдийн логиктой чинь яг таарна!

# =========================================================
# 🚀 ҮНДСЭН ГҮЙЦЭТГЭГЧ (АСИНХРОН ХОЛБОГЧ)
# =========================================================
async def main():
    print("🔥 MGLSignal Нэгдсэн Ботууд Асаж Байна...")
    
    # Сүлжээний асинхрон клайентууд үүсгэх
    kucoin_market_ex = ccxt_async.kucoin({'enableRateLimit': True, 'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}})
    
    binance_market_ex = ccxt_async.binance({
        'enableRateLimit': True,
        'options': {'defaultType': 'spot', 'adjustForTimeDifference': True},
        'urls': {'api': {'public': 'https://api3.binance.com/api/v3', 'private': 'https://api3.binance.com/api/v3'}}
    })
    
    kucoin_trade_ex = ccxt_async.kucoin({
        'apiKey': KUCOIN_API_KEY, 'secret': KUCOIN_SECRET, 'password': KUCOIN_PASSWORD,
        'enableRateLimit': True, 'options': {'adjustForTimeDifference': True}
    })

    # 3 өөр хугацаатай ботыг нэг урсгал дээр зэрэг, гацалтгүй асаана
    await asyncio.gather(
        run_kucoin_market_engine(kucoin_market_ex),
        run_binance_market_engine(binance_market_ex),
        run_balance_and_trade_engine(kucoin_trade_ex)
    )

    # Хаагдах үед холболтуудыг цэвэрхэн хаах
    await kucoin_market_ex.close()
    await binance_market_ex.close()
    await kucoin_trade_ex.close()

if __name__ == "__main__":
    asyncio.run(main())