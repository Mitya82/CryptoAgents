# получить текущую цену биткоина в долларах США с биржи и вывести на консоль
import requests
import urllib3
from urllib3.exceptions import InsecureRequestWarning

# Отключаем предупреждения о SSL
urllib3.disable_warnings(InsecureRequestWarning)


def get_btc_price():
    # MEXC API для получения цены BTC
    url = 'https://api.mexc.com/api/v3/ticker/price?symbol=BTCUSDT'
    try:
        response = requests.get(url, verify=False, timeout=10)
        response.raise_for_status()
        data = response.json()
        price = float(data['price'])
        return price
    except Exception as e:
        print(f"Ошибка при получении данных с MEXC: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    btc_price = get_btc_price()
    if btc_price:
        print(f"Текущая цена биткоина: ${btc_price}")
    else:
        print("Не удалось получить цену биткоина")
