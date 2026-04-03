import ccxt
import time
import os
import logging
import csv
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from telegram_notifier import TelegramNotifier
import pandas as pd

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Константы настроек сигналов
BB_LENGTH = 20
BB_STD = 2
STOCH_K = 14
STOCH_D = 3

# Загружаем переменные окружения из .env файла
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# --- настройки ---
# Список пар для отслеживания
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
EXCHANGE = os.getenv('EXCHANGE', 'mexc')
INTERVAL = 5 * 60                # опрашиваем биржу каждые 5 минут (300 сек)
TIMEFRAME = '5m'                # таймфрейм котировок
# минимальный интервал между отправками (15 минут)
NOTIFY_INTERVAL = 15 * 60
PRICE_CHANGE_THRESHOLD = 0.005   # 0.5% от цены последнего уведомления
DEMO = True
CSV_SIGNALS_FILE = Path(__file__).parent.parent / 'data' / 'signals.csv'

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
        logger.error(f"❌ Ошибка инициализации биржи: {e}")
        raise


def get_price(exchange, symbol):
    ticker = exchange.fetch_ticker(symbol)
    return ticker['last']


def calculate_bollinger_bands(close, length=BB_LENGTH, std=BB_STD):
    sma = close.rolling(length).mean()
    std_dev = close.rolling(length).std()
    upper = sma + std * std_dev
    lower = sma - std * std_dev
    return lower, sma, upper


def calculate_stochastic(high, low, close, k_period=STOCH_K, d_period=STOCH_D):
    lowest_low = low.rolling(k_period).min()
    highest_high = high.rolling(k_period).max()
    k = 100 * (close - lowest_low) / (highest_high - lowest_low)
    d = k.rolling(d_period).mean()
    return k, d


# НОВАЯ ФУНКЦИЯ СИЛЫ СИГНАЛА
def get_signal_strength(current_price, bb_lower, bb_upper, stoch_k, signal_type):
    """
    Сила сигнала от 0.0 (слабый) до 1.0 (очень сильный)
    """
    # Проверка исходных данных
    if current_price is None or bb_lower is None or bb_upper is None or stoch_k is None:
        logger.warning('Неверные данные для расчета силы сигнала: None')
        return 0.0

    bb_range = bb_upper - bb_lower
    if bb_range == 0:
        logger.warning('Деление на ноль в расчете Bollinger Bands position')
        return 0.0

    # Нормализуем положение цены относительно BB (0-1)
    bb_position = (current_price - bb_lower) / bb_range
    bb_position = max(0.0, min(1.0, bb_position))  # за пределами диапазона ограничиваем

    if signal_type == 'long':
        # Для LONG: чем ниже цена относительно BB и Stoch, тем сильнее
        bb_strength = max(0.0, 1.0 - bb_position)  # 1.0 если цена = bb_lower
        stoch_strength = max(0.0, min(1.0, (20.0 - stoch_k) / 20.0))
    else:  # short
        # Для SHORT: чем выше цена относительно BB и Stoch, тем сильнее
        bb_strength = max(0.0, min(1.0, (bb_position - 0.5) * 2.0))  # 1.0 если цена = bb_upper
        stoch_strength = max(0.0, min(1.0, (stoch_k - 80.0) / 20.0))

    # Итоговая сила = среднее двух индикаторов
    strength = (bb_strength + stoch_strength) / 2.0
    return round(min(strength, 1.0), 2)  # 0.0-1.0


def save_signal_to_csv(symbol, signal_type, strength, current_price, bb_lower, bb_upper, stoch_k):
    """
    Сохраняет информацию о сигнале в CSV файл
    """
    try:
        csv_file = CSV_SIGNALS_FILE
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_exists = csv_file.exists()
        
        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['timestamp', 'symbol', 'signal_type', 'strength', 
                               'price', 'bb_lower', 'bb_upper', 'stoch_k'])
            
            writer.writerow([
                datetime.now().isoformat(),
                symbol,
                signal_type,
                strength,
                f'{current_price:.2f}',
                f'{bb_lower:.2f}',
                f'{bb_upper:.2f}',
                f'{stoch_k:.2f}'
            ])
        logger.info(f"✅ Сигнал сохранён в CSV: {symbol} {signal_type} {strength*100:.0f}%")
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения CSV: {e}")


