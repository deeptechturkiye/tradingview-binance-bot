from flask import Flask, request
import json
import os
from binance.spot import Spot as Client

app = Flask(__name__)

# Key'leri Heroku Config Vars'tan al
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY")

@app.route("/webhook", methods=['POST'])
def webhook():
    try:
        data = json.loads(request.data)
        ticker = data['ticker']
        exchange = data['exchange']
        price = data['price']
        side = data['side']
        quantity = data['quantity']

        params = {
            "symbol": ticker,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }

        # Binance işlemi yap
        Client(BINANCE_API_KEY, BINANCE_SECRET_KEY).new_order(**params)

    except Exception as e:
        print(f"Hata oluştu: {e}")

    return {"code": "success"}

# Çalıştır
if __name__ == '__main__':
    app.run(debug=True, port=5000)