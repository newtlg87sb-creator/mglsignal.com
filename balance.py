import sys
import threading
import ccxt
import os
import json
from PyQt6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, 
                             QLabel, QTableWidget, QTableWidgetItem, QHeaderView, 
                             QPushButton, QMenu, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal, QTimer, QMetaObject, pyqtSlot
from PyQt6.QtGui import QAction, QColor
import time

# Тоон утгаар эрэмбэлэлт хийхэд зориулсан класс (Бусад файлаас хамааралгүй байх үүднээс энд тодорхойлов)
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

class KucoinBalanceApp(QWidget):
    balance_fetched = pyqtSignal(dict)
    error_occurred = pyqtSignal(str)
    asset_selected = pyqtSignal(str) # Зоос сонгогдох үед илгээх сигнал

    def __init__(self, main_dashboard=None):
        super().__init__()
        self.main_dashboard = main_dashboard
        self.setWindowTitle("KuCoin Manager - Advanced Table")
        self.resize(800, 400)
        self.setStyleSheet("background-color: #0f172a; color: white;")
        
        self.is_fetching = False
        self.creds = {
            'apiKey': os.environ.get('KUCOIN_API_KEY'),
            'secret': os.environ.get('KUCOIN_SECRET'),
            'password': os.environ.get('KUCOIN_PASSWORD'),
            'enableRateLimit': True,
            'options': {'adjustForTimeDifference': True},
        }
        self.init_ui()
        self.balance_fetched.connect(self.display_balance)
        self.error_occurred.connect(self.handle_error)

        self.timer = QTimer()
        self.timer.timeout.connect(self.start_fetch)
        self.timer.start(10000) 

        # New: Timer for automatic small exceed balance transfers
        self.auto_transfer_timer = QTimer(self)
        self.auto_transfer_timer.timeout.connect(self._auto_transfer_exceed_balances)
        
        QTimer.singleShot(100, self.start_fetch)

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        top_bar = QHBoxLayout()
        top_bar.setContentsMargins(5, 2, 5, 2)
        top_bar.setSpacing(8)

        self.menu_btn = QPushButton("≡")
        self.menu_btn.setFixedSize(30, 24)
        self.menu_btn.setStyleSheet("""
            QPushButton { 
                font-size: 18px; background-color: #1e293b; border: 1px solid #334155; border-radius: 4px; color: #38bdf8; 
            }
            QPushButton::menu-indicator { image: none; }
            QPushButton:hover { background-color: #334155; }
        """)
        
        self.main_menu = QMenu(self)
        self.main_menu.setStyleSheet("""
            QMenu { background-color: #1e293b; color: white; border: 1px solid #38bdf8; }
            QMenu::item { padding: 10px 20px; }
            QMenu::item:selected { background-color: #38bdf8; color: black; }
        """)
        
        to_funding_action = QAction("All Trading ➔ Funding", self)
        to_trading_action = QAction("All Funding ➔ Trading", self)
        all_exceed_action = QAction("All Exceed ➔ Funding", self)
        to_funding_action.triggered.connect(lambda: self.start_transfer('trade', 'funding'))
        to_trading_action.triggered.connect(lambda: self.start_transfer('funding', 'trade'))
        all_exceed_action.triggered.connect(self.start_all_exceed_transfer)
        
        self.main_menu.addAction(to_funding_action)
        self.main_menu.addAction(to_trading_action)
        self.main_menu.addAction(all_exceed_action)
        self.main_menu.addSeparator()
        
        sell_all_action = QAction("Sell All Trading Assets (Market)", self)
        sell_all_action.triggered.connect(self.confirm_sell_all)
        self.main_menu.addAction(sell_all_action)
        self.menu_btn.setMenu(self.main_menu)
        
        self.status_label = QLabel("Initializing...")
        self.status_label.setFixedHeight(24)
        self.status_label.setStyleSheet("color: #38bdf8; font-weight: bold; font-size: 11px; margin-left: 2px;")
        
        # Copy History Button
        self.copy_btn = QPushButton("📋 Copy Balance")
        self.copy_btn.setFixedSize(110, 24)
        self.copy_btn.setStyleSheet("""
            QPushButton { background-color: #334155; color: white; font-size: 10px; border-radius: 4px; }
            QPushButton:hover { background-color: #475569; }
        """)
        self.copy_btn.clicked.connect(self.copy_balance_to_clipboard)
        
        top_bar.addWidget(self.menu_btn)
        top_bar.addWidget(self.status_label)
        top_bar.addStretch()

        # Total Label-ийг дээд мөрөнд (Top Bar) багтааж зай хэмнэх
        self.total_lbl = QLabel("Total: $0.00")
        self.total_lbl.setFixedHeight(24)
        self.total_lbl.setStyleSheet("font-size: 11px; font-weight: bold; color: #10b981; margin-right: 5px;")
        top_bar.addWidget(self.total_lbl)
        top_bar.addWidget(self.copy_btn)
        
        layout.addLayout(top_bar)

        # БАГАНА ӨӨРЧЛӨЛТ: Asset, Trading, Exceed, Funding, Total (USDT)
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Asset", "Trading", "Exceed", "Funding", "Total (USDT)"])
        
        # Багануудын хэмжээг тогтворжуулах
        header = self.table.horizontalHeader()
        # Бүх багануудыг цонхны өргөнд тэнцүү сунгаж хуваах
        header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        # Asset баганад арай илүү зай өгөх (заавал биш бол устгаж болно)
        header.setStretchLastSection(True)

        self.table.itemClicked.connect(self.handle_item_click) # Дарахад ажиллах
        self.table.verticalHeader().setVisible(False)
        self.table.setShowGrid(False)
        self.table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff) # Гүйлгэх зурвасыг хаах
        self.table.setStyleSheet("""
            QTableWidget { background-color: #0f172a; border: none; gridline-color: #1e293b; }
            QTableWidget { background-color: #0f172a; border: none; gridline-color: #1e293b; }
            QHeaderView::section { background-color: #1e293b; color: #94a3b8; border: none; padding: 5px; }
        """)
        self.table.setMinimumHeight(120) # Доод хэмжээг багасгаж Лог хэсэгт зай гаргав
        layout.addWidget(self.table)

        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.setSortingEnabled(True) # Эрэмбэлэлтийг идэвхжүүлэх

    def handle_item_click(self, item):
        asset = self.table.item(item.row(), 0).text()
        if asset != 'USDT':
            # Сонгогдсон зоосыг Dashboard руу дамжуулах
            self.asset_selected.emit(f"{asset}/USDT")

    def copy_balance_to_clipboard(self):
        """Балансын хүснэгтийн мэдээллийг clipboard руу хуулах"""
        table = self.table
        rows = table.rowCount()
        cols = table.columnCount()
        text_lines = []
        
        # Header-ийг хуулах
        headers = [table.horizontalHeaderItem(i).text() for i in range(cols)]
        text_lines.append("\t".join(headers))
        
        for r in range(rows):
            row_data = [table.item(r, c).text() if table.item(r, c) else "" for c in range(cols)]
            text_lines.append("\t".join(row_data))
            
        QApplication.clipboard().setText("\n".join(text_lines))
        # Log-д бичихдээ main_dashboard-ийн log_signal-ийг ашиглана
        if hasattr(self, 'main_dashboard') and hasattr(self.main_dashboard, 'log_signal'):
            self.main_dashboard.log_signal.emit("📋 Balance copied to clipboard!")

    @pyqtSlot()
    def start_fetch(self):
        if self.is_fetching: return
        self.is_fetching = True
        self.status_label.setText("🔄 Syncing...")
        threading.Thread(target=self.run_worker, daemon=True).start()

    def show_context_menu(self, pos):
        index = self.table.indexAt(pos)
        if not index.isValid() or index.column() != 2: # Зөвхөн Exceed багана
            return

        row = index.row()
        asset = self.table.item(row, 0).text()
        try:
            exceed_val = float(self.table.item(row, 2).data(Qt.ItemDataRole.EditRole))
        except: return
        
        amount = abs(exceed_val)
        if amount < 1e-8: return

        menu = QMenu(self)
        menu.setStyleSheet("QMenu { background-color: #1e293b; color: white; border: 1px solid #38bdf8; } QMenu::item:selected { background-color: #38bdf8; color: black; }")
        
        move_to_funding = QAction(f"Move {amount:.4f} {asset} to Funding", self)
        move_to_trading = QAction(f"Move {amount:.4f} {asset} to Trading", self)
        
        move_to_funding.triggered.connect(lambda: self.execute_single_transfer(asset, amount, 'trade', 'main'))
        move_to_trading.triggered.connect(lambda: self.execute_single_transfer(asset, amount, 'main', 'trade'))
        
        menu.addAction(move_to_funding)
        menu.addAction(move_to_trading)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def execute_single_transfer(self, asset, amount, from_acc, to_acc):
        self.status_label.setText(f"⏳ Moving {asset}...")
        threading.Thread(target=self._transfer_worker, args=(asset, amount, from_acc, to_acc), daemon=True).start()

    def _transfer_worker(self, asset, amount, from_acc, to_acc):
        try:
            ex = ccxt.kucoin(self.creds)
            ex.transfer(asset, amount, from_acc, to_acc)
            QMetaObject.invokeMethod(self, 'start_fetch', Qt.ConnectionType.QueuedConnection)
        except Exception as e:
            self.error_occurred.emit(f"Transfer Error: {e}")

    def run_worker(self):
        try:
            ex = ccxt.kucoin(self.creds)
            trade_bal = ex.fetch_balance({'type': 'spot'})
            funding_bal = ex.fetch_balance({'type': 'funding'})
            tickers = ex.fetch_tickers()
            self.balance_fetched.emit({
                'trade': trade_bal.get('total', {}), 
                'funding': funding_bal.get('total', {}), 
                'tickers': tickers
            })
        except Exception as e:
            self.error_occurred.emit(str(e))
            # Store last fetched data even on error for potential reuse
            self.last_fetched_trade_balance = {}
            self.last_fetched_tickers = {}
        finally:
            self.is_fetching = False

    def display_balance(self, data):
        self.table.setSortingEnabled(False)
        
        trade, funding, tickers = data['trade'], data['funding'], data['tickers']
        all_assets = sorted(set(trade.keys()) | set(funding.keys()))
        
        # Filter assets with significant balance
        visible_assets = []
        for asset in all_assets:
            if (float(trade.get(asset, 0) or 0) + float(funding.get(asset, 0) or 0)) > 0.000001:
                visible_assets.append(asset)

        if self.table.rowCount() != len(visible_assets):
            self.table.setRowCount(len(visible_assets))
        
        # Store these for potential reuse by auto_transfer_exceed_balances
        self.last_fetched_trade_balance = trade
        self.last_fetched_tickers = tickers
        total_portfolio_usdt = 0
        
        tracked_holdings = {}
        # Оновчлол: auto.json-ийг уншихын оронд Dashboard-ийн санах ой дахь active_symbols-ийг ашиглах
        active_symbols = getattr(self.main_dashboard, 'active_symbols', {})
        for sym, amt in active_symbols.items():
            if "/" in sym:
                asset_name = sym.split('/')[0]
                tracked_holdings[asset_name] = tracked_holdings.get(asset_name, 0) + amt

        def get_or_create(r, c, is_numeric=True):
            item = self.table.item(r, c)
            if not item:
                item = NumericTableWidgetItem("") if is_numeric else QTableWidgetItem("")
                self.table.setItem(r, c, item)
            return item

        for row, asset in enumerate(visible_assets):
            t_amt = float(trade.get(asset, 0) or 0)
            f_amt = float(funding.get(asset, 0) or 0)
            total_qty = t_amt + f_amt
            
            if True: # Already filtered
                price = 1.0 if asset == 'USDT' else float(tickers.get(f"{asset}/USDT", {}).get('last', 0))
                asset_total_usdt = total_qty * price
                total_portfolio_usdt += asset_total_usdt
                
                # Exceed тооцоолох: Trading дээрх баланс - Auto trade-д ашиглагдаж буй хэмжээ
                # Хэрэв Trading balance нь Auto-оос их байвал "Илүүдэл" (Green), бага байвал "Дутуу" (Red)
                if asset == 'USDT':
                    exceed = 0
                else:
                    exceed = round(t_amt - tracked_holdings.get(asset, 0), 8)
                
                exceed_color = "#10b981" if exceed > 0.000001 else "#ef4444" if exceed < -0.000001 else "#94a3b8"
                
                # 0. Asset Name
                get_or_create(row, 0, False).setText(asset)
                
                # 1. Trading Amount
                t_item = get_or_create(row, 1)
                t_item.setText(f"{t_amt:.4f}")
                t_item.setData(Qt.ItemDataRole.EditRole, t_amt)
                
                # Trading balance нь Auto-ийн нээлттэй хэмжээтэй яг таарч байвал ногоон болгох
                current_auto_amt = tracked_holdings.get(asset, 0)
                is_match = False
                if current_auto_amt > 0:
                    diff = abs(t_amt - current_auto_amt)
                    if diff < 1e-6 or (diff / current_auto_amt) < 0.005:
                        is_match = True
                if asset != 'USDT' and is_match:
                    t_item.setForeground(QColor("#10b981")) # Green
                else:
                    t_item.setForeground(QColor("white"))
                
                # 2. Exceed (Зөрүү)
                display_exceed = exceed if abs(exceed) > 1e-7 else 0.0
                ex_item = get_or_create(row, 2)
                ex_item.setText(f"{display_exceed:.4f}")
                ex_item.setForeground(QColor(exceed_color))
                ex_item.setData(Qt.ItemDataRole.EditRole, exceed)
                
                # 3. Funding Amount
                f_item = get_or_create(row, 3)
                f_item.setText(f"{f_amt:.4f}")
                f_item.setData(Qt.ItemDataRole.EditRole, f_amt)
                
                # 4. Total (USDT)
                total_item = get_or_create(row, 4)
                total_item.setText(f"${asset_total_usdt:,.2f}")
                total_item.setForeground(QColor("#38bdf8"))
                total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                total_item.setData(Qt.ItemDataRole.EditRole, asset_total_usdt)

        # Өгөгдөл орж дууссаны дараа эрэмбэлэлтийг буцааж идэвхжүүлэх
        self.table.setSortingEnabled(True)
        self.total_lbl.setText(f"Total: ${total_portfolio_usdt:,.2f}")
        self.status_label.setText(f"✅ Live")

    @pyqtSlot()
    def _auto_transfer_exceed_balances(self):
        """
        5 минут тутамд 0.01 USDT-ээс бага илүүдэл балансыг Trading-ээс Funding руу шилжүүлэх.
        """
        # Auto Trade идэвхтэй үед л ажиллуулах
        if not hasattr(self.main_dashboard, 'auto_panel') or not self.main_dashboard.auto_panel.is_running:
            return

        self.main_dashboard.log_signal.emit("🔍 Жижиг илүүдэл балансуудыг шалгаж байна (0.01 USDT-ээс бага)...")
        
        try:
            # Хамгийн сүүлд татсан баланс болон тикер мэдээллийг ашиглах
            # (start_fetch нь 10 секунд тутамд ажилладаг тул энэ нь хангалттай шинэ байх ёстой)
            trade_bal = self.last_fetched_trade_balance
            tickers = self.last_fetched_tickers

            if not trade_bal or not tickers:
                self.main_dashboard.log_signal.emit("⚠️ Баланс эсвэл тикер мэдээлэл олдсонгүй. Шилжүүлэг хийх боломжгүй.")
                return

            trading_totals = trade_bal
            
            # Нээлттэй арилжаануудын нийт хэмжээг тооцоолох (Required amount)
            tracked_holdings = {}
            lock = getattr(self.main_dashboard, 'file_lock', threading.Lock())
            with lock:
                for filename in ["auto.json"]:
                    if os.path.exists(filename):
                        try:
                            with open(filename, "r") as f:
                                history = json.load(f)
                            for entry in history:
                                status = str(entry.get('status', '')).upper()
                                side = str(entry.get('side', '')).upper()
                                if status != "CLOSED" and side == "BUY":
                                    asset_name = entry.get('symbol', '').split('/')[0]
                                    tracked_holdings[asset_name] = tracked_holdings.get(asset_name, 0) + float(entry.get('amount', 0))
                        except: pass

            transferred_count = 0
            for asset, t_amt in trading_totals.items():
                if asset == 'USDT' or t_amt <= 0: continue

                required = tracked_holdings.get(asset, 0)
                exceed = t_amt - required

                if exceed > 0: # Зөвхөн эерэг илүүдлийг шалгана
                    price = float(tickers.get(f"{asset}/USDT", {}).get('last', 0) or 0)
                    exceed_usdt = exceed * price

                    if 0 < exceed_usdt < 0.01: # 0.01 USDT-ээс бага илүүдлийг шилжүүлнэ
                        self.main_dashboard.log_signal.emit(f"💸 Автоматаар шилжүүлж байна: {exceed:.8f} {asset} ({exceed_usdt:.4f} USDT) -> Funding.")
                        threading.Thread(target=self.execute_single_transfer, args=(asset, exceed, 'trade', 'main'), daemon=True).start()
                        transferred_count += 1
                        time.sleep(0.5) # Rate limit-ээс сэргийлэх

            if transferred_count == 0:
                self.main_dashboard.log_signal.emit("ℹ️ Автоматаар шилжүүлэх жижиг илүүдэл баланс олдсонгүй.")

        except Exception as e:
            self.main_dashboard.log_signal.emit(f"❌ Жижиг илүүдэл баланс шилжүүлэхэд алдаа гарлаа: {e}")

    def start_all_exceed_transfer(self):
        reply = QMessageBox.question(self, 'Confirm Transfer', 
                                    "Бүх илүүдэл (Exceed) балансыг Funding руу шилжүүлэх үү?", 
                                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.status_label.setText("⏳ Шилжүүлэг эхэллээ...")
            threading.Thread(target=self._all_exceed_transfer_worker, daemon=True).start()

    def _all_exceed_transfer_worker(self):
        try:
            ex = ccxt.kucoin(self.creds)
            trade_bal = ex.fetch_balance({'type': 'spot'})
            trading_totals = trade_bal.get('total', {})
            
            tracked_holdings = {}
            lock = getattr(self.main_dashboard, 'file_lock', threading.Lock())
            with lock:
                if os.path.exists("auto.json"):
                    try:
                        with open("auto.json", "r") as f:
                            history = json.load(f)
                        for entry in history:
                            status = str(entry.get('status', '')).upper()
                            side = str(entry.get('side', '')).upper()
                            if status != "CLOSED" and side == "BUY":
                                asset_name = entry.get('symbol', '').split('/')[0]
                                tracked_holdings[asset_name] = tracked_holdings.get(asset_name, 0) + float(entry.get('amount', 0))
                    except: pass

            count = 0
            for asset, t_amt in trading_totals.items():
                if asset == 'USDT' or t_amt <= 0: continue
                required = tracked_holdings.get(asset, 0)
                exceed = t_amt - required
                if exceed > 1e-8:
                    try:
                        ex.transfer(asset, exceed, 'trade', 'main')
                        count += 1
                        time.sleep(0.3)
                    except: continue
            
            self.error_occurred.emit(f"✅ {count} илүүдэл балансыг шилжүүлж дууслаа.")
            QMetaObject.invokeMethod(self, 'start_fetch', Qt.ConnectionType.QueuedConnection)
        except Exception as e:
            self.error_occurred.emit(f"Error: {e}")

    # [Бусад функцууд хэвээрээ: start_transfer, execute_transfer, execute_sell_all, handle_error]
    def start_transfer(self, from_type, to_type):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Шилжүүлэг")
        msg_box.setText(f"Бүх балансыг {from_type} -> {to_type} руу шилжүүлэх үү?")
        msg_box.setInformativeText("USDT-ийг хамт шилжүүлэх үү?")
        msg_box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel)
        msg_box.button(QMessageBox.StandardButton.Yes).setText("USDT-тэй хамт")
        msg_box.button(QMessageBox.StandardButton.No).setText("USDT-гүйгээр")
        msg_box.button(QMessageBox.StandardButton.Cancel).setText("Болих")
        ret = msg_box.exec()
        if ret == QMessageBox.StandardButton.Cancel: return
        include_usdt = (ret == QMessageBox.StandardButton.Yes)
        self.status_label.setText("⏳ Шилжүүлэг эхэллээ...")
        threading.Thread(target=self.execute_transfer, args=(from_type, to_type, include_usdt), daemon=True).start()

    def execute_transfer(self, from_type, to_type, include_usdt):
        try:
            ex = ccxt.kucoin(self.creds)
            target_account = 'spot' if from_type == 'trade' else 'funding'
            balance = ex.fetch_balance({'type': target_account})
            total_bal = balance.get('total', {})
            assets_to_move = {a: v for a, v in total_bal.items() if v > 0 and (include_usdt or a != 'USDT')}
            if not assets_to_move:
                self.error_occurred.emit("Шилжүүлэх зоос олдсонгүй!")
                return
            count = 0
            from_acc = 'trade' if from_type == 'trade' else 'main'
            to_acc = 'main' if to_type == 'funding' else 'trade'
            for asset, amount in assets_to_move.items():
                try:
                    ex.transfer(asset, amount, from_acc, to_acc)
                    count += 1
                    time.sleep(0.3)
                except: continue
            self.error_occurred.emit(f"✅ Нийт {count} зоосыг зөөж дууслаа.")
            QMetaObject.invokeMethod(self, 'start_fetch', Qt.ConnectionType.QueuedConnection)
        except Exception as e: self.error_occurred.emit(f"Error: {e}")

    def confirm_sell_all(self):
        reply = QMessageBox.question(self, 'Confirm Sell', "Trading дээрх бүх зоосыг зарах уу?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            threading.Thread(target=self.execute_sell_all, daemon=True).start()

    def execute_sell_all(self):
        try:
            ex = ccxt.kucoin(self.creds)
            balance = ex.fetch_balance({'type': 'spot'})
            assets_to_sell = {a: v for a, v in balance.get('total', {}).items() if v > 0 and a != 'USDT'}
            count = 0
            for asset, amount in assets_to_sell.items():
                try:
                    ex.create_market_sell_order(f"{asset}/USDT", amount)
                    count += 1
                    time.sleep(0.2)
                except: continue
            self.error_occurred.emit(f"✅ {count} зоосыг зарлаа.")
            QMetaObject.invokeMethod(self, 'start_fetch', Qt.ConnectionType.QueuedConnection)
        except Exception as e: self.error_occurred.emit(f"Error: {e}")

    def handle_error(self, msg):
        self.status_label.setText(f"⚠️ {msg}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = KucoinBalanceApp()
    window.show()
    sys.exit(app.exec())