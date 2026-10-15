# Бесплатный тестовый сервер

Владелец выбрал: сервер, вся Россия, пока без платных API. Облачная среда разработки
не считается постоянным сервером. Аккаунт хостинга, региональная доступность и
реальный запуск ещё не подтверждены.

## Выбранный кандидат: Railway Trial

Официальная документация проверена 2026-10-15 через репозиторий
[railwayapp/docs, commit c8e38c2](https://github.com/railwayapp/docs/blob/c8e38c2db90fb8d13008f3ca849fc78553dedeae/content/docs/pricing/free-trial.md):

- Пробный кредит $5, действует до 30 дней, заканчивается раньше при расходовании.
- Потом Free: $1 кредита/месяц, без переноса остатка. Для полного стека 24/7 недостаточно.
- Trial: до 1 GB RAM и 0.5 GB volume на сервис, до 5 сервисов в проекте.
- Free после trial: 0.5 GB RAM на сервис. Тяжёлый монтаж и Postiz сюда не планируем.
- Limited Trial имеет ограничения исходящей сети; GitHub verification автоматическая,
  без гарантии прохождения. Для Telegram/OSM нужен исходящий HTTPS.
- Trial volumes удаляются через 30 дней после окончания кредита. Бэкап выгружать заранее.
- Anonymous VM `railway.new`: окно 24 часа, незакреплённые VM удаляются. Для базы бота
  такой временный ресурс не используем.

[Лимиты и цены](https://docs.railway.com/pricing/plans). Стоимость зависит от RAM/CPU,
времени и трафика. «Бесплатно навсегда» и 30 дней при любой нагрузке не обещаем.
Не подключать карту/платный план для этого теста; проверить, что выбраны Trial/Free.

Нужно от владельца: войти на https://railway.com/ через свой GitHub, проверить наличие
trial-кредита и статус исходящей сети. Пароль/токены в чат не присылать. Развёртывание
в аккаунте и открытие внешних маршрутов выполняются после подготовки параметров
конкретного проекта. Пока регистрации и развёртывания с этой стороны не было.

## Постоянная альтернатива

Нужен Linux VPS с Docker Compose, ориентир 2 vCPU, 2–4 GB RAM, диск от 20 GB.
Free Tier/гранты зависят от страны, доступности и проверки аккаунта. Oracle Always
Free — кандидат для отдельной проверки, не подтверждённый свободный сервер.
Для экономии: Postiz внешний/отдельный по необходимости; FFmpeg по одному заданию;
браузер, платная генерация и LLM выключены. Самозапуск после перезагрузки — Compose
`restart: unless-stopped`. Telegram long polling не требует открывать n8n в Интернет.

## Локальная/Ubuntu установка на предоставленный VPS

Установить Docker Engine + Compose plugin, Node 24 и Python 3.12+. Из каталога проекта:

```bash
python3 scripts/setup.py
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
node scripts/build-sources.js
node scripts/build-publishing.js
docker compose up -d --wait
python3 scripts/migrate.py
python3 scripts/connect.py
python3 scripts/import-workflows.py --activate-local
docker compose --profile workers build worker
docker compose --profile workers up -d --wait
```

Владелец разрешил текущий токен для теста. Токен хранится в зашифрованном vault;
установить `TELEGRAM_ADMIN_ID=761405171` и обеспечить чтение vault, затем:

```bash
python3 scripts/connect.py
python3 scripts/import-workflows.py --activate-local
docker compose run --rm --no-deps telegram python3 scripts/telegram_transport.py --check
docker compose --profile workers --profile telegram up -d
```

Только один polling transport. Существующий webhook проверяется и автоматически
не удаляется. Внешние токены не нужны для DEMO/рендера. Форма сайта требует HTTPS
reverse proxy только к `/webhook/lh-form`, ограничения тела и rate limit на ingress;
редактор n8n/worker/content/transport маршруты публично не открывать. Secret формы
только в серверной части сайта. TLS сертификат получить штатным reverse proxy.

## Управляемая облачная среда

При наличии session proxy:

```bash
python3 scripts/cloud-compose.py
export COMPOSE_FILE=docker-compose.yml:.local/compose.cloud.json
export BUILDX_CONFIG="$PWD/.local/buildx"
docker compose --profile workers build worker
```

Override приватный и игнорируется git. CA монтируется read-only и передаётся в build
через BuildKit secret; в образ session CA не встраивается. Proxy и TLS сохраняются.
Untrusted HTML/RSS аудит за CONNECT proxy возвращает NEEDS_SAFE_TRANSPORT, поскольку
локальная проверка DNS не гарантирует адрес, который выберет proxy. На прямом VPS
HTTP-клиент использует проверенный публичный IP с исходным TLS hostname.

## Windows

Docker Desktop с WSL2; команды проекта выполнять в Ubuntu/WSL, включая `.venv` и
FFmpeg. Для нативного Python нужны ffmpeg/ffprobe в PATH и шрифт DejaVu Sans; проще
использовать контейнер worker. Linux cloud override не копировать в Windows: его
пути CA принадлежат конкретной сессии. Не переносить `.env` в GitHub.
