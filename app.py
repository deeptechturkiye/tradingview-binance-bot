import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# Binance API key ve secret (Render için ortam değişkenlerinden alınır)
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "YOUR_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET", "YOUR_API_SECRET")

client = Client(BINANCE_API_KEY, BINANCE_API_SECRET)

@app.route('/')
def home():
    return "Webhook bot is live!"

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print("📩 Webhook verisi alındı:", data)

    try:
        ticker = data.get("ticker")
        side = data.get("side").upper()
        usdt_amount = float(data.get("usdt_amount"))

        if not ticker or not side or not usdt_amount:
            return jsonify({"status": "error", "message": "Eksik veri"}), 400

        # Mevcut fiyatı anlık çekiyoruz
        price_data = client.ticker_price(symbol=ticker)
        current_price = float(price_data["price"])

        quantity = round(usdt_amount / current_price, 5)

        if side == "BUY":
            order = client.new_order(symbol=ticker, side="BUY", type="MARKET", quantity=quantity)
        elif side == "SELL":
            order = client.new_order(symbol=ticker, side="SELL", type="MARKET", quantity=quantity)
        else:
            return jsonify({"status": "error", "message": "Geçersiz yön"}), 400

        return jsonify({"status": "success", "order": order})

    except Exception as e:
        print("❌ Hata:", str(e))
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/balance/<symbol>', methods=['GET'])
def balance(symbol):
    try:
        account = client.account()
        asset = next((b for b in account["balances"] if b["asset"] == symbol.upper()), None)
        if asset:
            return jsonify({"status": "success", "asset": asset["asset"], "balance": float(asset["free"])})
        else:
            return jsonify({"status": "error", "message": "Varlık bulunamadı"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/balance', methods=['GET'])
def all_balances():
    try:
        account = client.account()
        balances = {b["asset"]: float(b["free"]) for b in account["balances"] if float(b["free"]) > 0}
        return jsonify({"status": "success", "balances": balances})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False)
