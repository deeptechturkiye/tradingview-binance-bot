import os
import math
import time
from flask import Flask, request, jsonify
from binance.spot import Spot as Client
from threading import Lock

app = Flask(__name__)

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")
client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

exchange_info_cache = {}
exchange_info_lock = Lock()
last_request_time = 0
request_lock = Lock()

def get_free_balance(asset):
    account_info = client.account()
    for b in account_info['balances']:
        if b['asset'] == asset:
            return float(b['free'])
    return 0.0

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
    balance = get_free_balance(symbol.upper())
    return jsonify({
        "asset": symbol.upper(),
        "balance": balance,
        "status": "success"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    global last_request_time
    try:
        with request_lock:
            now = time.time()
            if now - last_request_time < 1:
                return jsonify({"message": "Çok sık istek", "status": "rate_limited"}), 429
            last_request_time = now

        data = request.json
        symbol = data.get("ticker")
        side = data.get("side", "").upper()
        usdt_amount_raw = data.get("usdt_amount")

        if symbol is None or side not in ["BUY", "SELL"] or usdt_amount_raw is None:
            return jsonify({"message": "Eksik parametre", "status": "error"}), 400

        base_asset = symbol.replace("USDT", "")

        with exchange_info_lock:
            if symbol not in exchange_info_cache:
                exchange_info_cache[symbol] = client.exchange_info(symbol=symbol)

        filters = exchange_info_cache[symbol]["symbols"][0]["filters"]
        lot_size = next(f for f in filters if f["filterType"] == "LOT_SIZE")
        step_size = float(lot_size["stepSize"])
        min_qty = float(lot_size["minQty"])

        min_notional = next((f for f in filters if f["filterType"] == "MIN_NOTIONAL"), None)
        min_notional_val = float(min_notional["minNotional"]) if min_notional else 10

        quantity = 0
        price = float(client.ticker_price(symbol=symbol)["price"])


        if usdt_amount_raw == "ALL":
            asset = base_asset if side == "SELL" else "USDT"
            balance = get_free_balance(asset)
            if side == "SELL":
                quantity = round_step(balance * 0.995, step_size)
            else:
                quantity = round_step((balance / price) * 0.995, step_size)
        else:
            usdt_amount = float(usdt_amount_raw)
            quantity = round_step(usdt_amount / price, step_size)

        if quantity < min_qty or (price * quantity) < min_notional_val:
            return jsonify({"message": "İşlem miktarı Binance kurallarına uymuyor", "status": "error"}), 400

        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )

        print(f"Webhook verisi: {data}")
        print(f"İşlem: {side} - {symbol} - Miktar: {quantity}")
        print(f"Binance cevabı: {order}")

        return jsonify({
            "message": f"{side} emri gönderildi",
            "quantity": quantity,
            "order": order,
            "status": "success"
        })

    except Exception as e:
        print(f"HATA: {str(e)}")
        return jsonify({"message": str(e), "status": "error"}), 500
