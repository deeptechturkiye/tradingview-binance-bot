import os
import time
import math
from flask import Flask, request, jsonify
from binance.um_futures import UMFutures
from threading import Lock

app = Flask(__name__)

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")

client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_API_SECRET)

exchange_info_cache = {}
exchange_info_lock = Lock()
last_request_time = 0
request_lock = Lock()

def round_step_size(quantity, step_size):
    precision = int(round(-math.log10(step_size)))
    return round(quantity - (quantity % step_size), precision)

def get_balance(asset='USDT'):
    balances = client.balance()
    for b in balances:
        if b['asset'] == asset:
            return float(b['balance'])
    return 0.0

def get_position(symbol):
    positions = client.get_position_risk(symbol=symbol)
    for p in positions:
        if float(p['positionAmt']) != 0.0:
            return p
    return None

def get_current_margin_and_leverage(symbol):
    pos = get_position(symbol)
    if pos is None:
        return None, None
    return pos.get('marginType'), int(pos.get('leverage', 0))

@app.route("/")
def index():
    return "Binance Perpetual Bot çalışıyor ✅"

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_request_time
    try:
        if not request.is_json:
            return jsonify({"message": "Content-Type must be application/json", "status": "error"}), 415

        with request_lock:
            now = time.time()
            if now - last_request_time < 1:
                return jsonify({"message": "Çok sık istek", "status": "rate_limited"}), 429
            last_request_time = now

        data = request.get_json()
        symbol = data.get("ticker", "").replace(".P", "")
        side = data.get("side", "").upper()
        usdt_amount_raw = data.get("usdt_amount")

        if not symbol or side not in ["BUY", "SELL"] or usdt_amount_raw is None:
            return jsonify({"message": "Eksik parametre", "status": "error"}), 400

        margin_type, leverage = get_current_margin_and_leverage(symbol)

        if margin_type != "ISOLATED":
            try:
                client.change_margin_type(symbol=symbol, marginType="ISOLATED")
            except Exception:
                pass

        if leverage != 1:
            try:
                client.change_leverage(symbol=symbol, leverage=1)
            except Exception:
                pass

        with exchange_info_lock:
            if not exchange_info_cache:
                exchange_info_cache.update(client.exchange_info())

        symbol_info = next((s for s in exchange_info_cache['symbols'] if s['symbol'] == symbol), None)

        if symbol_info is None:
            return jsonify({"message": "Symbol not found", "status": "error"}), 400

        filters = symbol_info["filters"]
        lot_size = next(f for f in filters if f["filterType"] == "LOT_SIZE")
        step_size = float(lot_size["stepSize"])
        min_qty = float(lot_size["minQty"])

        price = float(client.ticker_price(symbol=symbol)["price"])
        usdt_balance = get_balance("USDT")

        if usdt_amount_raw == "ALL":
            notional = max(35, min(500, usdt_balance * 0.08))
        else:
            notional = float(usdt_amount_raw)
            if notional > 500:
                return jsonify({"message": "Maksimum izin verilen miktar 500 USDT", "status": "error"}), 400
            if notional > usdt_balance:
                return jsonify({"message": "Bakiye yetersiz", "status": "error"}), 400

        quantity = round_step_size(notional / price, step_size)
        if quantity < min_qty:
            return jsonify({"message": "Miktar Binance minimum sınırın altında", "status": "error"}), 400

        current_position = get_position(symbol)
        if current_position:
            pos_amt = float(current_position['positionAmt'])
            pos_side = "BUY" if pos_amt > 0 else "SELL"
            if pos_side != side:
                client.new_order(
                    symbol=symbol,
                    side="SELL" if pos_amt > 0 else "BUY",
                    type="MARKET",
                    quantity=abs(pos_amt),
                    reduceOnly=True
                )
                time.sleep(1)

        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )

        print(f"[ALERT] {side} - {symbol} - {quantity} adet - {notional} USDT")
        print(f"Binance cevabı: {order}")

        return jsonify({
            "message": f"{side} emri gönderildi",
            "quantity": quantity,
            "notional": notional,
            "order": order,
            "status": "success"
        })

    except Exception as e:
        print(f"HATA: {str(e)}")
        return jsonify({"message": str(e), "status": "error"}), 500
