import os
import time
import math
from flask import Flask, request, jsonify
from binance.um_futures import UMFutures
from threading import Lock

app = Flask(__name__)

# Çevresel değişkenlerden API anahtarlarını al
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")

# Binance UM Futures client'ı başlat
client = UMFutures(key=BINANCE_API_KEY, secret=BINANCE_API_SECRET)

exchange_info_cache = {}
exchange_info_lock = Lock()
last_request_time = 0
request_lock = Lock()


# Lot adımı kadar miktarı yuvarlar
def round_step_size(quantity, step_size):
    precision = int(round(-math.log10(step_size)))
    return round(quantity - (quantity % step_size), precision)


# USDT bakiyesini al
def get_balance(asset='USDT'):
    balances = client.balance()
    for b in balances:
        if b['asset'] == asset:
            return float(b['balance'])
    return 0.0


# Açık pozisyonu kontrol et
def get_position(symbol):
    positions = client.get_position_risk(symbol=symbol)
    for p in positions:
        if float(p['positionAmt']) != 0.0:
            return p
    return None


@app.route("/")
def index():
    return "Binance Perpetual Bot çalışıyor ✅"


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

        if not symbol or side not in ["BUY", "SELL"] or usdt_amount_raw is None:
            return jsonify({"message": "Eksik parametre", "status": "error"}), 400

        # Marjin ayarları
        client.change_margin_type(symbol=symbol, marginType="ISOLATED")
        client.change_leverage(symbol=symbol, leverage=1)

        # Borsa bilgilerini cache'le
        with exchange_info_lock:
            if symbol not in exchange_info_cache:
                exchange_info_cache[symbol] = client.exchange_info(symbol=symbol)

        filters = exchange_info_cache[symbol]["symbols"][0]["filters"]
        lot_size = next(f for f in filters if f["filterType"] == "LOT_SIZE")
        step_size = float(lot_size["stepSize"])
        min_qty = float(lot_size["minQty"])

        price = float(client.ticker_price(symbol=symbol)["price"])
        usdt_balance = get_balance("USDT")

        # İşlem büyüklüğü
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

        # Pozisyon varsa kapat
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
                time.sleep(1)  # Pozisyon kapansın

        # Yeni pozisyon aç
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
