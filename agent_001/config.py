"""config.py - Конфигурация приложения с поддержкой переменных окружения."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем .env файл из родительской директории
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)


class Config:
    """Класс конфигурации с валидацией."""
    
    # Telegram
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')
    
    # Exchange
    EXCHANGE = os.getenv('EXCHANGE', 'mexc')
    SYMBOL = os.getenv('SYMBOL', 'ETH/USDT')
    
    # Intervals (in seconds)
    PRICE_CHECK_INTERVAL = int(os.getenv('PRICE_CHECK_INTERVAL', 60))
    NOTIFY_INTERVAL = int(os.getenv('NOTIFY_INTERVAL', 900))  # 15 min
    
    # Thresholds
    PRICE_CHANGE_THRESHOLD = float(os.getenv('PRICE_CHANGE_THRESHOLD', 0.03))
    
    # Mode
    DEMO = os.getenv('DEMO', 'True').lower() == 'true'
    
    @classmethod
    def validate(cls) -> bool:
        """Проверить обязательные параметры."""
        if not cls.TELEGRAM_TOKEN:
            raise ValueError("❌ TELEGRAM_TOKEN не установлен в .env файле!")
        if not cls.TELEGRAM_CHAT_ID:
            raise ValueError("❌ TELEGRAM_CHAT_ID не установлен в .env файле!")
        return True
    
    @classmethod
    def get_summary(cls) -> str:
        """Получить сводку конфигурации для логирования."""
        cls.validate()
        return f"""
        🔧 Конфигурация:
        - Биржа: {cls.EXCHANGE}
        - Пара: {cls.SYMBOL}
        - Интервал проверки: {cls.PRICE_CHECK_INTERVAL}s
        - Интервал уведомления: {cls.NOTIFY_INTERVAL}s
        - Порог изменения: {cls.PRICE_CHANGE_THRESHOLD * 100}%
        - Режим: {'ДЕМО' if cls.DEMO else 'РЕАЛЬНЫЙ'}
        """
