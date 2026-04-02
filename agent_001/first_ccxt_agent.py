import ccxt

# 1. Создаём объект биржи MEXC
exchange = ccxt.hyperliquid()

# 2. Выбираем торговую пару
symbol = 'BTC/USDC:USDC'

try:
    # 3. Получаем текущий тикер (информацию о цене)
    ticker = exchange.fetch_ticker(symbol)

    # 4. Извлекаем из тикера последнюю цену
    price = ticker['last']

    # 5. Выводим результат
    print(f"💰 Текущая цена {symbol} на hyperliquid: ${price}")

except Exception as e:
    print(f"❌ Ошибка при получении данных: {e}")