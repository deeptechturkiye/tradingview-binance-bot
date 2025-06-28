import os
import time
from datetime import datetime
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# Güvenli API erişimi
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY") or "BURAYA_API_KEY"
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET") or "BURAYA_SECRET"

# SPAM KORUMA
last_signals = {}
MIN_INTERVAL_SECONDS = 60

# Retry wrapper
def execute_with_retry(func, max_retries=3, delay=5):
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            error_str = str(e)
            print(f"❌ Deneme {attempt + 1} başarısız: {error_str}")
            if "418" in error_str or "banned" in error_str.lower() or "-1003" in error_str:
                wait_time = 60 * (2 ** attempt)
                print(f"⏳ Rate limit! {wait_time} saniye bekleniyor...")
                time.sleep(wait_time)
            elif attempt < max_retries - 1:
                print(f"⏳ {delay} saniye beklenip tekrar deneniyor...")
                time.sleep(delay)
            else:
                raise e

# SPAM kontrolü
def is_spam_signal(symbol, side):
    key = f"{symbol}_{side}"
    current_time = time.time()
    if key in last_signals:
        time_diff = current_time - last_signals[key]
        if time_diff < MIN_INTERVAL_SECONDS:
            print(f"🚫 SPAM! {symbol} {side} sinyali {time_diff:.1f}s önce geldi")
            return True
    last_signals[key] = current_time
    return False

# Gerçek pozisyon kontrolü
def has_position(client, symbol):
    asset = symbol.replace("USDT", "")
    balances = client.account()["balances"]
    coin = next((b for b in balances if b["asset"] == asset), None)
    if coin is None:
        return False
    return float(coin["free"]) > 0

@app.route('/webhook', methods=['POST'])
def webhook():
    if not request.is_json:
        return jsonify({"status": "error", "message": "JSON bekleniyor"}), 400

    data = request.get_json()
    print(f"📩 Webhook: {data} | Zaman: {datetime.now().strftime('%H:%M:%S')}")

    symbol = data.get("ticker", "").upper()
    side = data.get("side", "").upper()

    if side not in ["BUY", "SELL"]:
        return jsonify({"status": "error", "message": f"Geçersiz yön: {side}"}), 400

    if is_spam_signal(symbol, side):
        return jsonify({"status": "skipped", "reason": "Spam sinyal"}), 200

    try:
        client = execute_with_retry(lambda: Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET))

        if side == "BUY":
            usdt_amount = float(str(data.get("usdt_amount", "0")).replace(",", "."))
            price = float(str(data.get("price", "0")).replace(",", "."))

            def get_step_size():
                info = client.exchange_info()
                sym = next((s for s in info["symbols"] if s["symbol"] == symbol), None)
                step = 0.0001
                if sym:
                    for f in sym["filters"]:
                        if f["filterType"] == "LOT_SIZE":
                            step = float(f["stepSize"])
                            break
                return step

            step_size = execute_with_retry(get_step_size)
            decimals = abs(int(f"{step_size:e}".split("e")[-1]))
            quantity = round(usdt_amount / price, decimals)

        else:  # SELL
            if not has_position(client, symbol):
                return jsonify({"status": "skipped", "reason": "Gerçek pozisyon yok"}), 200

            def get_balance():
                balances = client.account()["balances"]
                asset = symbol.replace("USDT", "")
                bal = next((b for b in balances if b["asset"] == asset), None)
                if not bal:
                    raise Exception(f"{asset} bakiyesi yok")
                return float(bal["free"])

            free = execute_with_retry(get_balance)

            def get_step_size():
                info = client.exchange_info()
                sym = next((s for s in info["symbols"] if s["symbol"] == symbol), None)
                step = 0.0001
                if sym:
                    for f in sym["filters"]:
                        if f["filterType"] == "LOT_SIZE":
                            step = float(f["stepSize"])
                            break
                return step

            step_size = execute_with_retry(get_step_size)
            decimals = abs(int(f"{step_size:e}".split("e")[-1]))
            quantity = round(free - step_size, decimals)

        def place_order():
            return client.new_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)

        order = execute_with_retry(place_order)

        print(f"✅ İşlem başarılı: {symbol} {side} {quantity} | Zaman: {datetime.now().strftime('%H:%M:%S')}")
        return jsonify({
            "status": "success",
            "message": f"{symbol} için {side} emri gönderildi",
            "quantity": quantity
        }), 200

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Emir hatası: {error_msg}")
        if "418" in error_msg or "banned" in error_msg.lower():
            return jsonify({
                "status": "error",
                "message": "Rate limit hatası - Sistem geçici olarak durduruldu",
                "error_type": "rate_limit"
            }), 429
        return jsonify({"status": "error", "message": f"İşlem hatası: {error_msg}"}), 500

# ✅ Tüm coin bakiyeleri
@app.route('/balance', methods=['GET'])
def balance():
    try:
        client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
        info = client.account()
        result = {b['asset']: float(b['free']) for b in info['balances'] if float(b['free']) > 0}
        return jsonify({"status": "success", "balances": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# ✅ Belirli coin bakiyesi (örn: /balance/BNB)
@app.route('/balance/<symbol>', methods=['GET'])
def balance_of(symbol):
    try:
        client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
        info = client.account()
        coin = next((b for b in info['balances'] if b['asset'].upper() == symbol.upper()), None)
        if not coin:
            return jsonify({"status": "success", "asset": symbol.upper(), "balance": 0.0})
        return jsonify({"status": "success", "asset": symbol.upper(), "balance": float(coin['free'])})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

# Durum kontrol
@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "status": "active",
        "last_signals": {k: datetime.fromtimestamp(v).strftime('%H:%M:%S') for k, v in last_signals.items()},
        "current_time": datetime.now().strftime('%H:%M:%S')
    })

# IP öğren
@app.route('/myip', methods=['GET'])
def get_ip():
    return jsonify({"ip": request.remote_addr})

# Flask başlat
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Bot başlatılıyor - Port: {port}")
    app.run(host="0.0.0.0", port=port)
