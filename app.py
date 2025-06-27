import os
import time
from datetime import datetime
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# API Key ve Secret
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY") or "BURAYA_API_KEY"
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET") or "BURAYA_SECRET"

# SPAM KORUMA
last_signals = {}
MIN_INTERVAL_SECONDS = 60
position_state = {}


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


def can_execute_trade(symbol, side):
    current_position = position_state.get(symbol, "NONE")
    if is_spam_signal(symbol, side):
        return False, "Spam sinyal"
    if side == "BUY":
        if current_position == "LONG":
            return False, "Zaten LONG pozisyonda"
    elif side == "SELL":
        if current_position != "LONG":
            return False, "LONG pozisyon yok, SELL yapılamaz"
    return True, "OK"


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
                print(f"⏳ {delay} saniye bekleyip tekrar deneniyor...")
                time.sleep(delay)
            else:
                raise e


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

    can_trade, reason = can_execute_trade(symbol, side)
    if not can_trade:
        print(f"⚠️ İşlem atlandı: {reason}")
        return jsonify({"status": "skipped", "reason": reason}), 200

    try:
        def create_binance_client():
            return Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

        client = execute_with_retry(create_binance_client)

        if side == "BUY":
            usdt_amount = float(str(data.get("usdt_amount", "0")).replace(",", "."))
            price = float(str(data.get("price", "0")).replace(",", "."))

            def get_exchange_info():
                exchange_info = client.exchange_info()
                symbol_info = next((s for s in exchange_info["symbols"] if s["symbol"] == symbol), None)
                step_size = 0.0001
                if symbol_info:
                    for f in symbol_info["filters"]:
                        if f["filterType"] == "LOT_SIZE":
                            step_size = float(f["stepSize"])
                            break
                return step_size

            step_size = execute_with_retry(get_exchange_info)
            decimals = abs(int(f"{step_size:e}".split("e")[-1]))
            quantity = round(usdt_amount / price, decimals)

        else:  # SELL
            asset = symbol.replace("USDT", "")

            def get_balance():
                balances = client.account()["balances"]
                balance = next((b for b in balances if b["asset"] == asset), None)
                if not balance:
                    raise Exception(f"{asset} bakiyesi yok")
                return float(balance["free"])

            free = execute_with_retry(get_balance)

            def get_step_size():
                exchange_info = client.exchange_info()
                symbol_info = next((s for s in exchange_info["symbols"] if s["symbol"] == symbol), None)
                step_size = 0.0001
                if symbol_info:
                    for f in symbol_info["filters"]:
                        if f["filterType"] == "LOT_SIZE":
                            step_size = float(f["stepSize"])
                            break
                return step_size

            step_size = execute_with_retry(get_step_size)
            decimals = abs(int(f"{step_size:e}".split("e")[-1]))
            quantity = round(free - step_size, decimals)

        def place_order():
            return client.new_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)

        order = execute_with_retry(place_order)

        if side == "BUY":
            position_state[symbol] = "LONG"
        elif side == "SELL":
            position_state[symbol] = "NONE"

        print(f"✅ İşlem başarılı: {symbol} {side} {quantity} | Zaman: {datetime.now().strftime('%H:%M:%S')}")
        print(f"📊 Güncel pozisyon: {position_state.get(symbol, 'NONE')}")

        return jsonify({
            "status": "success",
            "message": f"{symbol} için {side} emri gönderildi",
            "quantity": quantity,
            "position": position_state.get(symbol, 'NONE')
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


@app.route('/status', methods=['GET'])
def status():
    return jsonify({
        "status": "active",
        "positions": position_state,
        "last_signals": {k: datetime.fromtimestamp(v).strftime('%H:%M:%S') for k, v in last_signals.items()},
        "current_time": datetime.now().strftime('%H:%M:%S')
    })


@app.route('/reset', methods=['POST'])
def reset():
    global last_signals, position_state
    last_signals.clear()
    position_state.clear()
    return jsonify({"status": "reset", "message": "Tüm durumlar sıfırlandı"})


@app.route('/myip', methods=['GET'])
def get_ip():
    return jsonify({"ip": request.remote_addr})


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Bot başlatılıyor - Port: {port}")
    print(f"⏱️ Minimum sinyal aralığı: {MIN_INTERVAL_SECONDS} saniye")
    app.run(host="0.0.0.0", port=port)
