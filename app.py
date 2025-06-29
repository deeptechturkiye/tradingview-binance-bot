import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# Ortam değişkenlerinden API anahtarlarını al
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")

# Binance istemcisi
client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json
        print("📩 Webhook verisi alındı:", data)

        symbol = data["ticker"]
        side = data["side"].upper()
        usdt_amount = data["usdt_amount"]

        if side == "BUY":
            usdt = float(usdt_amount)
            price = float(client.ticker_price(symbol))
            quantity = round(usdt / price, 5)
            order = client.new_order(
                symbol=symbol, side="BUY", type="MARKET", quantity=quantity
            )
            return jsonify({"status": "buy order sent", "details": order}), 200

        elif side == "SELL":
            if usdt_amount == "ALL":
                asset = symbol.replace("USDT", "")
                balance = client.user_asset_balance(asset=asset)
                quantity = float(balance["free"])
            else:
                usdt = float(usdt_amount)
                price = float(client.ticker_price(symbol))
                quantity = round(usdt / price, 5)

            order = client.new_order(
                symbol=symbol, side="SELL", type="MARKET", quantity=quantity
            )
            return jsonify({"status": "sell order sent", "details": order}), 200

        else:
            return jsonify({"error": "Invalid side"}), 400

    except Exception as e:
        print("❌ Hata:", str(e))
        return jsonify({"error": str(e)}), 500


@app.route("/balance", methods=["GET"])
def get_all_balances():
    try:
        account_info = client.account()
        balances = {
            asset["asset"]: float(asset["free"])
            for asset in account_info["balances"]
            if float(asset["free"]) > 0
        }
        return jsonify({"balances": balances, "status": "success"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/balance/<asset>", methods=["GET"])
def get_asset_balance(asset):
    try:
        balance = client.user_asset_balance(asset=asset.upper())
        return jsonify({
            "asset": asset.upper(),
            "balance": float(balance["free"]),
            "status": "success"
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=False)
