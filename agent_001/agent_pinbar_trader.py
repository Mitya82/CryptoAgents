"""agent_pinbar_trader.py - Полный торговый агент на основе сигнала пин-бар.

Получает свечи с биржи, определяет тренд, ищет сигналы пин-бара и выставляет ордера.
"""

import argparse
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import ccxt


def create_exchange(exchange_id: str = "mexc") -> Any:
    """Создать объект биржи по id из ccxt."""
    try:
        exchange_cls = getattr(ccxt, exchange_id)
    except AttributeError:
        raise ValueError(f"Exchange '{exchange_id}' not found in ccxt")
    return exchange_cls()


def fetch_ohlcv(exchange: Any, symbol: str, timeframe: str = "1h",
                limit: int = 100) -> List[List]:
    """Загрузить OHLCV свечи с биржи."""
    try:
        exchange.load_markets()
    except Exception:
        pass

    candles = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    if not candles:
        raise ValueError(f"No candles fetched for {symbol} on {timeframe}")

    logging.debug(
        f"Загружено {
            len(candles)} свечей для {symbol} на {timeframe}")
    return candles


def calculate_sma(candles: List[List], period: int = 20,
                  price_index: int = 4) -> Optional[float]:
    """Вычислить простую скользящую среднюю (SMA)."""
    if len(candles) < period:
        logging.warning(
            f"Недостаточно данных для SMA({period}): есть только {
                len(candles)} свечей")
        return None

    sma = sum([candle[price_index] for candle in candles[-period:]]) / period
    return sma


def calculate_ema(candles: List[List], period: int = 12,
                  price_index: int = 4) -> Optional[float]:
    """Вычислить экспоненциальную скользящую среднюю (EMA)."""
    if len(candles) < period:
        logging.warning(
            f"Недостаточно данных для EMA({period}): есть только {
                len(candles)} свечей")
        return None

    multiplier = 2 / (period + 1)
    ema = calculate_sma(candles, period, price_index)

    if ema is None:
        return None

    # Упрощённо: используем первый расчёт как SMA
    for candle in candles[-period + 1:]:
        ema = candle[price_index] * multiplier + ema * (1 - multiplier)

    return ema


def determine_trend(
        candles: List[List], fast_period: int = 9, slow_period: int = 21) -> str:
    """Определить текущий тренд на основе EMA."""
    if len(candles) < slow_period:
        logging.warning("Недостаточно данных для определения тренда")
        return "sideways"

    ema_fast = calculate_ema(candles, fast_period)
    ema_slow = calculate_ema(candles, slow_period)

    if ema_fast is None or ema_slow is None:
        return "sideways"

    current_close = candles[-1][4]

    # Логика определения тренда
    if ema_fast > ema_slow and current_close > ema_fast:
        return "uptrend"
    elif ema_fast < ema_slow and current_close < ema_fast:
        return "downtrend"
    else:
        return "sideways"


def check_pinbar_buy_signal(previous_candle: List,
                            trend_direction: str = "uptrend") -> bool:
    """
    Проверяет, является ли предыдущая свеча сигнальной для покупки по правилу 'пин-бар в тренде'.

    Args:
        previous_candle (list): Данные предыдущей свечи [timestamp, open, high, low, close, volume].
        trend_direction (str): Направление тренда ('uptrend', 'downtrend', 'sideways').

    Returns:
        bool: True если сигнал на покупку, иначе False.
    """
    open_price = previous_candle[1]
    low_price = previous_candle[3]
    close_price = previous_candle[4]

    # Сигнал актуален только для аптренда
    if trend_direction != "uptrend":
        return False

    # Проверяем, что свеча медвежья (красная): закрытие ниже открытия
    is_bearish = close_price < open_price
    if not is_bearish:
        return False

    # Вычисляем тело свечи и тени
    body_size = abs(close_price - open_price)
    lower_shadow = min(open_price, close_price) - low_price

    # Главное условие: нижняя тень >= половине тела свечи
    if lower_shadow >= (body_size / 2):
        logging.info(
            f"[ПИН-БАР] Тело: {body_size:.8f}, Нижняя тень: {lower_shadow:.8f}")
        return True

    return False


def check_pinbar_sell_signal(previous_candle: List,
                             trend_direction: str = "downtrend") -> bool:
    """Проверяет сигнал пин-бара для продажи (в нисходящем тренде)."""
    open_price = previous_candle[1]
    high_price = previous_candle[2]
    close_price = previous_candle[4]

    if trend_direction != "downtrend":
        return False

    # Проверяем, что свеча бычья (зелёная): закрытие выше открытия
    is_bullish = close_price > open_price
    if not is_bullish:
        return False

    body_size = abs(close_price - open_price)
    upper_shadow = high_price - max(open_price, close_price)

    if upper_shadow >= (body_size / 2):
        logging.info(
            f"[ПИН-БАР ПРОДАЖА] Тело: {body_size:.8f}, Верхняя тень: {upper_shadow:.8f}")
        return True

    return False


def place_buy_order(exchange: Any, symbol: str, amount: float,
                    price: Optional[float] = None) -> Dict[str, Any]:
    """Разместить ордер на покупку."""
    try:
        if price:
            order = exchange.create_limit_buy_order(symbol, amount, price)
        else:
            order = exchange.create_market_buy_order(symbol, amount)

        logging.info(
            f"✅ ОРДЕР НА ПОКУПКУ: {symbol} x{amount} @ {price or 'MARKET'}")
        logging.info(f"Order ID: {order.get('id')}")
        return order
    except Exception as e:
        logging.error(f"❌ Ошибка при размещении ордера на покупку: {e}")
        return {}


