from flask import Flask, request
import json
# import telebot # Telegram kaldırıldı
from binance.spot import Spot as Client

app = Flask(__name__)

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
        binanceApiKey = data['binanceApiKey'] # Anahtarlar kodda sabit olduğu için kaldırıldı
        binanceSecretKey = data['binanceSecretKey'] # Anahtarlar kodda sabit olduğu için kaldırıldı

        params = {
            "symbol": ticker,
            "side": side,
            "type": "MARKET",
            "quantity": quantity,
        }


        Client(BINANCE_API_KEY, BINANCE_SECRET_KEY).new_order(**params)

        # telebot.TeleBot(telegramBotApi).send_message(telegramUserId, # Telegram kaldırıldı
        #                                              f"{ticker} {side}ING on {exchange} \nQuantity : {quantity} ")
    except:
        pass

    return {
        "code": "success",
    }