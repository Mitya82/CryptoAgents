"""agent_eyes.py - Подключение к бирже (refactored).

Вынесена логика в функции, добавлен CLI и логирование.
"""

from __future__ import annotations

import argparse
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import ccxt


DEFAULT_EXCHANGE = "binance"
DEFAULT_SYMBOL = "BTC/USDT"


def create_exchange(exchange_id: str = DEFAULT_EXCHANGE) -> Any:
    """Create and return a ccxt exchange instance by id."""
    try:
        exchange_cls = getattr(ccxt, exchange_id)
    except AttributeError:
        raise ValueError(f"Exchange '{exchange_id}' not found in ccxt")
    exchange = exchange_cls({"enableRateLimit": True})
    try:
        exchange.load_markets()
    except Exception:
        # not critical; some exchanges or ccxt builds may not require this
        pass
    return exchange


def fetch_ticker(exchange: Any, symbol: str) -> Dict[str, Any]:
    return exchange.fetch_ticker(symbol)


def signal_from_change(change: Optional[float]) -> str:
    if change is None:
        return "📢 СИГНАЛ: НЕТ ДАННЫХ ПО ИЗМЕНЕНИЮ"
    if change > 0:
        return "📢 СИГНАЛ: 🟢 РОСТ на рынке"
    return "📢 СИГНАЛ: 🔴 ПАДЕНИЕ на рынке"


def run(exchange_id: str = DEFAULT_EXCHANGE,
        symbol: str = DEFAULT_SYMBOL) -> None:
    logging.info("=" * 50)
    logging.info("АГЕНТ 001: ТЕСТ СВЯЗИ С РЫНКОМ")
    logging.info("=" * 50)

    try:
        exchange = create_exchange(exchange_id)
        logging.info("✅ Биржа: %s", getattr(exchange, "name", exchange_id))

        ticker = fetch_ticker(exchange, symbol)

        price = ticker.get("last")
        change = ticker.get("percentage")
        time = datetime.now(timezone.utc).strftime("%H:%M:%S")

        logging.info("🕒 Время (UTC): %s", time)

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

    except Exception as e:
        logging.error("❌ ОШИБКА: %s", e)
        logging.debug("Подробный трейс ошибки:", exc_info=True)

    finally:
        logging.info("=" * 50)
        logging.info("ТЕСТ ЗАВЕРШЁН")
        logging.info("=" * 50)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Agent 001: simple market connectivity test via ccxt")
    parser.add_argument(
        "--exchange",
        "-e",
        default=DEFAULT_EXCHANGE,
        help="ccxt exchange id (default: binance)")
    parser.add_argument(
        "--symbol",
        "-s",
        default=DEFAULT_SYMBOL,
        help="Market symbol (default: BTC/USDT)")
    args = parser.parse_args()

    run(exchange_id=args.exchange, symbol=args.symbol)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    main()
