import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# Ortam değişkenlerinden API anahtarlarını al
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_API_SECRET = os.environ.get("BINANCE_API_SECRET")
client = Client(api_key=BINANCE_API_KEY, api_secret=BINANCE_API_SECRET)

@app.route('/')
def index():
    return "✅ Bot çalışıyor!"

@app.route('/balance')
def balance_all():
    account_info = client.account()
    balances = {
        asset['asset']: float(asset['free'])
        for asset in account_info['balances']
        if float(asset['free']) > 0
    }
    return jsonify({"balances": balances, "status": "success"})

@app.route('/balance/<symbol>')
def balance_one(symbol):
    balance = client.get_asset_balance(asset=symbol.upper())
    return jsonify({
        "asset": symbol.upper(),
        "balance": float(balance['free']),
        "status": "success"
    })

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        symbol = data.get("ticker")
        side = data.get("side").upper()
        usdt_amount_raw = data.get("usdt_amount")

        if symbol is None or side not in ["BUY", "SELL"] or usdt_amount_raw is None:
            return jsonify({"message": "Eksik parametre", "status": "error"}), 400

        base_asset = symbol.replace("USDT", "")
        quantity = 0

        if usdt_amount_raw == "ALL":
            asset = base_asset if side == "SELL" else "USDT"
            balance = float(client.get_asset_balance(asset=asset)["free"])
            if side == "SELL":
                quantity = balance * 0.995  # %0.5 güvenlik marjı
            else:
                price = float(client.ticker_price(symbol=symbol))
                quantity = (balance / price) * 0.995
        else:
            usdt_amount = float(usdt_amount_raw)
            price = float(client.ticker_price(symbol=symbol))
            quantity = usdt_amount / price

        # Yuvarla
        quantity = round(quantity, 5)

        order = client.new_order(
            symbol=symbol,
            side=side,
            type="MARKET",
            quantity=quantity
        )

        return jsonify({"message": f"{side} emri gönderildi", "order": order, "status": "success"})

    except Exception as e:
        return jsonify({"message": str(e), "status": "error"}), 500

if __name__ == '__main__':
    app.run(debug=True)
