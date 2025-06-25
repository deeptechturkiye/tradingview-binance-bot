# Gerekli kütüphaneleri içe aktar
from flask import Flask, request
import json
import os
from binance.spot import Spot as Client

# Flask uygulamasını oluştur
app = Flask(__name__)

# --- ÖNEMLİ VE GÜVENLİ YÖNTEM ---
# API Anahtarlarını kodun içine yazmak yerine, Heroku'daki Ortam Değişkenlerinden (Config Vars) al.
# Bu, anahtarlarınızın güvende kalmasını sağlar.
BINANCE_API_KEY = os.environ.get("BINANCE_API_KEY")
BINANCE_SECRET_KEY = os.environ.get("BINANCE_SECRET_KEY")

# TradingView'dan gelen sinyalleri yakalayacak adres
@app.route("/webhook", methods=['POST'])
def webhook():
    try:
        # Gelen veriyi JSON formatına çevir
        data = json.loads(request.data)
        
        # Verinin içinden gerekli bilgileri al
        ticker = data['ticker']
        side = data['side']
        quantity = data['quantity']

        # Binance'e gönderilecek emir (order) parametrelerini hazırla
        params = {
            "symbol": ticker,
            "side": side.upper(),  # 'buy' veya 'sell' gelirse diye büyük harfe çevir
            "type": "MARKET",
            "quantity": quantity,
        }

        # Binance API istemcisini (client) anahtarlarınla oluştur
        client = Client(BINANCE_API_KEY, BINANCE_SECRET_KEY)
        
        # Yeni market emrini Binance'e gönder
        client.new_order(**params)
        print(f"Başarılı emir: {side} {quantity} {ticker}")

    except Exception as e:
        # Bir hata olursa, hatayı Heroku loglarına yazdır.
        # Bu sayede Heroku kontrol panelinden hatanın ne olduğunu görebilirsin.
        print(f"HATA OLUŞTU: {e}")

    # Her durumda TradingView'a işlemin alındığına dair bir mesaj gönder
    return {"code": "success"}


# Bu bölüm, kodu kendi bilgisayarında çalıştırırsan devreye girer.
# Heroku bu kısmı kullanmaz, kendi sunucusunu (Gunicorn) kullanır.
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
