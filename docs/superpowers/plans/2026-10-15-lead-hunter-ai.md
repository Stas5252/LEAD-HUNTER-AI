# LEAD HUNTER AI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking. Execution proposed: inline in the existing cloud checkout.

**Goal:** Реализовать этап A: DEMO JSON/CSV → n8n → нормализация и оценка → PostgreSQL → тестовая карточка или Telegram владельца.

**Architecture:** n8n управляет процессами, PostgreSQL хранит лиды, бюджет, состояния и очередь. Небольшие JavaScript-модули встраиваются в Code nodes генератором workflow; Python-скрипты обеспечивают настройку и приёмочные проверки. Отдельного backend нет.

**Tech Stack:** Docker Compose, фиксированные образы n8n и PostgreSQL, Node.js built-in test runner, Python 3 standard library, SQL migrations.

**Spec:** `docs/superpowers/specs/2026-10-15-lead-hunter-ai-design.md`.

## Global Constraints

- Работать в существующем `/workspace/LEAD-HUNTER-AI`, без дополнительного worktree.
- AUTOPUBLISH=false, AUTO_OUTREACH=false, VIDEO_GENERATION_PAID=false.
- DAILY_API_BUDGET_USD=1, MAX_LLM_CALLS_PER_DAY=50, MAX_LEADS_PER_RUN=100, MAX_PUBLIC_POSTS_PER_DAY=2.
- Фикстуры явно вымышленные; `is_demo=true` сохраняется до конечной карточки.
- Все девять способов сохраняются в реестре; реальные непроверенные интеграции не маркируются WORKS.
- Секреты не включаются в Git, workflow JSON, отчёты и вывод команд.
- Одобрение связано с действием и версией черновика; внешняя отправка КП отсутствует в этапе A.
- Код и проверки помещаются в репозиторий; ни тесты, ни DEMO не требуют внешних платных API.

## Review Focus

1. Пустое поле website и общий социальный домен не доказывают отсутствие сайта и не объединяют разные компании — тесты задачи 2.
2. Повторный импорт и повторный Telegram update не снимают DNC и не повторяют побочные эффекты — интеграционные тесты задач 3 и 4.
3. Одобрение устаревшего черновика, чужой callback и команды после /stop не выполняют действие — тесты задачи 4.
4. Параллельные запросы не превышают дневной лимит; повторы API тоже учитываются — тесты задачи 5.
5. Принятый Telegram запрос с потерянным ответом не отправляется повторно вслепую — тесты задачи 4.

---

### Task 1: Воспроизводимый Compose и база

**Files:** `docker-compose.yml`, `.env.example`, `.gitignore`, `scripts/setup.py`, `scripts/init-db.sh`, `scripts/migrate.py`, `migrations/001_core.sql`, `tests/test_stack.py`.

**Interfaces:** `python3 scripts/setup.py` создаёт отсутствующий `.env`; `python3 scripts/migrate.py` применяет миграции через Compose; прикладная роль `lead_hunter` работает только с базой `lead_hunter`, роль n8n — с базой n8n.

- [x] Написать проверки в `tests/test_stack.py`: отсутствующие конфигурационные файлы приводят к ошибке, миграция сохраняет таблицы и не выдаёт приложению superuser.
- [x] Запустить проверки и подтвердить ожидаемое падение до реализации.
- [x] Проверить официальные release/registry metadata и выбрать фиксированные версии образов с amd64/arm64; зафиксировать фактическую доступность в источниках.
- [x] Реализовать Compose: healthchecks, постоянные тома, loopback-порты, restart policies и log rotation. Отключить ненужную телеметрию.
- [x] Реализовать безопасную генерацию локальных секретов без перезаписи существующего `.env`; инициализацию разных ролей и баз; версионируемые миграции.
- [x] Запустить Compose, выполнить тесты, повторить миграцию; ожидается healthy n8n/PostgreSQL и отсутствие потери данных.

### Task 2: Нормализация, эвристики и честная карточка

**Files:** `lib/leads.js`, `lib/cards.js`, `fixtures/leads.json`, `fixtures/leads.csv`, `tests/leads.test.js`.

**Interfaces:** `normalizeLead(raw)` возвращает лид с ключом дедупликации; `scoreLead(lead)` возвращает классификацию, score, confidence и доказательства; `renderCard(lead)` возвращает безопасный текст и inline keyboard. Исходные функции доступны Node.js tests и генератору n8n workflow.

- [x] Написать тесты `node --test tests/leads.test.js`: прямой запрос, предложение исполнителя, спам, пустой сайт, разные страницы соцсети, нормализация URL/телефона, DEMO-маркер и экранирование.
- [x] Подтвердить падение тестов до реализации модулей.
- [x] Реализовать валидацию размеров и обязательных полей, канонизацию URL без утраты идентичности поста, стабильные ключи, классификацию и нишевые предложения без вымышленных портфолио.
- [x] Добавить JSON/CSV фикстуры с явно вымышленными примерами, различными намерениями и дубликатом.
- [x] Запустить тесты; все ожидаемые результаты должны совпадать, отсутствие сайта остаётся UNKNOWN.

### Task 3: Реальный n8n workflow DEMO и идемпотентная запись

**Files:** `scripts/build-workflows.js`, `scripts/import-workflows.py`, `scripts/demo.py`, `workflows/01-lead-import.json`, `migrations/002_ingestion.sql`, `tests/test_pipeline.py`.

