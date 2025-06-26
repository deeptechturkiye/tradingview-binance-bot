import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# API Key ve Secret
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY") or "BURAYA_API_KEY"
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET") or "BURAYA_SECRET"

@app.route('/webhook', methods=['POST'])
def webhook():
    if not request.is_json:
        return jsonify({"status": "error", "message": "JSON bekleniyor"}), 400

    data = request.get_json()
    print(f"📩 Webhook: {data}")

    try:
        client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Binance hatası: {e}"}), 500

    symbol = data.get("ticker", "").upper()
    side = data.get("side", "").upper()

    if side not in ["BUY", "SELL"]:
        return jsonify({"status": "error", "message": f"Geçersiz yön: {side}"}), 400

    try:
        if side == "BUY":
            usdt_amount = float(str(data.get("usdt_amount", "0")).replace(",", "."))
            price = float(client.ticker_price(symbol=symbol)["price"])

            # Lot adımını Binance’ten al
            exchange_info = client.exchange_info()
            symbol_info = next((s for s in exchange_info["symbols"] if s["symbol"] == symbol), None)
            step_size = 0.0001  # Varsayılan

            if symbol_info:
                for f in symbol_info["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        step_size = float(f["stepSize"])
                        break

            # Ondalık basamak sayısını hesapla (örn: 0.0001 → 4)
            decimals = abs(int(f"{step_size:e}".split("e")[-1]))
            quantity = round(usdt_amount / price, decimals)

        else:  # SELL
            asset = symbol.replace("USDT", "")
            balances = client.account()["balances"]
            balance = next((b for b in balances if b["asset"] == asset), None)

            if not balance:
                return jsonify({"status": "error", "message": f"{asset} bakiyesi yok"}), 400

            free = float(balance["free"])
            exchange_info = client.exchange_info()
            symbol_info = next((s for s in exchange_info["symbols"] if s["symbol"] == symbol), None)
            step_size = 0.0001

            if symbol_info:
                for f in symbol_info["filters"]:
                    if f["filterType"] == "LOT_SIZE":
                        step_size = float(f["stepSize"])
                        break

            decimals = abs(int(f"{step_size:e}".split("e")[-1]))
            quantity = round(free - step_size, decimals)  # Komisyon marjı

        order = client.new_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)
        print(f"✅ İşlem gönderildi: {order}")

        return jsonify({"status": "success", "message": f"{symbol} için {side} emri gönderildi"}), 200

    except Exception as e:
        print(f"❌ Emir hatası: {e}")
        return jsonify({"status": "error", "message": f"İşlem hatası: {e}"}), 500

@app.route('/myip', methods=['GET'])
def get_ip():
    return jsonify({"ip": request.remote_addr})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
