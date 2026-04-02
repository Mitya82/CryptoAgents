## TODO: Интеграция Telegram уведомлений

### Задача:
Добавить отправку уведомлений в Telegram когда:
- Цена изменилась на X%
- Срабатывает торговый сигнал
- Произошла ошибка

### Этапы реализации:
1. Создать бота в Telegram (@BotFather)
2. Получить TOKEN и CHAT_ID
3. Установить библиотеку: `pip install python-telegram-bot`
4. Создать файл `telegram_notifier.py`
5. Интегрировать в `agent_base_v1.py`

### Ссылки:
- https://core.telegram.org/bots/tutorial
- https://github.com/python-telegram-bot/python-telegram-bot

### Статус: ⏳ В очереди