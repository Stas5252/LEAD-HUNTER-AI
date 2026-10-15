# Подготовленное развёртывание Railway

Сейчас приоритет владельца — тест в текущей облачной среде. Railway остаётся
переносимым вариантом; в настоящий аккаунт ничего не развёрнуто. Cloudflare Workers
не запускает обычные Docker/n8n/PostgreSQL/FFmpeg процессы, Tunnel не предоставляет
VM. Перенос архитектуры на Workers/D1/Queues — отдельная работа, здесь не требуется.

Для дальнейшего Railway trial подготовлены 3 независимых сервиса. Источник — этот
репозиторий после сохранения в GitHub, не загружать `.env`, `.local`, backups, media.

1. **postgres**: config path `/deploy/railway/postgres.json`, private service, volume
   `/var/lib/postgresql/data`, до 0.5GB на trial; не публиковать TCP порт.
2. **n8n**: `/deploy/railway/n8n.json`, volume `/home/node/.n8n`, port5678. Для polling
   публичный domain не нужен; использовать private DNS. Первый старт импортирует
   encrypted credentials и19 workflows, делает backup перед заменой. Таймаут readiness300s.
3. **worker**: `/deploy/railway/worker.json`, volume `/data/media`. Start command
   `python3 scripts/cloud_worker.py`. Сам применяет миграции app DB, настройки,
   запускает адаптер и при наличии token/admin один Telegram transport. Docker socket
   не нужен. При сбое дочернего процесса контейнер перезапускается платформой.

Секретные переменные задать в Railway Variables, не в исходниках/чате:

| Переменная | Где | Назначение |
|---|---|---|
| POSTGRES_PASSWORD | postgres | Случайный пароль администратора БД |
| APP_DB_PASSWORD | postgres,n8n | Один одинаковый случайный пароль роли lead_hunter |
| N8N_DB_PASSWORD | postgres,n8n | Один одинаковый случайный пароль роли n8n |
| N8N_ENCRYPTION_KEY | n8n | Один устойчивый случайный ключ, сохранить отдельно |
| INGEST_TOKEN | n8n,worker | Один одинаковый серверный secret формы |
| TELEGRAM_WEBHOOK_SECRET | n8n,worker | Один одинаковый secret внутренних маршрутов |
| TELEGRAM_BOT_TOKEN | worker | Токен собственного бота через защищённые Variables |
| DATABASE_URL | worker | App-role URL к lead_hunter в private PostgreSQL |

Несекретные:

- postgres: POSTGRES_USER=postgres, POSTGRES_DB=postgres.
- n8n: DB_TYPE=postgresdb, DB_POSTGRESDB_HOST=postgres.railway.internal,
  DB_POSTGRESDB_PORT=5432, DB_POSTGRESDB_DATABASE=n8n, DB_POSTGRESDB_USER=n8n,
  DB_POSTGRESDB_PASSWORD — ссылка на N8N_DB_PASSWORD; N8N_DIAGNOSTICS_ENABLED=false,
  N8N_VERSION_NOTIFICATIONS_ENABLED=false, N8N_BLOCK_ENV_ACCESS_IN_NODE=true,
  NODE_FUNCTION_ALLOW_BUILTIN=crypto,url, N8N_SECURE_COOKIE=true.
- worker: LH_N8N_URL=http://n8n.railway.internal:5678, MEDIA_ROOT=/data/media,
  TELEGRAM_ADMIN_ID=761405171, AI_ENABLED=false, DAILY_API_BUDGET_USD=0,
  MAX_LLM_CALLS_PER_DAY=0, MAX_LEADS_PER_RUN=100, MAX_PUBLIC_POSTS_PER_DAY=2.
- DATABASE_URL app role, например `postgresql://lead_hunter:URL_ENCODED_PASSWORD@postgres.railway.internal:5432/lead_hunter`.
  URL хранить как secret. Внешние PostgreSQL подключения требуют TLS; этот пример
  использует только изолированную private сеть Railway.

Пароли после создания volume нельзя просто поменять в variables: существующие
PostgreSQL роли сохраняют прежний пароль. Нужна согласованная ротация. Ключ шифрования
n8n не менять без миграции credentials. Bootstrap резервирует workflows, UI-правки
сохранять в backup; importer потом заменяет только проектные stable IDs.

Рендер на trial ограничить одной задачей, короткими клипами, не превышать volume.
Нельзя считать service sleep/reset безопасным бэкапом. Dump app+n8n и media/manifest
выгрузить с платформы до окончания кредита. Общий scripts/backup.py предназначен для
Docker Compose VPS; в Railway использовать штатные pg_dump/export и скачивание volume.

Перед публичным доступом редактор закрыть авторизацией. Форма — отдельный HTTPS
маршрут со своим secret, consent и rate limit. Worker/transport/content webhooks
в Интернет не открывать. Для теста достаточно polling без публичного n8n.
