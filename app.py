import os
import math
import time
from flask import Flask, request, jsonify
from binance.spot import Spot as Client
from threading import Lock

app = Flask(__name__)

# Binance API bağlantısı
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")
client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

# Exchange info cache
exchange_info_cache = {}
exchange_info_lock = Lock()

# Sinyal başına rate limit (örnek: saniyede 1)
last_request_time = 0
request_lock = Lock()

# LOT_SIZE'a uygun miktarı yuvarlama fonksiyonu
def round_step(qty, step):
    precision = int(round(-math.log10(step)))
    return round(qty - (qty % step), precision)

@app.route('/')
def index():
    return "Bot çalışıyor"

@app.route('/balance')
def balance_all():
    account_info = client.account()
    balances = {
        asset['asset']: float(asset['free'])
        for asset in account_info['balances']
        if float(asset['free']) > 0
    }
    return jsonify({"balances": balances, "status": "success"})

@app.route('/balance/<symbol>')
def balance_one(symbol):
    balance = client.get_asset_balance(asset=symbol.upper())
    return jsonify({
        "asset": symbol.upper(),
        "balance": float(balance['free']),
        "status": "success"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    global last_request_time

    try:
        # Rate Limiting (1 istek / saniye)
        with request_lock:
            now = time.time()
            if now - last_request_time < 1:
                return jsonify({"message": "Çok sık istek gönderildi", "status": "rate_limited"}), 429
            last_request_time = now

        data = request.json
        symbol = data.get("ticker")
        side = data.get("side", "").upper()
        usdt_amount_raw = data.get("usdt_amount")

        if symbol is None or side not in ["BUY", "SELL"] or usdt_amount_raw is None:
            return jsonify({"message": "Eksik parametre", "status": "error"}), 400

        base_asset = symbol.replace("USDT", "")

        # exchangeInfo'yu önbellekten al veya çek
        with exchange_info_lock:
            if symbol not in exchange_info_cache:
                exchange_info_cache[symbol] = client.exchange_info(symbol=symbol)

        lot_size_filter = next(
            f for f in exchange_info_cache[symbol]["symbols"][0]["filters"]
            if f["filterType"] == "LOT_SIZE"
        )
        step_size = float(lot_size_filter["stepSize"])

        # Miktar hesaplama
        quantity = 0
        if usdt_amount_raw == "ALL":
            asset = base_asset if side == "SELL" else "USDT"
            balance = float(client.get_asset_balance(asset=asset)["free"])
            if side == "SELL":
                quantity = round_step(balance * 0.995, step_size)
            else:
                price = float(client.ticker_price(symbol=symbol))
                quantity = round_step((balance / price) * 0.995, step_size)
        else:
            usdt_amount = float(usdt_amount_raw)
            price = float(client.ticker_price(symbol=symbol))
            quantity = round_step(usdt_amount / price, step_size)

        if quantity <= 0:
            return jsonify({"message": "İşlem miktarı geçersiz", "status": "error"}), 400

        # Market emri gönder
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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
