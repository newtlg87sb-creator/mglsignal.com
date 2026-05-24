import sys
import threading
import ccxt
import time

from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QLabel,
                             QLineEdit, QTableWidget, QTableWidgetItem,
                             QHeaderView, QComboBox, QHBoxLayout, QMenu, QPushButton, QCheckBox)
from PyQt6.QtCore import (pyqtSignal, QTimer, Qt, QThread, QObject, QMetaObject, Q_ARG, pyqtSlot)
from PyQt6.QtGui import QColor, QFont

# Тоон утгаар зөв эрэмбэлэхэд зориулсан класс
class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            v1 = self.data(Qt.ItemDataRole.EditRole)
            v2 = other.data(Qt.ItemDataRole.EditRole)
            if v1 is None: return True
            if v2 is None: return False
            return float(v1) < float(v2)
        except (ValueError, TypeError):
            return super().__lt__(other)

# WebSocket ажиллуулах thread
class ExchangeWebSocketWorker(QObject):
    ticker_updated = pyqtSignal(str, float, float, float)
    ws_connected = pyqtSignal(bool) # Холболтын төлөв мэдээлэх

    def __init__(self, exchange, symbols):
        super().__init__()
        self._exchange = exchange
        self._symbols = symbols
        self._running = True

    def stop(self):
        self._running = False

    def run(self):
        # ЧУХАЛ: ccxt.pro ашиглаагүй үед watch_tickers ажиллахгүй.
        # Тиймээс энэ хэсгийг ажиллах боломжтой болтол WS status-ийг шалгах хэрэгтэй.
        self.ws_connected.emit(False) 
        
        # Хэрэв та ccxt.pro суулгаагүй бол энэ хэсэг ажиллахгүй тул 
        # REST API датаг WS-ийн оронд ашиглах логик нэмсэн.
        if not hasattr(self._exchange, 'watch_tickers'):
            print("WS Error: ccxt.pro (asynchronous) is required for watch_tickers.")
            return

        while self._running:
            try:
                # Асинхрон орчин биш тул энэ нь block хийж магадгүй
                tickers = self._exchange.watch_tickers(self._symbols)
                self.ws_connected.emit(True)
                for symbol, t in tickers.items():
                    if t and t.get('last') is not None:
                        self.ticker_updated.emit(
                            symbol, 
                            float(t.get('last', 0)), 
                            float(t.get('bid', 0)), 
                            float(t.get('ask', 0))
                        )
            except Exception as e:
                self.ws_connected.emit(False)
                time.sleep(5)

