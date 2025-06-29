import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# Ortam değişkenlerinden veya elle yazılmış API anahtarları
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY") or "BURAYA_API_KEY"
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET") or "BURAYA_SECRET"

client = Client(key=BINANCE_API_KEY, secret=BINANCE_API_SECRET)

@app.route('/webhook', methods=['POST'])
def webhook():
    if not request.is_json:
        return jsonify({"status": "error", "message": "JSON bekleniyor"}), 400

    data = request.get_json()
    print(f"📩 Webhook alındı: {data}")

    ticker = data.get("ticker")
    side = data.get("side")
    usdt_amount = float(data.get("usdt_amount", 0))

    if not all([ticker, side, usdt_amount]):
        return jsonify({"status": "error", "message": "Eksik veri var"}), 400

    # Sadece burada fiyat bilgisi alınır
    try:
        ticker_price = float(client.ticker_price(symbol=ticker))
        print(f"🎯 {ticker} şu anki fiyat: {ticker_price}")
    except Exception as e:
        return jsonify({"status": "error", "message": f"Fiyat alınamadı: {e}"}), 500

    # Hesaplanacak miktar
    quantity = round(usdt_amount / ticker_price, 5)

    try:
        if side.upper() == "BUY":
            order = client.new_order(symbol=ticker, side="BUY", type="MARKET", quoteOrderQty=usdt_amount)
        elif side.upper() == "SELL":
            order = client.new_order(symbol=ticker, side="SELL", type="MARKET", quantity=quantity)
        else:
            return jsonify({"status": "error", "message": f"Geçersiz işlem tipi: {side}"}), 400

        print(f"✅ {side.upper()} emri gönderildi: {order}")
        return jsonify({"status": "success", "order": order})

    except Exception as e:
        print(f"❌ Emir hatası: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/balance/<symbol>', methods=['GET'])
def get_balance(symbol):
    try:
        balance_info = client.asset_balance(symbol=symbol.upper())
        return jsonify({"status": "success", "asset": symbol.upper(), "balance": balance_info['free']})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/balance', methods=['GET'])
def get_all_balances():
    try:
        balances = client.account()["balances"]
        balances = {b['asset']: float(b['free']) for b in balances if float(b['free']) > 0}
        return jsonify({"status": "success", "balances": balances})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False)
