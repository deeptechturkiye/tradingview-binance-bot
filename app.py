from flask import Flask, request
import json
# import telebot # Telegram kaldırıldı
from binance.spot import Spot as Client

app = Flask(__name__)

# Sizin Binance API anahtarlarınız doğrudan buraya yazıldı
BINANCE_API_KEY = "tLcl7vllh7XnfiAk3YMDmQ2ocxBPSbsdYnsV6EaCbb6DiISxZVjjV8NBcdcX1PtP"
BINANCE_SECRET_KEY = "5TeRqdzZx2n9RPsM6KhHLAcgLCRlccYca2pIhkcxBs9IcQhtdATS06yasI2IMZCM"


@app.route("/webhook", methods=['POST'])
def webhook():
    try:
        data = json.loads(request.data)
        ticker = data['ticker']
        exchange = data['exchange']
        price = data['price']
        side = data['side']
        quantity = data['quantity']
        # telegramBotApi = data['telegramBotApi'] # Telegram kaldırıldı
        # telegramUserId = data['telegramUserId'] # Telegram kaldırıldı
        # binanceApiKey = data['binanceApiKey'] # Anahtarlar kodda sabit olduğu için kaldırıldı
        # binanceSecretKey = data['binanceSecretKey'] # Anahtarlar kodda sabit olduğu için kaldırıldı

        params = {
            "symbol": ticker,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }

        # Binance Client'ı kodda tanımlı API anahtarlarıyla kullan
        Client(BINANCE_API_KEY, BINANCE_SECRET_KEY).new_order(**params)

        # telebot.TeleBot(telegramBotApi).send_message(telegramUserId, # Telegram kaldırıldı
        #                                              f"{ticker} {side}ING on {exchange} \nQuantity : {quantity} ")
    except Exception as e:  # Hataları yakalamak ve göstermek için düzeltildi
        print(f"Hata oluştu: {e}")  # Hatayı konsola yazdır
        # Hata durumunda da success döndürülecek, videodaki davranışa göre

    return {
        "code": "success",
    }


# Flask uygulamasını başlat
if __name__ == '__main__':
    app.run(debug=True, port=5000)