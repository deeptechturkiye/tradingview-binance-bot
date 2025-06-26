import os
from flask import Flask, request, jsonify
from binance.spot import Spot as Client

app = Flask(__name__)

# DİKKAT: Güvenlik için ortam değişkenlerini kullanmak her zaman tercih edilir.
BINANCE_API_KEY = '1NK6KpwVAvrujTmmqi5svQoWeIWJcui8DsvrfDufG6tUfxRBpimJbVzfvMH77u7K'
BINANCE_API_SECRET = 'VzU4O81to2lNcOYXwi8yloB8ZpDCeY6Qm02DAEGGniEXs82E78MOyX6jeXR3Pzda'

@app.route('/webhook', methods=['POST'])
@app.route('/myip', methods=['GET'])
def get_ip():
    return jsonify({"ip": request.remote_addr})

def webhook():
    if request.is_json:
        data = request.json
        print("Received webhook data:")
        print(data)

        side_value = data.get('side')
        print(f"Side value received: '{side_value}'")

        try:
            api_key = BINANCE_API_KEY
            api_secret = BINANCE_API_SECRET
            print(f"DEBUG: Using embedded BINANCE_API_KEY: {'[SET]' if api_key else '[NOT SET]'}")
            print(f"DEBUG: Using embedded BINANCE_API_SECRET: {'[SET]' if api_secret else '[NOT SET]'}")

            if not api_key or not api_secret:
                raise ValueError("Binance API Key or Secret not properly set in code.")

            client = Client(api_key, api_secret)
        except Exception as e:
            print(f"Binance API Client initialization error: {e}")
            return jsonify({"status": "error", "message": "API Client init error"}), 500

        symbol = data.get('ticker')

        # quantity string olarak da gelebilir, sayı da olabilir → her iki durumu da kontrol ediyoruz
        quantity_raw = data.get('quantity')
        if isinstance(quantity_raw, str):
            quantity_str = quantity_raw.replace(",", ".")
        else:
            quantity_str = str(quantity_raw)

        try:
            quantity = float(quantity_str)
        except ValueError:
            print(f"Error converting quantity to float: {quantity_raw}")
            return jsonify({"status": "error", "message": f"Invalid quantity format: {quantity_raw}"}), 400

        if side_value == "BUY" or side_value == "SELL":
            try:
                order = client.new_order(symbol=symbol, side=side_value, type='MARKET', quantity=quantity)
                print(f"Order placed successfully: {order}")
                return jsonify({"status": "success", "message": "Order placed"}), 200
            except Exception as e:
                print(f"Error placing order with Binance API: {e}")
                return jsonify({"status": "error", "message": str(e)}), 400
        else:
            print(f"Invalid side value received from TradingView: {side_value}. Not placing order.")
            return jsonify({"status": "error", "message": f"Invalid side value received: {side_value}"}), 400
    else:
        return jsonify({"status": "error", "message": "Request must be JSON"}), 400

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
