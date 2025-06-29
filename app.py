# ✅ Full-featured Binance Trading Bot - Spot, TP/SL, Anti-Ban

import os
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY") or "BURAYA_API_KEY"
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET") or "BURAYA_SECRET"

# ✅ SPAM ve RATE LIMIT KORUMA
last_signals = {}
MIN_INTERVAL_SECONDS = 60

def is_spam_signal(symbol, side):
    key = f"{symbol}_{side}"
    current_time = time.time()
    if key in last_signals:
        time_diff = current_time - last_signals[key]
        if time_diff < MIN_INTERVAL_SECONDS:
            print(f"\u274c SPAM BLOCK: {symbol} {side} - {time_diff:.1f}s once geldi")
            return True
    last_signals[key] = current_time
    return False

def execute_with_retry(func, max_retries=3, delay=5):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error = str(e)
            print(f"\u274c Deneme {attempt + 1} basarisiz: {error}")
            if "418" in error or "banned" in error.lower() or "-1003" in error:
                wait = 60 * (2 ** attempt)
                print(f"\u23f3 Ban koruma aktif! {wait}s bekleniyor...")
                time.sleep(wait)
            elif attempt < max_retries - 1:
                time.sleep(delay)
            else:
                raise e

# ✅ GERCEK POZISYON KONTROLU

def has_position(client, symbol):
    asset = symbol.replace("USDT", "")
    balances = client.account()["balances"]
    coin = next((b for b in balances if b["asset"] == asset), None)
    return float(coin["free"]) > 0 if coin else False

def get_free_balance(client, asset):
    balances = client.account()["balances"]
    bal = next((b for b in balances if b["asset"] == asset), None)
    return float(bal["free"]) if bal else 0.0

def get_step_size(client, symbol):
    info = client.exchange_info()
    sym = next((s for s in info["symbols"] if s["symbol"] == symbol), None)
    step = 0.0001
    if sym:
        for f in sym["filters"]:
            if f["filterType"] == "LOT_SIZE":
                step = float(f["stepSize"])
                break
    return step

# ✅ FIYAT TAKIPLI TP/SL SISTEMI
trackers = {}  # symbol -> {entry_price, tp, sl}

def track_tp_sl(symbol, entry_price, tp_percent, sl_percent):
    client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
    tp = entry_price * (1 + tp_percent / 100)
    sl = entry_price * (1 - sl_percent / 100)
    print(f"\ud83c\udf0d Takip: {symbol} | TP: {tp:.2f} | SL: {sl:.2f}")

    while has_position(client, symbol):
        price = float(client.ticker_price(symbol)["price"])
        print(f"\ud83d\udd39 {symbol} Anlik: {price:.2f}")

        if price >= tp:
            print(f"\u2705 TP Seviyesi Geldi - SATILIYOR!")
            qty = get_free_balance(client, symbol.replace("USDT", ""))
            step = get_step_size(client, symbol)
            dec = abs(int(f"{step:e}".split("e")[-1]))
            qty = round(qty - step, dec)
            client.new_order(symbol=symbol, side="SELL", type="MARKET", quantity=qty)
            break

        elif price <= sl:
            print(f"\u26d4 SL Seviyesi Geldi - SATILIYOR!")
            qty = get_free_balance(client, symbol.replace("USDT", ""))
            step = get_step_size(client, symbol)
            dec = abs(int(f"{step:e}".split("e")[-1]))
            qty = round(qty - step, dec)
            client.new_order(symbol=symbol, side="SELL", type="MARKET", quantity=qty)
            break

        time.sleep(5)

@app.route("/webhook", methods=["POST"])
def webhook():
    if not request.is_json:
        return jsonify({"status": "error", "message": "JSON bekleniyor"}), 400

    data = request.get_json()
    symbol = data.get("ticker", "").upper()
    side = data.get("side", "").upper()
    client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

    if side not in ["BUY", "SELL"]:
        return jsonify({"status": "error", "message": "BUY/SELL bekleniyor"}), 400

    if is_spam_signal(symbol, side):
        return jsonify({"status": "skipped", "reason": "Spam sinyali"})

    try:
        if side == "BUY":
            price = float(str(data.get("price", "0")).replace(",", "."))
            step = get_step_size(client, symbol)
            dec = abs(int(f"{step:e}".split("e")[-1]))

            if str(data.get("usdt_amount")).upper() == "ALL":
                usdt = get_free_balance(client, "USDT") * 0.998
                qty = round(usdt / price, dec)
            elif "usdt_amount" in data:
                usdt = float(str(data.get("usdt_amount", "0")).replace(",", "."))
                qty = round(usdt / price, dec)
            elif "quantity" in data:
                qty = float(data["quantity"])
            else:
                return jsonify({"status": "error", "message": "Miktar belirtilmeli"}), 400

            client.new_order(symbol=symbol, side="BUY", type="MARKET", quantity=qty)

            tp = data.get("tp")
            sl = data.get("sl")
            if tp and sl:
                threading.Thread(target=track_tp_sl, args=(symbol, price, float(tp), float(sl))).start()

            return jsonify({"status": "success", "message": f"{symbol} BUY emri gonderildi", "quantity": qty})

        elif side == "SELL":
            if not has_position(client, symbol):
                return jsonify({"status": "skipped", "reason": "Pozisyon yok"})
            free = get_free_balance(client, symbol.replace("USDT", ""))
            step = get_step_size(client, symbol)
            dec = abs(int(f"{step:e}".split("e")[-1]))
            qty = round(free - step, dec) if "quantity" not in data else float(data["quantity"])
            client.new_order(symbol=symbol, side="SELL", type="MARKET", quantity=qty)
            return jsonify({"status": "success", "message": f"{symbol} SELL gonderildi", "quantity": qty})

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/balance", methods=["GET"])
def balance():
    client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
    balances = client.account()["balances"]
    result = {b["asset"]: float(b["free"]) for b in balances if float(b["free"]) > 0}
    return jsonify({"status": "success", "balances": result})

@app.route("/balance/<symbol>", methods=["GET"])
def coin_balance(symbol):
    client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
    free = get_free_balance(client, symbol.upper())
    return jsonify({"status": "success", "asset": symbol.upper(), "balance": free})

@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": "running",
        "last_signals": {k: datetime.fromtimestamp(v).strftime('%H:%M:%S') for k, v in last_signals.items()},
        "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

@app.route("/myip", methods=["GET"])
def myip():
    return jsonify({"ip": request.remote_addr})

@app.route("/reset", methods=["POST"])
def reset():
    last_signals.clear()
    trackers.clear()
    return jsonify({"status": "reset", "message": "Geçmiş sinyaller temizlendi."})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"\ud83d\ude80 Bot calisiyor | Port: {port}")
    app.run(host="0.0.0.0", port=port)
