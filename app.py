import math
import time
from flask import Flask, request, jsonify
from binance.um_futures import UMFutures
from threading import Lock

app = Flask(__name__)

# 🚨 DİREKT GÖMÜLÜ API ANAHTARI (GÜVENLİK RİSKİ VAR)
BINANCE_API_KEY = "1NK6KpwVAvrujTmmqi5svQoWeIWJcui8DsvrfDufG6tUfxRBpimJbVzfvMH77y7K"
BINANCE_API_SECRET = "VzU4O81to2lNcOYXwi8yloB8ZpDCeY6Qm02DAEGGniEXs82E78MOyX6jeXR3Pzda"

client = UMFutures(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

exchange_info_cache = {}
exchange_info_lock = Lock()
last_request_time = 0
request_lock = Lock()
last_trade = {"symbol": None, "side": None, "timestamp": 0}

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
    positions = client.position_information(symbol=symbol)
    for p in positions:
        if float(p['positionAmt']) != 0.0:
            return p
    return None

@app.route("/")
def index():
    return "Binance Perpetual Bot AKTİF ✅"

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_request_time, last_trade
    try:
        with request_lock:
            now = time.time()
            if now - last_request_time < 1:
                return jsonify({"message": "Rate limit", "status": "rate_limited"}), 429
            last_request_time = now

        data = request.json
        symbol = data.get("ticker", "").replace(".P", "")
        side = data.get("side", "").upper()
        usdt_amount_raw = data.get("usdt_amount")

        if symbol == "" or side not in ["BUY", "SELL"] or usdt_amount_raw is None:
            return jsonify({"message": "Eksik parametre", "status": "error"}), 400

        now = time.time()
        if last_trade["symbol"] == symbol and last_trade["side"] == side and now - last_trade["timestamp"] < 10:
            return jsonify({"message": "Tekrar emir engellendi", "status": "duplicate"}), 200
        last_trade.update({"symbol": symbol, "side": side, "timestamp": now})

        client.change_margin_type(symbol=symbol, marginType="ISOLATED")
        client.change_leverage(symbol=symbol, leverage=1)

        with exchange_info_lock:
            if symbol not in exchange_info_cache:
                exchange_info_cache[symbol] = client.exchange_info(symbol=symbol)
        filters = exchange_info_cache[symbol]["symbols"][0]["filters"]
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
                return jsonify({"message": "Maksimum 500 USDT", "status": "error"}), 400
            if notional > usdt_balance:
                return jsonify({"message": "Yetersiz bakiye", "status": "error"}), 400

        quantity = round_step_size(notional / price, step_size)
        if quantity < min_qty:
            return jsonify({"message": "Minimum emir boyutunun altında", "status": "error"}), 400

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

        print(f"[EMİR] {side} {symbol} | {quantity} adet | {notional} USDT")
        return jsonify({
            "message": f"{side} emri gönderildi",
            "quantity": quantity,
            "notional": notional,
            "order": order,
            "status": "success"
        })

    except Exception as e:
        print(f"[HATA] {str(e)}")
        return jsonify({"message": str(e), "status": "error"}), 500
