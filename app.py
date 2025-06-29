import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# Binance API Anahtarları
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY", "BURAYA_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET", "BURAYA_SECRET")

# Binance istemcisi
client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

# Ana endpoint → servis ayakta mı kontrol için
@app.route('/')
def home():
    return "✅ Bot is working and waiting for webhook..."

# Webhook endpoint
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()

    try:
        symbol = data['ticker']
        side = data['side']
        usdt_amount = float(data['usdt_amount'])

        # Fiyatı al
        price = float(client.ticker_price(symbol=symbol)['price'])
        quantity = round(usdt_amount / price, 5)

        # Alış/Satış işlemi
        if side == "BUY":
            order = client.new_order(symbol=symbol, side="BUY", type="MARKET", quantity=quantity)
        elif side == "SELL":
            order = client.new_order(symbol=symbol, side="SELL", type="MARKET", quantity=quantity)
        else:
            return jsonify({"status": "error", "message": "Geçersiz işlem yönü"}), 400

        print(f"✅ Emir gönderildi: {order}")
        return jsonify({"status": "success", "order": order}), 200

    except Exception as e:
        print(f"❌ Hata: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Bakiye sorgulama
@app.route('/balance/<symbol>', methods=['GET'])
def balance(symbol):
    try:
        balance = client.balance(symbol=symbol.upper())
        return jsonify({"status": "success", "asset": symbol.upper(), "balance": float(balance)}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/balance', methods=['GET'])
def all_balances():
    try:
        balances = client.account()['balances']
        balances = {item['asset']: float(item['free']) for item in balances if float(item['free']) > 0}
        return jsonify({"status": "success", "balances": balances}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