**Interfaces:** `node scripts/build-workflows.js` формирует воспроизводимые JSON; `python3 scripts/import-workflows.py` привязывает локальные n8n credentials без секретов в tracked JSON; `python3 scripts/demo.py --format json|csv` запускает workflow через n8n и показывает конечные карточки.

- [x] Написать интеграционный тест: workflow существует и запускается n8n, записи появляются в PostgreSQL, повторный запуск не увеличивает число уникальных лидов.
- [x] Подтвердить ожидаемое падение при отсутствии workflow.
- [x] Получить шаблон 15411 с официального источника либо зафиксировать невозможность и документировать самостоятельный стандартный workflow без ложного заявления об адаптации.
- [x] Реализовать workflow стандартными нодами: ввод → normalize/score → параметризованный PostgreSQL UPSERT → карточка/очередь.
- [x] Реализовать SQL-ограничения и функции: DNC неизменен при импорте, исходный момент создания сохраняется, уведомление имеет уникальный ключ.
- [x] Проверить импорт и запуск в выбранной версии n8n на обоих форматах; повреждённый ввод должен завершаться понятной ошибкой, не частичным молчаливым успехом.

### Task 4: Telegram-пульт, одобрения и остановка

**Files:** `lib/telegram.js`, `workflows/02-telegram.json`, `workflows/03-notifications.json`, `migrations/003_telegram.sql`, `scripts/connect.py`, `scripts/telegram_transport.py`, `tests/telegram.test.js`, `tests/test_telegram_flow.py`.

**Interfaces:** `parseUpdate(update, adminId)` возвращает разрешённую команду либо ignored; SQL-функция обрабатывает update_id и изменение состояния атомарно. Отправщик карточек доставляет только в разрешённый личный чат владельца.

- [x] Написать тесты: чужой пользователь/чат, повторный update, /stop и /resume, /reject → DNC, одобрение конкретной версии, изменённый черновик аннулирует одобрение.
- [x] Подтвердить ожидаемое падение тестов до реализации.
- [x] Реализовать /start, /today, /find, /leads, /lead, /draft, /approve, /reject, /sources, /stats, /budget, /stop, /resume и inline-кнопки.
- [x] Реализовать long polling с сохраняемым offset, проверкой владельца и исключением одновременного webhook. Создать инструкцию HTTPS webhook с secret header; не регистрировать webhook без подключения владельцем.
- [x] Реализовать outbox: ограниченный backoff для однозначных отказов, неоднозначный результат отмечается для ручной проверки, отсутствие слепого повтора sendMessage.
- [x] Выполнить тесты payload и workflow с HTTP mock. При отсутствии токена сохранить статус NEEDS_KEY, не заявлять реальную доставку.

### Task 5: OpenAI, кэш и атомарный бюджет

**Files:** `lib/scoring.js`, `workflows/04-openai-score.json`, `migrations/004_budget.sql`, `tests/scoring.test.js`, `tests/test_budget.py`.

**Interfaces:** `validateScoreResponse(response)` валидирует JSON Schema результат Responses API; SQL-функции резервируют дневной бюджет и вызов; cache key включает контент, модель, версию промпта и схемы.

- [x] Написать тесты корректного/повреждённого ответа, таймаута, неверного диапазона score, отказа модели, повторного вызова и конкурентного резервирования последнего лимита.
- [x] Подтвердить ожидаемое падение до реализации.
- [x] Реализовать опциональный Responses API с JSON Schema, ограничениями токенов/таймаутом, настраиваемой моделью и ценами. Без цены, ключа или лимита расходы запрещены; fallback явно эвристический.
- [x] Реализовать атомарное резервирование стоимости/вызовов и кэш; повтор учитывается отдельно, ошибки не снимают консервативный резерв.
- [x] Проверить mock через n8n и конкуренцию на настоящей PostgreSQL; реальный OpenAI остаётся NEEDS_KEY до отдельной проверки.

### Task 6: Запуск с нуля, документация и итоговая приёмка

**Files:** `README.md`, `START_HERE.md`, `docs/SOURCES_AND_DECISIONS.md`, `docs/STATUS.md`, `docs/OPERATIONS.md`, `scripts/verify.py`, `scripts/backup.py`, `scripts/restore.py`.

**Interfaces:** `python3 scripts/verify.py` запускает предусмотренные проверки и сохраняет exit status; backup/restore работают с отдельным тестовым восстановлением без удаления рабочих данных.

- [x] Описать 5–10 шагов первого запуска Ubuntu/Windows, реальные credentials n8n, тестовый и настоящий режимы, сеть, HTTPS, резервное копирование.
- [x] Зафиксировать по всем девяти каналам, Threads, Instagram и видео статусы WORKS/NEEDS_KEY/NEEDS_APP_REVIEW/PLANNED/FAILED; отдельно отметить DEMO и mocks.
- [x] Указать фактически поднятые сервисы, проверенные версии/лицензии/источники, допущения стоимости и ориентиры ресурсов без гарантии бесплатного VPS.
- [x] Выполнить весь предусмотренный набор unit/integration tests; подтвердить DEMO через настоящий n8n, повторный импорт, DNC и сохранение состояния после перезапуска собственных контейнеров.
- [x] Проверить backup/restore в отдельной базе и отсутствие секретов среди tracked/untracked артефактов, предназначенных для Git.
- [x] Сохранить проверенные install_script/start_skill для облачной среды, не полагаясь на сохранение живых процессов. Сообщить отдельно о сохранении черновика и необходимости публикации владельцем.
- [x] Провести итоговый review по спецификации и устранить замечания в рамках этапа A; итоговый отчёт содержит действительные результаты команд и оставшиеся внешние ограничения.
