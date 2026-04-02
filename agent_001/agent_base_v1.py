import ccxt
import time
import os
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram_notifier import TelegramNotifier
from config import Config
import pandas as pd

# Загружаем переменные окружения из .env файла
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# --- настройки ---
# Список пар для отслеживания
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
EXCHANGE = os.getenv('EXCHANGE', 'mexc')
INTERVAL = 60                    # опрашиваем биржу каждую минуту
NOTIFY_INTERVAL = 15 * 60        # минимальный интервал между отправками (15 минут)
PRICE_CHANGE_THRESHOLD = 0.005   # 0.5% от цены последнего уведомления
DEMO = True

# Загружаем токены из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
# ------------------

def init_exchange():
    try:
        exchange = getattr(ccxt, EXCHANGE)({
            'enableRateLimit': True,
        })
        exchange.load_markets()
        return exchange
    except Exception as e:
        print(f"❌ Ошибка инициализации биржи: {e}")
        raise

def get_price(exchange, symbol):
    ticker = exchange.fetch_ticker(symbol)
    return ticker['last']

def calculate_bollinger_bands(close, length=20, std=2):
    sma = close.rolling(length).mean()
    std_dev = close.rolling(length).std()
    upper = sma + std * std_dev
    lower = sma - std * std_dev
    return lower, sma, upper

def calculate_stochastic(high, low, close, k_period=14, d_period=3):
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(d_period).mean()
    return k, d

def run():
    # Проверяем наличие необходимых токенов
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError(
            "❌ Ошибка! Токены Telegram не найдены. "
            "Убедитесь, что файл .env существует и содержит TELEGRAM_TOKEN и TELEGRAM_CHAT_ID"
        )
    
    print(f"🤖 Агент запущен. Отслеживаем пары: {', '.join(SYMBOLS)}")
    print(f"📊 Режим: {'ДЕМО' if DEMO else 'РЕАЛЬНЫЙ'}") 
    print("-" * 50)

    exchange = init_exchange()
    notifier = TelegramNotifier(TELEGRAM_TOKEN, TELEGRAM_CHAT_ID)
    notifier.send_sync(f"🤖 Агент стартовал, отслеживаем: {', '.join(SYMBOLS)}")

    # Словарь для хранения OHLCV данных
    candles_data = {}

    # Словарь для хранения состояния каждой пары
    symbol_states = {}
    for symbol in SYMBOLS:
        symbol_states[symbol] = {
            'last_notify_time': 0.0,
            'last_notify_price': None,
            'last_signal': None
        }

    while True:
        try:
            now = time.time()
            ts = datetime.now().strftime("%H:%M:%S")
            
            # Получаем OHLCV данные для всех пар
            for symbol in SYMBOLS:
                try:
                    ohlcv = exchange.fetch_ohlcv(symbol, '1m', limit=100)
                    candles_data[symbol] = ohlcv
                except Exception as e:
                    print(f"❌ Ошибка получения OHLCV {symbol}: {e}")
                    candles_data[symbol] = []
            
            # Собираем цены всех пар
            prices = {}
            for symbol in SYMBOLS:
                try:
                    price = get_price(exchange, symbol)
                    prices[symbol] = price
                except Exception as e:
                    print(f"❌ Ошибка получения цены {symbol}: {e}")
                    prices[symbol] = None
            
            # Выводим цены в консоль
            price_strings = []
            for symbol, price in prices.items():
                if price is not None:
                    price_strings.append(f"{symbol}: ${price:.2f}")
                else:
                    price_strings.append(f"{symbol}: ОШИБКА")
            print(f"[{ts}] {' | '.join(price_strings)}")
            
            # ПРОВЕРКА СИГНАЛОВ
            for symbol in SYMBOLS:
                if candles_data[symbol]:
                    df = pd.DataFrame(candles_data[symbol], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    bb_lower, bb_middle, bb_upper = calculate_bollinger_bands(df['close'], length=20)
                    stoch_k, stoch_d = calculate_stochastic(df['high'], df['low'], df['close'], k_period=14, d_period=3)
                    current_price = prices[symbol]
                    
                    if len(bb_lower) > 0 and len(stoch_k) > 0:
                        last_bb_lower = bb_lower.iloc[-1]
                        last_bb_upper = bb_upper.iloc[-1]
                        last_stoch_k = stoch_k.iloc[-1]
                        state = symbol_states[symbol]
                        current_signal = None
                        
                        if current_price < last_bb_lower and last_stoch_k < 20:
                            current_signal = 'long'
                            if state.get('last_signal') != 'long':
                                msg = f"🟢 СИГНАЛ ЛОНГ {symbol}: цена ${current_price:.2f} ниже нижней полосы ({last_bb_lower:.2f}), стохастик {last_stoch_k:.1f} (перепродан)"
                                print(msg)
                                notifier.send_sync(msg)
                                state['last_signal'] = 'long'
                        elif current_price > last_bb_upper and last_stoch_k > 80:
                            current_signal = 'short'
                            if state.get('last_signal') != 'short':
                                msg = f"🔴 СИГНАЛ ШОРТ {symbol}: цена ${current_price:.2f} выше верхней полосы ({last_bb_upper:.2f}), стохастик {last_stoch_k:.1f} (перекуплен)"
                                print(msg)
                                notifier.send_sync(msg)
                                state['last_signal'] = 'short'
                        
                        if current_signal is None and state.get('last_signal') is not None:
                            state['last_signal'] = None
            
            # ВЫВОД ИНДИКАТОРОВ
            for symbol in SYMBOLS:
                if candles_data[symbol]:
                    df = pd.DataFrame(candles_data[symbol], columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    bb_lower, bb_middle, bb_upper = calculate_bollinger_bands(df['close'], length=20)
                    stoch_k, stoch_d = calculate_stochastic(df['high'], df['low'], df['close'], k_period=14, d_period=3)
                    if len(bb_lower) > 0 and len(stoch_k) > 0:
                        print(f"[{ts}] {symbol} BB: L={bb_lower.iloc[-1]:.2f}, M={bb_middle.iloc[-1]:.2f}, U={bb_upper.iloc[-1]:.2f} | STOCH: K={stoch_k.iloc[-1]:.2f}, D={stoch_d.iloc[-1]:.2f}")
                    else:
                        print(f"[{ts}] {symbol}: Недостаточно данных для индикаторов")
            
            # ПРОВЕРКА УВЕДОМЛЕНИЙ
            for symbol in SYMBOLS:
                price = prices[symbol]
                if price is None:
                    continue
                state = symbol_states[symbol]
                send = False
                reason = ''
                
                if state['last_notify_price'] is None or now - state['last_notify_time'] >= NOTIFY_INTERVAL:
                    send = True
                    reason = f'таймер {NOTIFY_INTERVAL // 60} мин'
                else:
                    change = abs(price - state['last_notify_price']) / state['last_notify_price']
                    if change > PRICE_CHANGE_THRESHOLD:
                        send = True
                        reason = f'изменение {change*100:.2f}%'
                
                if send:
                    msg = f"📊 {symbol}: ${price:.2f}"
                    if state['last_notify_price'] is not None:
                        diff = (price - state['last_notify_price']) / state['last_notify_price'] * 100
                        msg += f" ({diff:+.2f}%)"
                    msg += f" | {reason}"
                    notifier.send_sync(msg)
                    state['last_notify_time'] = now
                    state['last_notify_price'] = price
        
        except Exception as e:
            err = f"❌ Ошибка: {e}"
            print(err)
            notifier.send_sync(err)
        
        time.sleep(INTERVAL)

if __name__ == "__main__":
    run()