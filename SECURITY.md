# 🔒 Руководство по безопасности токенов

## Проблема: Утечка учетных данных

Хранение токенов и ID прямо в коде (захардкодирование) - это **критическая уязвимость**:

❌ **Опасно:**
```python
Удалён скомпрометированный токен
TELEGRAM_CHAT_ID = '520421965'
```

**Почему это плохо:**
- Если закоммитить в Git, токен видят все разработчики
- Если репозиторий на GitHub, токен доступен в истории даже после удаления
- Любой с доступом к коду может использовать ваши токены

---

## ✅ Решение: Переменные окружения + .env файл

### Как это работает:

1. **Создается файл `.env`** (НЕ комитится в git):
```
TELEGRAM_TOKEN=ваш_токен_здесь
TELEGRAM_CHAT_ID=ваш_id_здесь
```

2. **Код загружает из окружения:**
```python
import os
from dotenv import load_dotenv

load_dotenv('.env')
TOKEN = os.getenv('TELEGRAM_TOKEN')
```

3. **.gitignore защищает .env:**
```
.env          # ← не комитится!
.env.local
```

---

## 🚀 Инструкция по внедрению

### 1️⃣ Установка зависимостей

```bash
pip install -r requirements.txt
```

Или вручную:
```bash
pip install python-dotenv requests ccxt
```

### 2️⃣ Создание файла `.env`

В папке `CryptoAgents/` создайте файл `.env`:

```
TELEGRAM_TOKEN=8781984176:AAHKR6VHGXrVeRcfdp2rshGyOUWPpl6k6LI
TELEGRAM_CHAT_ID=520421965
EXCHANGE=mexc
SYMBOL=ETH/USDT
DEMO=True
```

### 3️⃣ Использование в коде

**Старый способ (опасно):**
```python
TELEGRAM_TOKEN = '8781984176:AAHKR6...'  # Опасно!
```

**Новый способ (безопасно):**
```python
from config import Config

Config.validate()  # Проверка на наличие токенов
TOKEN = Config.TELEGRAM_TOKEN
CHAT_ID = Config.TELEGRAM_CHAT_ID
```

---

## 🛡️ Проверка безопасности

**ПередCommit проверьте:**

```bash
# Посмотреть, что будет закоммичено
git diff --cached

# Убедитесь, что .env НЕ в списке!
# Если .env случайно добавлен, удалите:
git rm --cached .env
```

---

## 📋 Разные окружения (Development, Production)

Создавайте разные `.env` файлы:

```
.env              # локальная разработка
.env.production   # production (на сервере)
.env.staging      # staging
```

**Загрузка нужного окружения:**
```python
import os
env_file = f".env.{os.getenv('APP_ENV', 'local')}"
load_dotenv(env_file)
```

---

## 🔄 Если токен уже утек (в истории Git)

### 1. Немедленно воссоздайте токен в Telegram:
- Перейдите в @BotFather
- Используйте `/revoke` чтобы аннулировать старый токен
- Создайте новый токен

### 2. Очистите историю Git:

```bash
# Найти все commits с токеном
git log -S "8781984176" --oneline

# Переписать историю (ОПАСНО! Только если не pushed на сервер)
git filter-branch --tree-filter 'grep -l "TELEGRAM_TOKEN" * && sed -i "s/8781984176.*/REDACTED/g" *' -- --all

# Или используйте git-filter-repo (более новый инструмент)
git filter-repo --replace-text expressions.txt
```

**⚠️ Важно:** После переписи истории нужно делать force push всем, кто использует репозиторий.

---

## 🔐 Дополнительные советы

### 1. **Никогда не коммитьте:**
   - `.env`
   - Конфигурационные файлы с паролями
   - API ключи
   - Private keys

### 2. **Используйте .env.example** для документации:
```
# .env.example (можно коммитить!)
TELEGRAM_TOKEN=your_token_here
TELEGRAM_CHAT_ID=your_chat_id_here
EXCHANGE=mexc
SYMBOL=ETH/USDT
```

### 3. **На production сервере:**
   - Используйте системные переменные окружения
   - Или инструменты типа **AWS Secrets Manager**, **HashiCorp Vault**
   - Никогда не используйте `.env` файлы на production!

### 4. **Для Docker:**
```dockerfile
# Dockerfile
FROM python:3.11
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Переменные окружения приходят из docker-compose.yml или .dockerignore
ENV TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
```

```yaml
# docker-compose.yml
services:
  agent:
    build: .
    env_file: .env
    environment:
      - TELEGRAM_TOKEN=${TELEGRAM_TOKEN}
```

---

## ✨ Итоговая структура проекта

```
CryptoAgents/
├── .env                    # ← Ваши токены (НЕ коммитить!)
├── .env.example            # ← Пример для других (можно коммитить)
├── .gitignore              # ← Защита .env
├── requirements.txt
├── agent_001/
│   ├── config.py           # ← Конфигурация
│   ├── agent_base_v1.py    # ← Использует конфиг
│   └── telegram_notifier.py
└── README.md
```

---

## 🚨 Чек-лист безопасности

- [ ] `.env` файл создан
- [ ] `TELEGRAM_TOKEN` и `TELEGRAM_CHAT_ID` в `.env`
- [ ] `.gitignore` содержит `.env`
- [ ] Код удален из `agent_base_v1.py`
- [ ] `requirements.txt` содержит `python-dotenv`
- [ ] Проверено: `git status` не показывает `.env`
- [ ] Создан `.env.example` с примером
- [ ] Если утек старый токен - воссоздан новый в Telegram