# SpotMarketPanel доторх засалтууд:
class SpotMarketPanel(QWidget):
    
    refresh_signal = pyqtSignal()
    data_updated = pyqtSignal(list) # Шинэ өгөгдөл бэлэн болмогц логик руу илгээх

    def __init__(self, main_dashboard=None, creds=None):
        super().__init__()
        self.main_dashboard = main_dashboard

        # Exchange-ийг creds-ээр үүсгэх
        self.exchange = ccxt.kucoin({**(creds or {}),
            'enableRateLimit': True, 
            'options': {'defaultType': 'spot', 'adjustForTimeDifference': True}
        })

        self.price_history = {} 
        self.markets = {}
        self.all_data = []
        self.is_fetching = False
        self.sort_col = 8 
        self.sort_desc = True
        self.max_coins = 1000
        self.selected_symbol = None
        self.session_initial_prices = {} # Программ ажиллах үеийн үнийг хадгалах
        self.h1_ago_fixed_prices = {} # Биржээс татсан яг 1 цагийн өмнөх үнэ
        self.spread_cache = {}
        self.last_spread_update = 0
        # API ачаалал хянах хувьсагчууд
        self.api_call_count = 0
        self.last_api_reset = time.time()
        self.error_429_count = 0
        self.sentiment_type = "Real%" # Sentiment тооцох төрөл (1h% эсвэл Real%)
        
        self.ws_prices = {}
        self.ws_bids = {}
        self.ws_asks = {}
        self.ws_worker = None
        self.ws_thread = None

        self.ui_timer = QTimer(self)
        self.ui_timer.timeout.connect(self.refresh_table) 
        
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.start_update)

        # API метрикийг шинэчлэх таймер
        self.api_metrics_timer = QTimer(self)
        self.api_metrics_timer.timeout.connect(self.update_api_metrics)

        self.init_ui()
        self.load_kucoin_markets()
        self.ui_timer.start(500)
        self.timer.start(2000)
        self.api_metrics_timer.start(1000) # Таймерыг секунд тутамд ажиллуулна

    def init_ui(self):
        self.setWindowTitle("Kucoin Pro Terminal")
        self.setStyleSheet("background-color: #0f172a;")
        layout = QVBoxLayout(self)

        # Header controls
        controls = QHBoxLayout()
        self.status = QLabel("Connecting Kucoin...")
        self.status.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        
        # Sentiment тохируулах Combo
        self.sent_combo = QComboBox()
        self.sent_combo.addItems(["Sentiment: 1h%", "Sentiment: Real%"])
        self.sent_combo.setCurrentText("Sentiment: Real%")
        self.sent_combo.setStyleSheet("background: #1e293b; color: #38bdf8; padding: 4px; border-radius: 4px; font-size: 11px;")
        self.sent_combo.currentTextChanged.connect(self.on_sentiment_type_changed)

        self.ticker_search = QLineEdit()
        self.ticker_search.setPlaceholderText(" 🔍 Search Symbols...")
        self.ticker_search.setFixedWidth(130)
        self.ticker_search.setStyleSheet("""
            QLineEdit {
                background: #1e293b; color: white; padding: 8px; 
                border: 1px solid #334155; border-radius: 6px;
            }
        """)
        self.ticker_search.textChanged.connect(self.refresh_table)

        self.refresh_box = QComboBox()
        self.refresh_box.addItems(["1s", "2s", "5s", "10s"])
        self.refresh_box.setCurrentText("2s")
        self.refresh_box.setFixedHeight(24)
        self.refresh_box.setStyleSheet("background: #1e293b; color: white; padding: 2px; border-radius: 4px; font-size: 10px;")
        self.refresh_box.currentTextChanged.connect(self.change_interval)

        self.hide_blacklist_cb = QCheckBox("Hide Blacklist")
        self.hide_blacklist_cb.setFixedHeight(24)
        self.hide_blacklist_cb.setStyleSheet("color: #94a3b8; font-size: 10px; margin-left: 5px;")
        self.hide_blacklist_cb.stateChanged.connect(self.refresh_table)
        self.hide_blacklist_cb.setChecked(True)

        self.hide_spread_cb = QCheckBox("Hide Spread")
        self.hide_spread_cb.setFixedHeight(24)
        self.hide_spread_cb.setStyleSheet("color: #94a3b8; font-size: 10px; margin-left: 5px;")
        self.hide_spread_cb.stateChanged.connect(self.refresh_table)
        self.hide_spread_cb.setChecked(True)

        self.hide_vol_low_cb = QCheckBox("Hide Low Vol")
        self.hide_vol_low_cb.setFixedHeight(24)
        self.hide_vol_low_cb.setStyleSheet("color: #94a3b8; font-size: 10px; margin-left: 5px;")
        self.hide_vol_low_cb.stateChanged.connect(self.refresh_table)
        self.hide_vol_low_cb.setChecked(True)

        self.hide_min_high_cb = QCheckBox("Hide Min High")
        self.hide_min_high_cb.setFixedHeight(24)
        self.hide_min_high_cb.setStyleSheet("color: #94a3b8; font-size: 10px; margin-left: 5px;")
        self.hide_min_high_cb.stateChanged.connect(self.refresh_table)
        self.hide_min_high_cb.setChecked(True)

        self.hide_limit_high_cb = QCheckBox("Hide Limit High")
        self.hide_limit_high_cb.setFixedHeight(24)
        self.hide_limit_high_cb.setStyleSheet("color: #94a3b8; font-size: 10px; margin-left: 5px;")
        self.hide_limit_high_cb.stateChanged.connect(self.refresh_table)
        self.hide_limit_high_cb.setChecked(True)

        self.reset_real_btn = QPushButton("🔄 Reset Real%")
        self.reset_real_btn.setFixedSize(85, 24)
        self.reset_real_btn.setStyleSheet("background-color: #1e293b; color: #fbbf24; font-size: 10px; border-radius: 4px; border: 1px solid #fbbf24;")
        self.reset_real_btn.clicked.connect(self.reset_session_prices)

        self.expand_btn = QPushButton("↕ Maximize")
        self.expand_btn.setFixedSize(90, 24)
        self.expand_btn.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-size: 10px; border-radius: 4px; border: 1px solid #38bdf8;")
        self.expand_btn.clicked.connect(self.toggle_maximize)

        controls.addWidget(self.status)
        controls.addStretch()
        controls.addWidget(self.sent_combo)
        controls.addWidget(self.reset_real_btn)
        controls.addWidget(self.ticker_search)
        controls.addWidget(self.hide_blacklist_cb)
        controls.addWidget(self.hide_spread_cb)
        controls.addWidget(self.hide_vol_low_cb)
        controls.addWidget(self.hide_min_high_cb) # Шинэ checkbox нэмэгдсэн
        controls.addWidget(self.hide_limit_high_cb)
        controls.addWidget(self.expand_btn)
        controls.addWidget(self.refresh_box)
        layout.addLayout(controls)

        self.ws_status = QLabel("WS: Disconnected")
        self.ws_status.setStyleSheet("color: #64748b; font-size: 11px; margin-right: 15px;")

        # API Monitor Panel (UI-ийн доор нэмэх)
        self.api_monitor_layout = QHBoxLayout()
        self.api_monitor_layout.setContentsMargins(5, 0, 5, 5)
        self.req_label = QLabel("Req: 0/min")
        self.req_label.setStyleSheet("color: #38bdf8; font-size: 11px; margin-right: 10px;")
        self.limit_status = QLabel("Health: 100%")
        self.limit_status.setStyleSheet("color: #22c55e; font-size: 11px; margin-right: 10px;")
        self.error_label = QLabel("429s: 0")
        self.error_label.setStyleSheet("color: #94a3b8; font-size: 11px; margin-right: 15px;")

        self.api_monitor_layout.addWidget(self.ws_status)
        self.api_monitor_layout.addWidget(self.req_label)
        self.api_monitor_layout.addWidget(self.limit_status)
        self.api_monitor_layout.addWidget(self.error_label)
        self.api_monitor_layout.addStretch()
        
        layout.addLayout(self.api_monitor_layout)

        # Table Setup
        self.table = QTableWidget(0, 11) 
        self.table.setHorizontalHeaderLabels([
            "#", "Coin", "Bid", "Ask", "Spread%", "Min $", "Vol", "Real%", "1h%", "24%", "Limit $"
        ])
        
        # Багануудын хэмжээг тогтворжуулж, "түлхэлцэх" хөдөлгөөнийг зогсоох
        header = self.table.horizontalHeader()
        # Бүх багануудыг тэнцүү хувааж сунгах
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        
        # # Индекс баганыг ( # ) агуулгаар нь хэмжээг нь тааруулж бусад баганад зай гаргаж болно
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        # Харин Coin нэрэнд арай илүү зай өгөхөөр үлдээж болно
        header.setStretchLastSection(True)

        self.table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStyleSheet("QHeaderView::section { background-color: #1e293b; color: #94a3b8; padding: 6px; border: none; font-weight: bold; }")
        self.table.horizontalHeader().sectionClicked.connect(self.on_header_clicked)
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Хэвтээ jitter-ийг устгах
        
        # STYLE: outline: none нэмж "хайрцаг" харагдахаас сэргийлнэ
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #0f172a; color: #e2e8f0; gridline-color: #1e293b;
                border: 1px solid #1e293b; outline: none;
            }
            QTableWidget::item { padding: 10px; border-bottom: 1px solid #1e293b; }
            QTableWidget::item:selected { background-color: #334155; color: white; }
        """)
        layout.addWidget(self.table)

    def load_kucoin_markets(self):
        def task():
            try:
                self.markets = self.safe_api_call(self.exchange.load_markets)
                usdt_pairs = [s for s in self.markets.keys() if s.endswith('/USDT')]
                QMetaObject.invokeMethod(self.status, "setText", Qt.ConnectionType.QueuedConnection, Q_ARG(str, f"📡 Online: {len(usdt_pairs)} Pairs"))
                self.start_ws(usdt_pairs)
                # Background-оор 1 цагийн өмнөх үнийг татаж эхлэх
                threading.Thread(target=self._fetch_h1_ohlcv_background, args=(usdt_pairs,), daemon=True).start()
            except Exception as e:
                QMetaObject.invokeMethod(self.status, "setText", Qt.ConnectionType.QueuedConnection, Q_ARG(str, f"❌ Market Load Error: {e}"))
        threading.Thread(target=task, daemon=True).start()

    def safe_api_call(self, func, *args, **kwargs):
        """API хүсэлт бүрийг бүртгэж, алдааг хянах функц"""
        start_time = time.perf_counter()
        try:
            self.api_call_count += 1
            result = func(*args, **kwargs)
            
            # Хариу өгөх хурдыг тооцох (одоогоор ашиглагдахгүй ч ирээдүйд хэрэг болно)
            # resp_time = time.perf_counter() - start_time
            # self.avg_response_time = (self.avg_response_time * 0.9) + (resp_time * 0.1)
            
            return result
        except Exception as e:
            if "429" in str(e): # Rate limit алдаа
                self.error_429_count += 1
                QMetaObject.invokeMethod(self.status, "setText", Qt.ConnectionType.QueuedConnection, Q_ARG(str, "⚠️ RATE LIMIT HIT! Slowing down..."))
            raise e # Алдааг цааш дамжуулна

    def _fetch_h1_ohlcv_background(self, symbols):
        """1 цагийн өмнөх бодит үнийг биржээс татаж түүхэнд нэмэх (Rate limit-д орохгүйгээр)"""
        # Rate limit-ээс айж байгаа бол хугацааг нь 0.5s болгож ихэсгэ
        for sym in symbols:
            if not self.timer.isActive(): break
            try:
                # fetch_ohlcv-г safe_api_call-аар дамжуулна
                ohlcv = self.safe_api_call(self.exchange.fetch_ohlcv, sym, timeframe='1h', limit=2)
                if len(ohlcv) >= 1:
                    self.h1_ago_fixed_prices[sym] = float(ohlcv[0][4])
                time.sleep(0.5) # 0.2-оос 0.5 болгож аюулгүй болгов
            except Exception as e:
                if "429" in str(e): # Too many requests алдаа гарвал 10 сек амрах
                    time.sleep(10)
                else:
                    time.sleep(1)

    @pyqtSlot(bool)
    def update_ws_status(self, connected):
        if connected:
            self.ws_status.setText("WS: Live Stream 🟢 Connected")
            self.ws_status.setStyleSheet("color: #22c55e; font-size: 11px;")
        else:
            self.ws_status.setText("WS: Disconnected (REST Mode)")
            self.ws_status.setStyleSheet("color: #ef4444; font-size: 11px;")

    def start_ws(self, symbols):
        self.ws_thread = QThread()
        self.ws_worker = ExchangeWebSocketWorker(self.exchange, symbols)
        self.ws_worker.moveToThread(self.ws_thread)
        self.ws_worker.ticker_updated.connect(self._update_ws_prices)
        self.ws_worker.ws_connected.connect(self.update_ws_status) # Төлөв холбох
        self.ws_thread.started.connect(self.ws_worker.run)
        self.ws_thread.start()

    def _update_ws_prices(self, symbol, last, bid, ask):
        self.ws_prices[symbol] = last
        self.ws_bids[symbol] = bid
        self.ws_asks[symbol] = ask
        self.ws_status.setText(f"WS: Live Stream 🟢 {symbol}")

    @pyqtSlot()
    def reset_session_prices(self):
        """Программ ажиллаж эхлэх үеийн үнийг тэглэж, Real%-ийг одоогийн үнээс тоолж эхлэх"""
        self.session_initial_prices = {}
        if self.main_dashboard:
            self.main_dashboard.log_signal.emit("🔄 Real% tracker reset to current market prices.")
        self.refresh_table()

    def toggle_maximize(self):
        """Market жагсаалтыг томруулах/багасгах дохиог MainDashboard руу илгээх"""
        if not self.main_dashboard: return
        if self.expand_btn.text() == "↕ Maximize":
            self.expand_btn.setText("↕ Restore")
            self.main_dashboard.maximize_market(True)
        else:
            self.expand_btn.setText("↕ Maximize")
            self.main_dashboard.maximize_market(False)

    def change_interval(self, val):
        self.timer.start(int(val.replace("s", "")) * 1000)

    def on_header_clicked(self, index):
        self.sort_desc = not self.sort_desc if self.sort_col == index else True
        self.sort_col = index
        self.refresh_table()

    def on_sentiment_type_changed(self, val):
        self.sentiment_type = "Real%" if "Real%" in val else "1h%"
        self.refresh_table()

    def start_update(self):
        if self.is_fetching or not self.markets: return
        self.is_fetching = True
        def task():
            try:
                # fetch_tickers-ийг safe_api_call-аар дамжуулна
                tickers = self.safe_api_call(self.exchange.fetch_tickers, params={'type': 'spot'})
                now = time.time()
                data = []
                symbols = [s for s in self.markets.keys() if s.endswith('/USDT') and s in tickers][:self.max_coins]
                for i, sym in enumerate(symbols):
                    t = tickers[sym]
                    # Last price-ийг алгасаж бодит Ask үнийг үндсэн үнээр (lp) авах
                    lp = float(t.get('ask') or t.get('last') or 0.0)
                    
                    # WS ажиллахгүй үед History Panel-д үнэ харуулахын тулд cache-г шинэчлэх
                    self.ws_prices[sym] = lp
                    self.ws_bids[sym] = float(t.get('bid') or 0)
                    self.ws_asks[sym] = float(t.get('ask') or 0)
                    
                    # Программ ажиллах үеийн анхны үнийг нэг удаа хадгалах
                    if sym not in self.session_initial_prices and lp > 0:
                        self.session_initial_prices[sym] = lp

                    if sym not in self.price_history: self.price_history[sym] = []
                    self.price_history[sym].append((now, lp))
                    self.price_history[sym] = [p for p in self.price_history[sym] if now - p[0] <= 3600]
                    
                    h1 = 0.0
                    # Эхлээд биржээс татсан 1 цагийн өмнөх үнийг ашиглахыг оролдоно
                    anchor_p = self.h1_ago_fixed_prices.get(sym)
                    if anchor_p and anchor_p > 0:
                        h1 = ((lp - anchor_p) / anchor_p) * 100
                    elif len(self.price_history[sym]) > 1:
                        old = self.price_history[sym][0][1]
                        if old > 0: h1 = ((lp - old) / old) * 100
                    
                    market = self.markets[sym]
                    info = market.get('info', {})
                    is_st = info.get('isST', False) or info.get('st', False) or (info.get('enableTrading') == False)
                    
                    # Real% тооцоолох
                    init_p = self.session_initial_prices.get(sym, lp)
                    real_change = ((lp - init_p) / init_p * 100) if init_p > 0 else 0.0

                    data.append({
                        "index": i,
                        "symbol": sym, "last": lp, "h1_change": h1, "real_change": real_change,
                        "change": float(t.get("percentage") or 0),
                        "volume": float(t.get("quoteVolume") or 0),
                        "bid": float(t.get("bid") or 0), "ask": float(t.get("ask") or 0),
                        "min_amount": market['limits']['amount']['min'] or 0.0,
                        "limit": market['limits']['cost']['min'] or 0.0,
                        "is_st": bool(is_st),
                        "live_spread": 0,
                        "val_usd": 0
                    })
                self.all_data = data
            except Exception as e: # safe_api_call-аас ирсэн алдааг энд барина
                # safe_api_call нь 429 алдааны мессежийг status label-д бичсэн тул энд дахин бичихгүй
                pass 
            finally: self.is_fetching = False
        threading.Thread(target=task, daemon=True).start()

    def update_api_metrics(self):
        """UI дээрх API мониторыг шинэчлэх"""
        now = time.time()
        elapsed = now - self.last_api_reset
        
        # Минут тутамд тоологчийг тэглэх
        if elapsed >= 60: 
            self.api_call_count = 0
            self.last_api_reset = now
            
        # UI шинэчлэх
        self.req_label.setText(f"Req: {self.api_call_count}/min")
        self.error_label.setText(f"429s: {self.error_429_count}")
        
        # Limit Health тооцох (Хэрэв алдаа гарвал эрүүл мэнд буурна)
        health = max(0, 100 - (self.error_429_count * 20)) # 429 алдаа бүр 20% эрүүл мэндийг бууруулна
        self.limit_status.setText(f"Health: {health:.0f}%")
        
        h_clr = "#22c55e" if health > 80 else "#fbbf24" if health > 40 else "#ef4444"
        self.limit_status.setStyleSheet(f"color: {h_clr}; font-size: 11px;")

    @pyqtSlot()
    def refresh_table(self):
        if not self.all_data: return

        # 1. Бүх зоосны тооцооллыг хийх (Стратегид зөв дата очихын тулд)
        now = time.time()
        should_update_spread = (now - self.last_spread_update >= 600)
        
        for d in self.all_data:
            sym = d['symbol'].upper()
            d['live_bid'] = self.ws_bids.get(sym, d['bid'])
            d['live_ask'] = self.ws_asks.get(sym, d['ask'])
            
            current_live_spread = ((d['live_ask']-d['live_bid'])/d['live_ask']*100) if d['live_ask']>0 else 0
            if should_update_spread or sym not in self.spread_cache:
                self.spread_cache[sym] = current_live_spread
            d['live_spread'] = self.spread_cache[sym]
            
            # Val_usd (Min $) тооцоолохдоо Ask үнийг ашиглах
            current_price = d['live_ask'] if d['live_ask'] > 0 else d['last']
            d['val_usd'] = d['min_amount'] * current_price

        if should_update_spread:
            self.last_spread_update = now

        # 2. Ангилал болон Шүүлтүүр (Centralized Logic)
        search = self.ticker_search.text().upper()
        
        active_syms = set()
        blacklist = set()
        if hasattr(self, 'main_dashboard') and hasattr(self.main_dashboard, 'active_symbols'):
            active_syms = {s.upper() for s in self.main_dashboard.active_symbols.keys()}
        if hasattr(self, 'main_dashboard') and hasattr(self.main_dashboard, 'handler'):
            blacklist = self.main_dashboard.handler.blacklist

        act_list, bl_list, spread_list, low_vol_list, min_high_list, limit_high_list, mkt_list = [], [], [], [], [], [], []
        strategy_mkt_list = [] # Стратегид зориулсан хайлтаас хамааралгүй цэвэр жагсаалт

        for d in self.all_data:
            sym = d['symbol']
            base = sym.split('/')[0]
            is_in_search = search in sym

            if sym in active_syms or base in active_syms:
                if is_in_search: act_list.append(d)
            elif d['is_st'] or sym in blacklist or base in blacklist:
                if is_in_search and not self.hide_blacklist_cb.isChecked(): bl_list.append(d)
            elif d['live_spread'] > 1.0:
                if is_in_search and not self.hide_spread_cb.isChecked(): spread_list.append(d)
            elif d['volume'] < 30000:
                if is_in_search and not self.hide_vol_low_cb.isChecked(): low_vol_list.append(d)
            elif d.get('limit', 0) > 0.1: # Лимит нь 0.1-ээс их бол тусад нь ангилна
                if is_in_search and not self.hide_limit_high_cb.isChecked(): limit_high_list.append(d)
            elif d.get('val_usd', 0) > 0.11: # val_usd-ээр шалгана
                if is_in_search and not self.hide_min_high_cb.isChecked(): min_high_list.append(d)
            else:
                # Энэ бол жинхэнэ "Market List" зоос (ямар нэг хязгаарлалтгүй)
                strategy_mkt_list.append(d)
                if is_in_search: mkt_list.append(d)

        # Sentiment (Зөвхөн харагдаж буй зооснуудаар тооцно)
        all_visible = act_list + bl_list + spread_list + low_vol_list + min_high_list + limit_high_list + mkt_list
        if not all_visible: all_visible = strategy_mkt_list # Хайлт хийгээгүй үед

        data_key = 'real_change' if self.sentiment_type == "Real%" else 'h1_change'
        
        # Өсөлт, уналтын тоо (0.5% босго)
        ups = len([d for d in all_visible if d.get(data_key, 0) > 0.5])
        dns = len([d for d in all_visible if d.get(data_key, 0) < -0.5])
        
        if ups > dns * 3 and ups > 5:
            sent_text = "🚀 STRONG BULL ↑↑"
            clr = "#22c55e" # Хурц ногоон
        elif ups > dns * 1.5:
            sent_text = "📈 BULL ↑"
            clr = "#4ade80" # Цайвар ногоон
        elif dns > ups * 3 and dns > 5:
            sent_text = "🩸 STRONG BEAR ↓↓"
            clr = "#ef4444" # Хурц улаан
        elif dns > ups * 1.5:
            sent_text = "📉 BEAR ↓"
            clr = "#f87171" # Цайвар улаан
        else:
            sent_text = "⚖️ FLAT ↔"
            clr = "#94a3b8" # Саарал

        self.status.setText(f"{sent_text} | Up: {ups} | Down: {dns} ({self.sentiment_type})")
        self.status.setStyleSheet(f"color: {clr}; font-weight: bold; font-size: 12px;")

        total_real_change = sum(d.get('real_change', 0) for d in all_visible)
        total_h1_change = sum(d.get('h1_change', 0) for d in all_visible)
        total_24h_change = sum(d.get('change', 0) for d in all_visible)

        # Sort
        sort_key_map = {0: 'index', 1:'symbol', 2:'live_bid', 3:'live_ask', 4:'live_spread', 5:'val_usd', 6:'volume', 7:'real_change', 8:'h1_change', 9:'change', 10:'limit'}
        k = sort_key_map.get(self.sort_col, 'volume')
        for g in [act_list, bl_list, spread_list, low_vol_list, min_high_list, limit_high_list, mkt_list]:
            g.sort(key=lambda x: x.get(k, 0) if k!='symbol' else str(x.get(k)).lower(), reverse=self.sort_desc)

        self.table.setUpdatesEnabled(False)
        self.table.clearSpans()
        # setRowCount(0) нь хуучин CellWidget (Header товчлуур) болон нэгтгэсэн мөрүүдийг бүрэн цэвэрлэнэ
        self.table.setRowCount(0) 
        
        # Бодит шаардлагатай мөрийн тоог тооцоолох
        total_rows = len(act_list) + len(bl_list) + len(spread_list) + len(low_vol_list) + len(min_high_list) + len(limit_high_list) + len(mkt_list)
        if act_list: total_rows += 1
        if bl_list: total_rows += 1
        if spread_list: total_rows += 1
        if low_vol_list: total_rows += 1
        if min_high_list: total_rows += 1
        if limit_high_list: total_rows += 1
        if mkt_list: total_rows += 1
        total_rows += 1 # For the new totals row
        self.table.setRowCount(total_rows)
        
        curr = 0
        def add_head(title, count, bg):
            nonlocal curr
            if count == 0: return # Дата байхгүй бол гарчиг нэмэхгүй
            btn = QPushButton(f"  {title} ({count})")
            btn.setEnabled(False)
            btn.setStyleSheet(f"background: {bg}; color: white; text-align: left; font-weight: bold; border: none; height: 30px; border-radius: 0px;")
            self.table.setCellWidget(curr, 0, btn)
            self.table.setSpan(curr, 0, 1, 11)
            curr += 1

        if act_list:
            add_head("★ ACTIVE", len(act_list), "#1e40af")
            for d in act_list: self.render_row(curr, d, "#1e3a8a"); curr += 1
        
        if bl_list:
            add_head("🚫 BLACKLISTED / ST RISK", len(bl_list), "#7f1d1d")
            for d in bl_list: self.render_row(curr, d, "#450a0a"); curr += 1
            
        if spread_list:
            add_head("⚠️ HIGH SPREAD (>1.0%)", len(spread_list), "#92400e")
            for d in spread_list: self.render_row(curr, d, "#451a03"); curr += 1

        if low_vol_list:
            add_head("📉 VOLUME LOW (<50K)", len(low_vol_list), "#4c1d95")
            for d in low_vol_list: self.render_row(curr, d, "#2e1065"); curr += 1

        if min_high_list:
            add_head("⚖️ MINIMUM HIGH (>0.11)", len(min_high_list), "#334155")
            for d in min_high_list: self.render_row(curr, d, None); curr += 1

        if limit_high_list:
            add_head("🚧 LIMIT HIGH (>0.1)", len(limit_high_list), "#4b5563")
            for d in limit_high_list: self.render_row(curr, d, "#1f2937"); curr += 1

        if mkt_list:
            add_head("📊 MARKET LIST", len(mkt_list), "#334155")
            for d in mkt_list: self.render_row(curr, d, None); curr += 1

        # Хамгийн доод талд нийлбэр мөрийг нэмэх
        # "TOTALS" шошго
        total_label_item = QTableWidgetItem("TOTALS")
        total_label_item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        total_label_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        total_label_item.setBackground(QColor("#1e293b"))
        total_label_item.setForeground(QColor("#cbd5e1"))
        self.table.setItem(curr, 1, total_label_item)
        self.table.setSpan(curr, 0, 1, 2) # Эхний 2 баганыг нэгтгэж "TOTALS" харуулна

        # Real% нийлбэр
        total_real_item = NumericTableWidgetItem(f"{total_real_change:+.2f}%")
        total_real_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        total_real_item.setBackground(QColor("#1e293b"))
        total_real_item.setForeground(QColor("#fbbf24" if total_real_change >= 0 else "#f87171"))
        self.table.setItem(curr, 7, total_real_item)

        # 1h% нийлбэр
        total_h1_item = NumericTableWidgetItem(f"{total_h1_change:+.2f}%")
        total_h1_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        total_h1_item.setBackground(QColor("#1e293b"))
        total_h1_item.setForeground(QColor("#38bdf8" if total_h1_change >= 0 else "#fb7185"))
        self.table.setItem(curr, 8, total_h1_item)

        # 24% нийлбэр
        total_24h_item = NumericTableWidgetItem(f"{total_24h_change:+.2f}%")
        total_24h_item.setFont(QFont("Arial", 10, QFont.Weight.Bold))
        total_24h_item.setBackground(QColor("#1e293b"))
        total_24h_item.setForeground(QColor("#22c55e" if total_24h_change > 0 else "#ef4444"))
        self.table.setItem(curr, 9, total_24h_item)
        
        # Бусад хоосон нүднүүдийг ижил фонтой болгох
        for col_idx in range(self.table.columnCount()):
            if self.table.item(curr, col_idx) is None:
                empty_item = QTableWidgetItem("")
                empty_item.setBackground(QColor("#1e293b"))
                self.table.setItem(curr, col_idx, empty_item)

        self.table.setUpdatesEnabled(True)
        self.update_api_metrics() # Сүүлд нь метрикийг шинэчлэнэ
        self.data_updated.emit(strategy_mkt_list) # Зөвхөн "Market List" зооснуудыг илгээнэ

    def render_row(self, row, d, bg_color):
        sym = d['symbol']
        idx = NumericTableWidgetItem(str(d['index'] + 1))
        idx.setData(Qt.ItemDataRole.EditRole, d['index'] + 1)
        if bg_color: idx.setBackground(QColor(bg_color))
        self.table.setItem(row, 0, idx)
        
        name = sym.split('/')[0]
        if d['is_st']: name += " [ST]"
        c_item = QTableWidgetItem(name)
        if d['is_st']: c_item.setForeground(QColor("#f87171"))
        self.table.setItem(row, 1, c_item)

        self.table.setItem(row, 2, NumericTableWidgetItem(f"{d['live_bid']:.6f}"))
        self.table.setItem(row, 3, NumericTableWidgetItem(f"{d['live_ask']:.6f}"))
        
        spr = d['live_spread']
        s_item = NumericTableWidgetItem(f"{spr:.2f}%")
        if spr > 1.0: s_item.setForeground(QColor("#fbbf24"))
        self.table.setItem(row, 4, s_item)

        m_item = NumericTableWidgetItem(f"{d['val_usd']:.4f}")
        if d.get('val_usd', 0) <= 0.11:
            m_item.setForeground(QColor("#10b981")) # 0.11-ээс бага бол Ногоон
        else:
            m_item.setForeground(QColor("#ffffff")) # 0.11-ээс их бол Цагаан
        self.table.setItem(row, 5, m_item)

        v = d['volume']
        self.table.setItem(row, 6, NumericTableWidgetItem(f"{v/1e6:.1f}M" if v>=1e6 else f"{v/1e3:.1f}K"))
        
        r_val = d.get('real_change', 0)
        r_item = NumericTableWidgetItem(f"{r_val:+.2f}%")
        r_item.setForeground(QColor("#fbbf24" if r_val >= 0 else "#f87171"))
        self.table.setItem(row, 7, r_item)

        h = d['h1_change']
        h_item = NumericTableWidgetItem(f"{h:+.2f}%")
        h_item.setForeground(QColor("#38bdf8" if h>=0 else "#fb7185"))
        self.table.setItem(row, 8, h_item)

        c = d['change']
        ch_item = QTableWidgetItem(f"{c:+.2f}%")
        ch_item.setForeground(QColor("#22c55e" if c>0 else "#ef4444"))
        self.table.setItem(row, 9, ch_item)
        
        self.table.setItem(row, 10, NumericTableWidgetItem(str(d['limit'])))

    def closeEvent(self, event):
        if self.ws_thread:
            self.ws_worker.stop()
            self.ws_thread.quit()
            self.ws_thread.wait()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = SpotMarketPanel()
    window.resize(1100, 800)
    window.show()
    sys.exit(app.exec())