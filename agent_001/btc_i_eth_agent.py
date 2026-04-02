"""agent_eyes_mexc.py - Подключение к бирже через ccxt (refactored).

Вынесена логика в функции, добавлен CLI и логирование.
"""

import argparse
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import ccxt


def create_exchange(exchange_id: str = "mexc") -> Any:
    """Создать объект биржи по id из ccxt."""
    try:
        exchange_cls = getattr(ccxt, exchange_id)
    except AttributeError:
        raise ValueError(f"Exchange '{exchange_id}' not found in ccxt")
    return exchange_cls()


def fetch_ticker(exchange: Any, symbol: str) -> Dict[str, Any]:
    """Загрузить рынки (safely) и получить тикер для символа."""
    try:
        # load_markets помогает избежать ленивых загрузок в некоторых реализациях
        exchange.load_markets()
    except Exception:
        # не критично — некоторые адаптеры не требуют загрузки рынков
        pass
    return exchange.fetch_ticker(symbol)


def signal_from_change(change: Optional[float]) -> str:
    if change is None:
        return "📢 СИГНАЛ: НЕТ ДАННЫХ ПО ИЗМЕНЕНИЮ"
    if change > 1.0:
        return "📢 СИГНАЛ: 🚀 СИЛЬНЫЙ РОСТ (>1%)"
    if change > 0:
        return "📢 СИГНАЛ: 🟢 ЛЁГКИЙ РОСТ"
    if change > -1.0:
        return "📢 СИГНАЛ: 🔴 ЛЁГКОЕ ПАДЕНИЕ"
    return "📢 СИГНАЛ: 🩸 СИЛЬНОЕ ПАДЕНИЕ (<-1%)"


def run(exchange_id: str = "mexc", symbol: str = "BTC/USDT") -> None:
    logging.info("=" * 50)
    logging.info("АГЕНТ 001: ПОДКЛЮЧЕНИЕ К %s", exchange_id.upper())
    logging.info("=" * 50)

    try:
        exchange = create_exchange(exchange_id)
        logging.info("✅ Биржа: %s", getattr(exchange, "name", exchange_id))

        time = datetime.now(timezone.utc).strftime("%H:%M:%S")
        logging.info("🕒 Время (UTC): %s", time)

        # Fetch BTC/USDT
        ticker = fetch_ticker(exchange, symbol)

        price = ticker.get("last")
        change = ticker.get("percentage")

        if price is not None:
            try:
                logging.info("💰 %s: $%.2f", symbol, float(price))
            except Exception:
                logging.info("💰 %s: %s", symbol, price)
        else:
            logging.warning("Цена отсутствует в ответе тикера")

        if change is not None:
            try:
                logging.info("📈 Изменение 24ч: %.2f%%", float(change))
            except Exception:
                logging.info("📈 Изменение 24ч: %s", change)
        else:
            logging.info("📈 Изменение 24ч: N/A")

        logging.info(signal_from_change(change))

        # Fetch ETH/USDT
        logging.info("-" * 50)
        eth_symbol = "ETH/USDT"
        try:
            eth_ticker = fetch_ticker(exchange, eth_symbol)
            eth_price = eth_ticker.get("last")
            eth_change = eth_ticker.get("percentage")

            if eth_price is not None:
                try:
                    logging.info("💰 %s: $%.2f", eth_symbol, float(eth_price))
                except Exception:
                    logging.info("💰 %s: %s", eth_symbol, eth_price)
            else:
                logging.warning("Цена ETH отсутствует в ответе тикера")

            if eth_change is not None:
                try:
                    logging.info("📈 Изменение 24ч: %.2f%%", float(eth_change))
                except Exception:
                    logging.info("📈 Изменение 24ч: %s", eth_change)
            else:
                logging.info("📈 Изменение 24ч: N/A")

            logging.info(signal_from_change(eth_change))
        except Exception as e:
            logging.error("❌ ОШИБКА при получении ETH/USD: %s", e)

    except Exception as e:
        logging.error("❌ ОШИБКА: %s", e)
        logging.debug("Подробный трейс ошибки:", exc_info=True)

    finally:
        logging.info("=" * 50)
        logging.info("АГЕНТ 001: РАЗВЕДКА ЗАВЕРШЕНА")
        logging.info("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(description="Agent 001: fetch ticker from exchange via ccxt")
    parser.add_argument("--exchange", "-e", default="mexc", help="ccxt exchange id (default: mexc)")
    parser.add_argument("--symbol", "-s", default="BTC/USDT", help="Market symbol (default: BTC/USDT)")
    args = parser.parse_args()

    run(exchange_id=args.exchange, symbol=args.symbol)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()