def run():
    # Проверяем наличие необходимых токенов
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        raise ValueError(
            "❌ Ошибка! Токены Telegram не найдены. "
            "Убедитесь, что файл .env существует и содержит TELEGRAM_TOKEN и TELEGRAM_CHAT_ID"
        )

    logger.info(f"🤖 Агент запущен. Отслеживаем пары: {', '.join(SYMBOLS)}")
    logger.info(f"📊 Режим: {'ДЕМО' if DEMO else 'РЕАЛЬНЫЙ'}")
    logger.info("-" * 50)

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
            'last_signal': None,
            'last_indicators_time': 0.0
        }

    while True:
        try:
            now = time.time()
            ts = datetime.now().strftime("%H:%M:%S")

            # Получаем OHLCV данные для всех пар
            for symbol in SYMBOLS:
                try:
                    ohlcv = exchange.fetch_ohlcv(symbol, TIMEFRAME, limit=100)
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
            logger.info(f"[{ts}] {' | '.join(price_strings)}")

            # === НОВЫЙ БЛОК ПРОВЕРКИ СИГНАЛОВ ===
            for symbol in SYMBOLS:
                if candles_data[symbol]:
                    df = pd.DataFrame(
                        candles_data[symbol],
                        columns=['timestamp','open','high','low','close','volume'])
                    bb_lower, bb_middle, bb_upper = calculate_bollinger_bands(df['close'])
                    stoch_k, stoch_d = calculate_stochastic(df['high'], df['low'], df['close'])
                    current_price = prices[symbol]

                    if current_price is None:
                        logger.warning(f"Цена для {symbol} отсутствует. Пропуск сигнала.")
                        continue

                    if len(bb_lower) > 0 and len(stoch_k) > 0:
                        last_bb_lower = bb_lower.iloc[-1]
                        last_bb_upper = bb_upper.iloc[-1]
                        last_stoch_k = stoch_k.iloc[-1]
                        state = symbol_states[symbol]
                        current_signal = None

                        # LONG сигнал
                        if current_price < last_bb_lower and last_stoch_k < 20:
                            strength = get_signal_strength(
                                current_price, last_bb_lower, last_bb_upper, last_stoch_k, 'long')
                            current_signal = f'long_{strength}'

                            if state.get('last_signal') != current_signal:
                                msg = (f"🟢 LONG {symbol} **{strength*100:.0f}%**\n"
                                       f"💰 Цена: ${current_price:.2f} (BB_low: ${last_bb_lower:.2f})\n"
                                       f"📉 Stoch: {last_stoch_k:.1f}\n"
                                       f"⚡ СИЛА: {strength*100:.0f}%")
                                logger.info(msg)
                                notifier.send_sync(msg)
                                save_signal_to_csv(symbol, 'long', strength, current_price, 
                                                 last_bb_lower, last_bb_upper, last_stoch_k)
                                state['last_signal'] = current_signal

                        # SHORT сигнал
                        elif current_price > last_bb_upper and last_stoch_k > 80:
                            strength = get_signal_strength(
                                current_price, last_bb_lower, last_bb_upper, last_stoch_k, 'short')
                            current_signal = f'short_{strength}'

                            if state.get('last_signal') != current_signal:
                                msg = (f"🔴 SHORT {symbol} **{strength*100:.0f}%**\n"
                                       f"💰 Цена: ${current_price:.2f} (BB_up: ${last_bb_upper:.2f})\n"
                                       f"📈 Stoch: {last_stoch_k:.1f}\n"
                                       f"⚡ СИЛА: {strength*100:.0f}%")
                                logger.info(msg)
                                notifier.send_sync(msg)
                                save_signal_to_csv(symbol, 'short', strength, current_price, 
                                                 last_bb_lower, last_bb_upper, last_stoch_k)
                                state['last_signal'] = current_signal

                        # Сброс слабых сигналов
                        if current_signal is None and state.get('last_signal'):
                            state['last_signal'] = None

            # ВЫВОД ИНДИКАТОРОВ (раз в 15 минут)
            for symbol in SYMBOLS:
                if candles_data[symbol]:
                    state = symbol_states[symbol]
                    if now - state.get('last_indicators_time', 0) >= 15 * 60:
                        df = pd.DataFrame(
                            candles_data[symbol],
                            columns=[
                                'timestamp',
                                'open',
                                'high',
                                'low',
                                'close',
                                'volume'])
                        bb_lower, bb_middle, bb_upper = calculate_bollinger_bands(df['close'])
                        stoch_k, stoch_d = calculate_stochastic(df['high'], df['low'], df['close'])
                        if len(bb_lower) > 0 and len(stoch_k) > 0:
                            logger.info(f"[{ts}] {symbol} BB: L={bb_lower.iloc[-1]:.2f}, M={bb_middle.iloc[-1]:.2f}, U={bb_upper.iloc[-1]:.2f} | STOCH: K={stoch_k.iloc[-1]:.2f}, D={stoch_d.iloc[-1]:.2f}")
                            state['last_indicators_time'] = now
                        else:
                            logger.info(f"[{ts}] {symbol}: Недостаточно данных для индикаторов")

            # ПРОВЕРКА УВЕДОМЛЕНИЙ
            for symbol in SYMBOLS:
                price = prices[symbol]
                if price is None:
                    continue
                state = symbol_states[symbol]
                send = False
                reason = ''

                if state['last_notify_price'] is None or now - \
                        state['last_notify_time'] >= NOTIFY_INTERVAL:
                    send = True
                    reason = f'таймер {NOTIFY_INTERVAL // 60} мин'
                else:
                    change = abs(
                        price - state['last_notify_price']) / state['last_notify_price']
                    if change > PRICE_CHANGE_THRESHOLD:
                        send = True
                        reason = f'изменение {change * 100:.2f}%'

                if send:
                    msg = f"📊 {symbol}: ${price:.2f}"
                    if state['last_notify_price'] is not None:
                        diff = (
                            price - state['last_notify_price']) / state['last_notify_price'] * 100
                        msg += f" ({diff:+.2f}%)"
                    msg += f" | {reason}"
                    notifier.send_sync(msg)
                    state['last_notify_time'] = now
                    state['last_notify_price'] = price

        except Exception as e:
            err = f"❌ Ошибка: {e}"
            logger.error(err)
            notifier.send_sync(err)

        time.sleep(INTERVAL)


if __name__ == "__main__":
    run()
