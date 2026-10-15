# До первой карточки

1. Установите Docker с Compose, Python 3.12+ и Node.js 24+ (для тестов и изменения workflow). В Windows используйте Docker Desktop с Linux containers; команды ниже выполняйте в PowerShell, заменяя `python3` на `python`, если требуется.
2. Перейдите в корень `LEAD-HUNTER-AI`. Выполните `python3 scripts/setup.py`. Скрипт создаст приватный `.env` и не перезапишет существующий. Пароли и токены в чат не отправляйте.
3. Запустите `docker compose up -d --wait`, затем `python3 scripts/migrate.py`.
4. Выполните `python3 scripts/connect.py`, затем `python3 scripts/import-workflows.py --activate-local`. Четыре workflow появятся в n8n. Локальная активация workflow не публикует посты и не отправляет КП.
5. Выполните `python3 scripts/demo.py`, затем `python3 scripts/demo.py --format csv`. Получите карточки с пометкой **DEMO: вымышленный пример**. В редакторе n8n на локальном порту 5678 завершите создание владельца через экран первоначальной настройки.
6. До подключения настоящих аккаунтов выполните `python3 scripts/verify.py`. Проверки изменяют тестовые состояния, используют HTTP-моки и должны запускаться на DEMO-инстансе.
7. Создайте своего бота через BotFather. Впишите токен в `TELEGRAM_BOT_TOKEN` внутри локального `.env`, свой числовой Telegram user ID — в `TELEGRAM_ADMIN_ID`. Не используйте ID группы. Бот принимает команды только владельца в личном чате. Повторите `python3 scripts/connect.py` и `python3 scripts/import-workflows.py --activate-local`.
8. Выполните `python3 scripts/telegram_transport.py --check`, затем `python3 scripts/telegram_transport.py`. В Telegram откройте бота, отправьте `/start`, `/sources`, `/find maps_demo`. Работает один экземпляр transport. По умолчанию используется polling: публичный домен не нужен.
9. Для первого настоящего лида подготовьте разрешённый JSON/CSV с реальной компанией или запросом, ссылкой и точной цитатой; `is_demo=false`. Импортируйте: `python3 scripts/demo.py --input /path/to/real-leads.json`. Схема показана в `fixtures/leads.json`. Это ручной импорт источника, а не готовый парсер карт; API карт и мониторинг чатов относятся к следующему этапу.
10. OpenAI необязателен. Для включения задайте ключ, модель и актуальные цены за миллион токенов, `AI_ENABLED=true`, затем повторите connect/import. Перед включением проверьте собственный API-биллинг и лимиты. Подписка ChatGPT Plus не оплачивает OpenAI API. Без этого работает бесплатная эвристика.

Режимы, ограничения и статусы каналов: [README](README.md), [STATUS](docs/STATUS.md).
