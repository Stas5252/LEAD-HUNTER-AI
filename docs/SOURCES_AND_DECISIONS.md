# Источники и решения

Дата обращения: 15 октября 2026 года. Звёзды не использовались как доказательство
работоспособности; их текущие значения и все issues здесь не проверены и не выдуманы.

| Источник | Что использовано/проверено | Доступ, стоимость, лицензия |
|---|---|---|
| https://github.com/n8n-io/n8n | Официальный образ 2.43.6, CLI `execute/import/publish`, типы стандартных нод, PostgreSQL query parameters; реальный импорт и исполнения | Self-hosted внутреннее использование; Sustainable Use License, **не OSI open-source**. Не продавать доступ к редактору как свой SaaS без проверки условий. |
| https://registry.npmjs.org/n8n | Текущая опубликованная версия 2.43.6 и Node.js ≥24; integrity metadata прочитаны | npm-пакет не устанавливался; используется официальный Docker image, проверки Docker digest сохранены |
| https://github.com/n8n-io/n8n-docs | Прочитаны текущие Docker/CLI инструкции из официального GitHub checkout, HEAD `ad8c4a94f3b4764c232dc91aeb9496fb6bf0ed2a` | Сайт docs.n8n.io блокировался прокси; использовано официальное зеркало исходников, TLS не отключался |
| https://n8n.io/workflows/15411-local-business-lead-discovery-and-enrichment-agent/ | Запрос завершился proxy 403; JSON шаблона не получен | **Адаптация не выполнена**. Собственный стандартный workflow реализует согласованный DEMO-поток. Для точной адаптации нужен доступ к исходному JSON. |
| https://n8n.io/workflows/6091-google-maps-lead-scraper-and-enrichment-with-ai-powered-personalized-outreach/ | Кандидат из задания, в этап A не включён | Источники/платные зависимости и право использования не проверялись; не считать готовой интеграцией |
| https://n8n.io/workflows/5443-google-maps-business-scraper-and-lead-enricher-with-bright-data-and-google-gemini/ | Кандидат из задания, в этап A не включён | Платный провайдер не подключался |
| https://hub.docker.com/_/postgres | Официальный PostgreSQL 17.11-alpine, Docker pull/digest, настоящие миграции, роли и SQL-функции | PostgreSQL license; образ опубликован для amd64/arm64, фактический запуск только amd64 |
| https://core.telegram.org/bots/api | Реализованы getMe/getWebhookInfo/getUpdates/sendMessage/answerCallbackQuery/setWebhook через HTTPS | Сайт заблокирован сетью; тесты payload и local HTTP mock пройдены, реальный Bot API **NEEDS_KEY** |
| https://platform.openai.com/docs/api-reference/responses | Responses JSON Schema request и валидатор, HTTP node, кэш/бюджет/fallback проверены на локальном mock | Сайт блокировался сетью; живой API не проверен. Платный API, тариф задаётся владельцем; ChatGPT Plus не покрывает API |
| https://github.com/gitroomhq/postiz-app | Отложен до этапа B; публикации не нужны для вертикального среза | Актуальный релиз/лицензия/API/ресурсы в этой сборке не проверены; не установлен |
| https://github.com/nocodb/nocodb | Опциональная CRM GUI отложена; Telegram и SQL достаточны для этапа A | Не установлен, не исследован как готовая интеграция |
| https://github.com/unclecode/crawl4ai | Браузерный аудит отложен, HTTP-скрейпинга сайтов в этапе A нет | Не установлен; случайные URL не скачиваются |
| https://github.com/harry0703/MoneyPrinterTurbo | Отложен; дорогая генерация по умолчанию отключена | Не установлен, лицензия/провайдеры/ресурсы требуют проверки перед этапом C |
| https://github.com/x-bizarre/amy-threads-bot и https://github.com/poisonstefani-dev/threads-mcp | Кандидаты следующего этапа, код не заимствован | Не исследованы и не заявлены готовыми; Threads Search требует Meta review независимо от этих проектов |

## Принятые решения

- Использовать n8n/PostgreSQL и небольшие адаптеры; не писать отдельный backend.
- Четыре содержательных workflow вместо набора неработающих collector-заглушек.
- Реальная ветка HTTP OpenAI проверяется через n8n локальным mock, не имитируется
  печатью придуманного ответа. Mock остаётся отдельным методом `openai_mock`.
- Python нужен для polling/доставки, так как встроенная Telegram интеграция n8n
  ориентирована на webhook. Правила и состояния остаются в n8n/PostgreSQL.
- Отсутствие ключей не блокирует DEMO. Бюджет и AI включаются только явными настройками.
- Дедупликация и одобрения атомарны, коммерческие сообщения автоматически не отправляются.
- Не расширять этап A за счёт неподтверждённых поисковых и социальных API.
