# This Pine Script™ code is subject to the terms of the Mozilla Public License 2.0 at https://mozilla.org/MPL/2.0/
# © algostudio
# Code Generated using PineGPT - www.marketcalls.in

from flask import Flask, request, jsonify
from binance.um_futures import UMFutures
from threading import Lock
import os
import math
import time

app = Flask(__name__)

# Binance API Anahtarları (Render Environment Variables'tan alınır)
API_KEY = os.environ.get("BINANCE_API_KEY")
API_SECRET = os.environ.get("BINANCE_API_SECRET")

# 🔄 Binance bağlantısı
client = UMFutures(API_KEY, API_SECRET)

# Cache ve thread güvenliği
exchange_info_cache = {}
exchange_info_lock = Lock()
request_lock = Lock()
last_request_time = 0

# Miktar ayarlayıcı
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
def home():
    return "Binance Perpetual Bot AKTİF ✅"

@app.route("/webhook", methods=["POST"])
def webhook():
    global last_request_time
    try:
        with request_lock:
            now = time.time()
            if now - last_request_time < 1:
                return jsonify({"message": "Çok sık istek", "status": "rate_limited"}), 429
            last_request_time = now

        data = request.json
        symbol = data.get("ticker", "").replace(".P", "")
        side = data.get("side", "").upper()
        usdt_amount_raw = data.get("usdt_amount")

        if symbol == "" or side not in ["BUY", "SELL"] or usdt_amount_raw is None:
            return jsonify({"message": "Hatalı parametre", "status": "error"}), 400

        client.change_margin_type(symbol=symbol, marginType="ISOLATED")
        client.change_leverage(symbol=symbol, leverage=1)

        with exchange_info_lock:
            if symbol not in exchange_info_cache:
                info = client.exchange_info()
                exchange_info_cache[symbol] = next(
                    s for s in info["symbols"] if s["symbol"] == symbol
                )

        filters = exchange_info_cache[symbol]["filters"]
        lot_size = next(f for f in filters if f["filterType"] == "LOT_SIZE")
        step_size = float(lot_size["stepSize"])
        min_qty = float(lot_size["minQty"])

        price = float(client.ticker_price(symbol=symbol)["price"])
        usdt_balance = get_balance("USDT")

        if usdt_amount_raw == "ALL":
            notional = max(35, min(500, usdt_balance * 0.08))
        else:
            notional = float(usdt_amount_raw)
            if notional > usdt_balance:
                return jsonify({"message": "Yetersiz bakiye", "status": "error"}), 400
            if notional > 500:
                return jsonify({"message": "Maksimum limit 500 USDT", "status": "error"}), 400

        quantity = round_step_size(notional / price, step_size)
        if quantity < min_qty:
            return jsonify({"message": "Minimum miktarın altında", "status": "error"}), 400

        # Var olan pozisyonu kapat
        current = get_position(symbol)
        if current:
            amt = float(current["positionAmt"])
            current_side = "BUY" if amt > 0 else "SELL"
            if current_side != side:
                client.new_order(
                    symbol=symbol,
                    side="SELL" if amt > 0 else "BUY",
                    type="MARKET",
                    quantity=abs(amt),
                    reduceOnly=True
                )
                time.sleep(1)

        # Yeni pozisyon
        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )

        return jsonify({
            "message": f"{side} emri gönderildi",
            "quantity": quantity,
            "order": order,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500
