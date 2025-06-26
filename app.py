import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# API Key ve Secret (env veya doğrudan)
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
            quantity = round(usdt_amount / price, 5)
        else:
            asset = symbol.replace("USDT", "").upper()
            balances = client.account()["balances"]
            coin_balance = next((b for b in balances if b["asset"] == asset), None)
            if not coin_balance:
                return jsonify({"status": "error", "message": f"{asset} bakiyesi bulunamadı"}), 404
            quantity = round(float(coin_balance["free"]) - 0.001, 5)  # küçük komisyon payı
    except Exception as e:
        return jsonify({"status": "error", "message": f"Emir öncesi hesaplama hatası: {e}"}), 500

    try:
        order = client.new_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)
        print(f"✅ Emir gerçekleşti: {order}")

        asset = symbol.replace("USDT", "")
        balances = client.account()["balances"]
        balance = next((b for b in balances if b["asset"] == asset), None)
        if balance:
            print(f"📊 Yeni bakiye {asset}: {balance['free']}")

        return jsonify({"status": "success", "message": f"{side} emri gönderildi: {quantity} {asset}"}), 200
    except Exception as e:
        print(f"❌ Emir hatası: {e}")
        return jsonify({"status": "error", "message": f"Emir başarısız: {e}"}), 400

@app.route('/myip', methods=['GET'])
def get_ip():
    return jsonify({"ip": request.remote_addr})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
