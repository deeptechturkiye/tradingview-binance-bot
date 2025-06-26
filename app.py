import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# API Key ve Secret (env ya da doğrudan tanım)
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY") or "BURAYA_API_KEY"
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET") or "BURAYA_SECRET"

@app.route('/webhook', methods=['POST'])
def webhook():
    if not request.is_json:
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

    data = request.get_json()
    print(f"Webhook received: {data}")

    try:
        client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)
    except Exception as e:
        return jsonify({"status": "error", "message": f"Binance client error: {e}"}), 500

    symbol = data.get("ticker", "").upper()
    side = data.get("side", "").upper()

    if side not in ["BUY", "SELL"]:
        return jsonify({"status": "error", "message": f"Invalid side: {side}"}), 400

    # Eğer SELL ise → Otomatik coin bakiyesi tespit et
    if side == "SELL":
        try:
            # Coin adını sembolden ayıkla (örn: ETHUSDT → ETH)
            asset = symbol.replace("USDT", "").upper()

            # Hesaptaki coin bakiyesini çek
            balances = client.account()["balances"]
            coin_balance = next((b for b in balances if b["asset"] == asset), None)

            if not coin_balance:
                return jsonify({"status": "error", "message": f"No balance found for asset: {asset}"}), 404

            free_amount = float(coin_balance["free"])
            quantity = round(free_amount - 0.001, 6)  # Komisyon payı bırak
        except Exception as e:
            return jsonify({"status": "error", "message": f"Balance fetch error: {e}"}), 500

    else:
        # BUY için quantity doğrudan JSON'dan gelir
        qty_raw = str(data.get("quantity", "0")).replace(",", ".")
        try:
            quantity = float(qty_raw)
        except:
            return jsonify({"status": "error", "message": f"Quantity parse error: {qty_raw}"}), 400

    # Market emrini ver
    try:
        order = client.new_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)
        print(f"✅ Order executed: {order}")

        # İşlem sonrası bakiyeyi göster
        try:
            asset = symbol.replace("USDT", "").upper()
            balances = client.account()["balances"]
            updated_balance = next((b for b in balances if b["asset"] == asset), None)
            print(f"📊 Güncel {asset} Bakiyesi: {updated_balance['free']}")
        except Exception as e:
            print(f"⚠️ Bakiyeyi gösterme hatası: {e}")

        return jsonify({"status": "success", "message": f"{side} order executed for {symbol}"}), 200

    except Exception as e:
        print(f"❌ Binance order error: {e}")
        return jsonify({"status": "error", "message": f"Order error: {e}"}), 400

# Test için /myip route (IP loglama)
@app.route('/myip', methods=['GET'])
def get_ip():
    return jsonify({"ip": request.remote_addr})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