def place_sell_order(exchange: Any, symbol: str, amount: float,
                     price: Optional[float] = None) -> Dict[str, Any]:
    """Разместить ордер на продажу."""
    try:
        if price:
            order = exchange.create_limit_sell_order(symbol, amount, price)
        else:
            order = exchange.create_market_sell_order(symbol, amount)

        logging.info(
            f"✅ ОРДЕР НА ПРОДАЖУ: {symbol} x{amount} @ {price or 'MARKET'}")
        logging.info(f"Order ID: {order.get('id')}")
        return order
    except Exception as e:
        logging.error(f"❌ Ошибка при размещении ордера на продажу: {e}")
        return {}


def run_trading_loop(
    exchange_id: str = "mexc",
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    interval: int = 60,
    trade_amount: float = 0.001,
    demo_mode: bool = True,
) -> None:
    """
    Основной торговый цикл агента.

    Args:
        exchange_id: ID биржи (mexc, binance, etc.)
        symbol: Торговая пара (BTC/USDT, ETH/USDT и т.д.)
        timeframe: Таймфрейм для свечей (1h, 4h, 1d, etc.)
        interval: Интервал проверки сигналов в секундах
        trade_amount: Размер позиции для торговли
        demo_mode: Если True, только логирует сигналы без реальных ордеров
    """
    logging.info("=" * 60)
    logging.info(f"АГЕНТ ПИН-БАР: ЗАПУСК")
    logging.info(
        f"Биржа: {
            exchange_id.upper()}, Пара: {symbol}, TF: {timeframe}")
    logging.info(f"Режим: {'ДЕМО' if demo_mode else 'РЕАЛЬНАЯ ТОРГОВЛЯ'}")
    logging.info("=" * 60)

    try:
        exchange = create_exchange(exchange_id)
        logging.info(
            f"✅ Подключено к: {
                getattr(
                    exchange,
                    'name',
                    exchange_id)}")

        iteration = 0
        last_signal_candle_time = None

        while True:
            iteration += 1
            time_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

            try:
                # Получаем свечи
                candles = fetch_ohlcv(exchange, symbol, timeframe, limit=100)

                # Определяем тренд
                trend = determine_trend(candles)
                current_close = candles[-1][4]
                current_time = candles[-1][0]

                logging.info(
                    f"\n[{iteration}] {time_str} | Тренд: {
                        trend.upper()} | Цена: ${
                        current_close:.2f}")

                # Проверяем сигналы только на предыдущей закрытой свече
                if current_time != last_signal_candle_time and len(
                        candles) >= 2:
                    previous_candle = candles[-2]

                    # Проверяем сигнал на покупку
                    if check_pinbar_buy_signal(previous_candle, trend):
                        logging.warning(f"🚀 СИГНАЛ НА ПОКУПКУ ОБНАРУЖЕН!")
                        if not demo_mode:
                            place_buy_order(exchange, symbol, trade_amount)
                        last_signal_candle_time = current_time

                    # Проверяем сигнал на продажу
                    elif check_pinbar_sell_signal(previous_candle, trend):
                        logging.warning(f"🔴 СИГНАЛ НА ПРОДАЖУ ОБНАРУЖЕН!")
                        if not demo_mode:
                            place_sell_order(exchange, symbol, trade_amount)
                        last_signal_candle_time = current_time

            except Exception as e:
                logging.error(f"❌ Ошибка в цикле: {e}", exc_info=False)

            # Ждём перед следующей проверкой
            logging.debug(f"Ждём {interval} сек до следующей проверки...")
            time.sleep(interval)

    except KeyboardInterrupt:
        logging.info("\n⚠️  Цикл прерван пользователем (Ctrl+C)")
    except Exception as e:
        logging.error(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", exc_info=True)
    finally:
        logging.info("=" * 60)
        logging.info("АГЕНТ ПИН-БАР: ОСТАНОВЛЕН")
        logging.info("=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Торговый агент на основе сигнала пин-бар"
    )
    parser.add_argument("--exchange", "-e", default="mexc",
                        help="ccxt exchange id (default: mexc)")
    parser.add_argument(
        "--symbol",
        "-s",
        default="BTC/USDT",
        help="Market symbol (default: BTC/USDT)")
    parser.add_argument("--timeframe", "-tf", default="1h",
                        help="Candle timeframe (default: 1h)")
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=60,
        help="Check interval in seconds (default: 60)")
    parser.add_argument(
        "--amount",
        "-a",
        type=float,
        default=0.001,
        help="Trade amount (default: 0.001)")
    parser.add_argument(
        "--trade",
        action="store_true",
        help="Enable real trading (default: demo mode)")
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging")

    args = parser.parse_args()

    # Настройка логирования
    log_level = logging.DEBUG if args.debug else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%H:%M:%S"
    )

    # Запуск торгового цикла
    run_trading_loop(
        exchange_id=args.exchange,
        symbol=args.symbol,
        timeframe=args.timeframe,
        interval=args.interval,
        trade_amount=args.amount,
        demo_mode=not args.trade,
    )


if __name__ == "__main__":
    main()
