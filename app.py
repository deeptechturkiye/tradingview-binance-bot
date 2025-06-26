import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# DİKKAT: Güvenlik için ortam değişkenlerini kullanmak her zaman tercih edilir.
# Bu sadece hata ayıklama amacıyla ve geçici bir çözümdür.
# Kendi Binance API Key ve Secret'ınızı BURAYA girdim:
BINANCE_API_KEY = '1NK6KpwVAvrujTmmqi5svQoWeIWJcui8DsvrfDufG6tUfxRBpimJbVzfvMH77u7K'  # API Key'iniz
BINANCE_API_SECRET = 'VzU4O81to2lNcOYXwi8yloB8ZpDCeY6Qm02DAEGGniEXs82E78MOyX6jeXR3Pzda'  # Secret Key'iniz


@app.route('/webhook', methods=['POST'])
def webhook():
    if request.is_json:
        data = request.json
        # Gelen tüm JSON'u loglayın (hata ayıklama için önemli)
        print("Received webhook data:")
        print(data)

        side_value = data.get('side')
        # Gelen 'side' değerini loglayın
        print(f"Side value received: '{side_value}'")

        try:
            # Doğrudan koda gömülen anahtarları kullanın
            api_key = BINANCE_API_KEY
            api_secret = BINANCE_API_SECRET

            # Hata ayıklama için API anahtarlarının durumunu loglayın
            print(f"DEBUG: Using embedded BINANCE_API_KEY: {'[SET]' if api_key else '[NOT SET]'}")
            print(f"DEBUG: Using embedded BINANCE_API_SECRET: {'[SET]' if api_secret else '[NOT SET]'}")

            if not api_key or not api_secret:  # Anahtarların boş olup olmadığını kontrol eder
                raise ValueError("Binance API Key or Secret not properly set in code.")

            client = Client(api_key, api_secret)
        except Exception as e:
            print(f"Binance API Client initialization error: {e}")
            return jsonify({"status": "error", "message": "API Client init error"}), 500

        symbol = data.get('ticker')

        # TradingView'den string olarak gelebileceği için float'a çeviriyoruz
        # .replace(",", ".") ekledim, eğer TradingView ondalık ayracı olarak virgül gönderirse diye.
        try:
            quantity_str = str(data.get('quantity')).replace(",", ".")
            quantity = float(quantity_str)
        except (ValueError, TypeError):
            print(f"Error converting quantity to float: {data.get('quantity')}")
            return jsonify({"status": "error", "message": "Invalid quantity format"}), 400

        # Sadece "BUY" veya "SELL" gelirse emir gönder
        if side_value == "BUY" or side_value == "SELL":
            try:
                # Binance API'sine emir gönderme
                # type='MARKET' en basit emir türüdür. Limit emir veya başka türler de kullanabilirsiniz.
                order = client.new_order(symbol=symbol, side=side_value, type='MARKET', quantity=quantity)
                print(f"Order placed successfully: {order}")
                return jsonify({"status": "success", "message": "Order placed"}), 200
            except Exception as e:
                # Binance API'den dönen tüm hatayı loglayın
                print(f"Error placing order with Binance API: {e}")
                return jsonify({"status": "error", "message": str(e)}), 400
        else:
            # Geçersiz 'side' değeri geldiğinde hata ver
            print(f"Invalid side value received from TradingView: {side_value}. Not placing order.")
            return jsonify({"status": "error", "message": f"Invalid side value received: {side_value}"}), 400
    else:
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400


if __name__ == '__main__':
    # Render'da doğru portu kullanmak için 'PORT' ortam değişkenini kullanın
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
