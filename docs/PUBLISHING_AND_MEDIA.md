# Контент, собственные аккаунты и медиа

`config/business.json` содержит подтверждённые владельцем услуги и контакты. Цены,
кейсы, права на визуальные материалы, WhatsApp и числовые Meta account IDs ещё не
подтверждены. Контент-план — оригинальные образовательные черновики, без выдуманных
клиентов/результатов:

```bash
.venv/bin/python scripts/editorial.py --days 14 > .local/editorial-plan.json
```

## Публикации

Предпочтён зрелый Postiz public API. Его OAuth управляет state, разрешениями и
обновлением Meta токенов. Свои OAuth backend/обход review не создаём. Текущий Postiz
включает PostgreSQL, Redis и Temporal; в бесплатный маленький trial его дополнительно
не размещаем. При необходимости отдельный self-hosted Postiz с проверкой лицензии
AGPL-3.0 и ресурсов; облачный Postiz не считается бесплатным.

Установленный Postiz: `POSTIZ_API_URL=https://.../api/public/v1`, защищённый
`POSTIZ_API_KEY`, подключить в UI **свои** Threads/Instagram аккаунты и получить IDs
через `GET /integrations`. API key передаётся Authorization без выдуманного Bearer.
См. проверенные исходники [021c2ee](https://github.com/gitroomhq/postiz-app/blob/021c2ee0763ed03aa211d863298a2ae0e9010544/apps/backend/src/public-api/routes/v1/public.integrations.controller.ts).

```bash
python3 scripts/content.py account my-threads threads REAL_POSTIZ_INTEGRATION_ID --enable
```

Это локальная настройка, не доказательство живой авторизации. Worker сверяет ID,
тип и enabled аккаунта перед публикацией. `/content new my-threads Текст`, затем
`/content show UUID`, `/content approve UUID ВЕРСИЯ`, `/publish UUID ВЕРСИЯ`.
`/publish` разрешает внешнюю публикацию именно выбранного контента; не вызывать,
пока не готовы опубликовать. Для media/timezone использовать action JSON через
`scripts/content.py action FILE.json`; due_at — ISO с часовым поясом. Время хранится
в timestamptz, счётчик публикаций в UTC. Изменение due_at через edit отзывает approve.

```json
{"action":"create","account_id":"my-threads","text":"Проверяемый текст","media_ids":[],"due_at":"2026-10-20T10:00:00+03:00"}
```

DRAFT → APPROVED → SCHEDULED → PUBLISHING → SUBMITTED. Ответ Postiz не доказывает
публикацию в соцсети: проверить provider ID/его статус, после подтверждения выполнить
owner action `reconcile` с content_id, state=PUBLISHED и provider_id. При потере ответа
UNCERTAIN: нельзя повторно ставить в очередь без сверки. FAILED тоже не переотправляется
автоматически. `/cancel UUID` отменяет только ещё не отправленный контент; внешнее
удаление требует отдельного действия. Одновременные submissions учитываются в
дневном лимите (2), резервы при ошибках сохраняются консервативно. STOP проверяется
перед upload и POST. AUTOPUBLISH и AUTO_OUTREACH не включены; обязательное одобрение
каждой версии сохраняется.

Threads Search: `THREADS_ACCESS_TOKEN`, `THREADS_REVIEW_CONFIRMED=true` только после
реального разрешения. Источник threads_search config `{"query":"нужен сайт"}`.
Используется keyword_search/RECENT, русскоязычные свежие записи ≤7 дней и cursor;
произвольный paging.next не открывается. [Официальный пример Meta](https://github.com/fbsamples/threads_api/blob/854fc140a37e20f6a7086cf3ee0065f99d41f646/src/index.js).
Own replies клиент читает только по переданному собственному thread ID; автопответов
и холодных DM нет. Статистика provider сохраняется через content_action metrics,
лиды/сделки учитываются отдельно через UTM и CRM. Лайки не считаются продажами.

## Локальное видео/карусели

```bash
.venv/bin/python scripts/media_factory.py demo
.venv/bin/python scripts/media_factory.py carousel config/examples/carousel.json
```

`demo` создаёт собственный синтетический клип и монтирует новые сцены/титры/CTA.
Это тест рендера, не чужое видео и не генерация фильма нейросетью. 720×1280, до 60s,
до 12 сцен, 1 поток рендера; карусель 1080×1350, 5–7 карточек. Нужны FFmpeg/ffprobe
и DejaVu Sans; в worker image уже установлены. Встроенные эффекты не обещают
фактическую эффективность рекламы.

Сначала зарегистрировать файл внутри media root с правами. Пример own rights:
`{"kind":"own","grant":"Снято мной, разрешаю коммерческий монтаж","owner":"Станислав"}`.
Для licensed нужны license_url, commercial=true, derivatives=true и grant. Reference
URL — только вдохновение, не лицензия и не команда на скачивание. Заимствованные
голоса, музыка и материалы без разрешения не принимаются. File SHA256 — immutable ID;
изменение файла ломает проверку. Paths/симлинки за пределами root запрещены.

Видеоспецификация использует только asset IDs:

```json
{"scenes":[{"asset_id":"64_HEX_SHA256","seconds":3,"caption":"Понятный результат"}],"cta":"stanislavweb.ru","is_demo":false}
```

`audio_asset_id` — собственная/лицензированная озвучка. Без неё ролик без аудио;
TTS/платная генерация не объявляются подключёнными. Текст рисуется Pillow, не
подставляется в FFmpeg filter expression. Исходный звук клипов автоматически не
копируется. CPU/time/file/duration ограничены. Нужна смысловая новая композиция,
одной замены CTA для чужого ролика недостаточно.

Для очереди register/render через `scripts/content.py`, либо команды контейнера
worker (на сервере media находится в volume `/data/media`). `/media list`,
`/media revoke ID`. Renderer пишет результат и отдельную очередь preview владельцу;
transport отправляет multipart sendVideo/sendMediaGroup только по проверенным IDs.
Предпросмотр не одобряет публичную публикацию. DEMO media нельзя включить в живой
пост; отзыв прав блокирует очереди, в том числе зависимые assets.

## Проверка живого подключения

Требуется отдельно: getMe и получение owner command; один разрешённый реальный
источник → карточка; свои account permissions; согласованный тестовый пост → URL;
собственный media → preview → отдельное одобрение → публикация. Пока этих доступов
нет, HTTP mocks и локальный рендер не считаются такой проверкой.

## Совместимый ИИ провайдер владельца

Base URL из предоставленной инструкции: https://shprotoness-ai.jq9gfk.workers.dev/v1.
Секретный API key хранится как AI_ACCESS_KEY в authenticated encrypted vault;
назначение второй строки пока не известно, она не пересылается провайдеру.
Владелец отдельно разрешил GET /models, но текущий proxy ответил403 Forbidden.
Нужен сетевой доступ к этому hostname. До подтверждения модели/квоты генерация OFF.

Реализованы Responses и Chat Completions со строгой JSON Schema, проверкой структуры
и точной цитаты. Cache учитывает endpoint/style. AI_PROVIDER_MODEL должен совпадать
с настоящим model ID. AI_PROVIDER_STYLE=chat_completions для соответствующего API,
или responses после проверки его поддержки. Наличие OpenAI SDK в инструкции не
подтверждает поддержку Responses, schemas, лимитов и всех моделей.
AI_FREE_QUOTA_CONFIRMED=true допустим только при реально подтверждённой бесплатной
квоте; тогда стоимость0, число вызовов всё равно ограничено. Иначе нужны цены и
согласованный денежный бюджет. Текущие AI_ENABLED=false, бюджет0, maxcalls0.

## Зашифрованные секреты

scripts/secrets_store.py принимает ключи скрытым вводом (getpass), хранит
`.local/secrets.enc` с Fernet authenticated encryption. `.local/secrets.key` —
отдельный master key с правами0600. Оба файла игнорируются git; секреты не передаются
через argv. Это защита файловых копий: администратор с обоими файлами сможет
расшифровать значения. Ключ и ciphertext резервировать раздельно.
Common config/Telegram transport расшифровывают только в памяти. Настройки облачного
secret manager с непустыми runtime значениями имеют приоритет. n8n credentials
дополнительно шифруются его N8N_ENCRYPTION_KEY. Роли БД/внутренние сгенерированные
ключи остаются в приватном `.env`; не включать его в git и публичные архивы.
