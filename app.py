import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# Binance API anahtarları
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")

client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

# USDT bakiyesini veya istenen varlığı sorgulamak için
@app.route("/balance/<asset>", methods=["GET"])
def balance(asset):
    try:
        info = client.account()
        for b in info["balances"]:
            if b["asset"] == asset.upper():
                return jsonify({"asset": asset.upper(), "balance": b["free"], "status": "success"})
        return jsonify({"message": f"{asset} not found", "status": "error"}), 404
    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

@app.route("/webhook", methods=["POST"])
def webhook():
    data = request.get_json()

    try:
        ticker = data["ticker"]
        side = data["side"].upper()
        amount_raw = data["usdt_amount"]

        # Güncel fiyatı çek
        price = float(client.ticker_price(ticker)["price"])

        # Varlık adı (örneğin: BNBUSDT -> BNB)
        base_asset = ticker.replace("USDT", "")

        if amount_raw == "ALL":
            balance = float(client.account()["balances"]
                            [0 if base_asset == "USDT" else
                             next(i for i, b in enumerate(client.account()["balances"]) if b["asset"] == (base_asset if side == "SELL" else "USDT"))]["free"])

            if side == "BUY":
                qty = round(balance / price, 6)
            else:  # SELL
                qty = round(balance, 6)
        else:
            qty = round(float(amount_raw) / price, 6) if side == "BUY" else round(float(amount_raw), 6)

        order = client.new_order(
            symbol=ticker,
            side=side,
            type="MARKET",
            quantity=qty
        )

        return jsonify({
            "message": f"{side} emri gönderildi",
            "order": order,
            "quantity": qty,
            "status": "success"
        })

    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 400
