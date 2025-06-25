from flask import Flask, request
import json
# import telebot # Telegram kaldırıldı
from binance.spot import Spot as Client

app = Flask(__name__)

# Sizin Binance API anahtarlarınız doğrudan buraya yazıldı
BINANCE_API_KEY = "1NK6KpwVAvrujTmmqi5svQoWeIWJcui8DsvrfDufG6tUfxRBpimJbVzfvMH77y7K"
BINANCE_SECRET_KEY = "VzU4O81to2lNcOYXwi8yloB8ZpDCeY6Qm02DAEGGniEXs82E78MoYX6jeXR3Pzda"

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

        # Binance Client'ı kodda tanımlı API anahtarlarıyla kullan
        Client(BINANCE_API_KEY, BINANCE_SECRET_KEY).new_order(**params)

    except Exception as e: # Hataları yakalamak ve göstermek için düzeltildi
        print(f"Hata oluştu: {e}") # Hatayı konsola yazdır

    return {
        "code": "success",
    }

# Flask uygulamasını başlat
if __name__ == '__main__':
    app.run(debug=True, port=5000)