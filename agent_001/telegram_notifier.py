# filepath: c:\Code\CryptoAgents\agent_001\telegram_notifier.py
import requests


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.url = f'https://api.telegram.org/bot{token}/sendMessage'
        self.chat_id = chat_id

    def send_sync(self, message: str) -> None:
        try:
            resp = requests.post(self.url,
                                 data={
                                     'chat_id': self.chat_id, 'text': message},
                                 timeout=10)
            resp.raise_for_status()
            print(f"📨 Уведомление отправлено: {message}")
        except Exception as e:
            print(f"❌ Ошибка отправки: {e}")
