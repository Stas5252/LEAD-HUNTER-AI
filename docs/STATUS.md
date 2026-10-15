# Фактическое состояние

Обновлено 2026-10-15. Код находится в `/workspace/LEAD-HUNTER-AI`; исходники сохранены в GitHub
Stas5252/LEAD-HUNTER-AI, ветка main. Это рабочий сессионный тест, а не обещание постоянного сервера.

Подробный список оставшихся подключений и действий: [CONNECTIONS.md](CONNECTIONS.md).

## Запущено и проверено

- PostgreSQL17 и n8n2.43.6 healthy;19 workflows,11 применённых миграций.
- Добавлен Telegram visitor intake для статического сайта GitHub Pages (Stas5252/Stanislav):
  согласие → задача → рабочий контакт → CRM → карточка владельцу.
  Проверены 35 Node tests,9 изолированных DB tests и5 шагов через настоящий n8n.
  Подробнее [WEBSITE_INTAKE.md](WEBSITE_INTAKE.md).
- Меню Telegram из 15 команд установлено и прочитано обратно для чата владельца.
- Host worker и один Telegram polling transport запущены; повторный start-local
  не создаёт дубликаты. Владелец привязан к761405171, STOP сохранён (сейчас false).
- Бот [@LeadMagnetic67_bot](https://t.me/LeadMagnetic67_bot): getMe успешен,
  существующего webhook нет. Реальная карточка доставлена через n8n/outbox. Получена настоящая команда
  владельца `/start`, ответ доставлен (processed owner command1, sent reply1).
- Реальный DEMO-клип: собственный синтетический asset → регистрация прав → n8n
  очередь → FFmpeg render → Telegram sendVideo. Media job DONE, outbox SENT.
  Это демонстрационный материал, не клиентский кейс и не публичная публикация.
- Локальные проверки:33 Node прошли;64 различных Python checks прошли с учётом
  целевых повторов после исправлений. Проверка восстановления в НОВУЮ БД
  заблокирована заполненным диском. Последний полный прогон64 Python имел2 errors:
  старый deployed workflow формы (после импорта целевой повтор PASS) и ENOSPC при
  CREATE DATABASE. После него добавлена и пройдена проверка общего media root.

## Что реализовано

Девять сценариев имеют независимые workflows/configs: OSM, регистрационные выгрузки,
Telegram allowlist, factual HTML audit, нишевые предложения, субподряд, подписанные
формы, партнёры, свой контент. Подробно [каналы](CHANNELS.md). Все источники не
становятся живыми от наличия кода: нужны разрешённые данные/доступ/конфигурация.

Контент: versioned approvals, STOP/дневной лимит, Postiz официальный API,
Threads keyword_search с cursor, UTM/CRM, UNCERTAIN без слепой повторной отправки.
Live Meta/Postiz аккаунты не подключены; реальные посты/DM клиентам не отправлялись.

Медиа: rights registry, SHA256, зависимости/отзыв, наследование DEMO, FFmpeg/Pillow,
5–7 карточек, captions/CTA, своя озвучка optional, Telegram preview. Чужие материалы
без прав и платная генерация выключены. Переданные фото/скриншоты не считаются
автоматическим разрешением коммерчески использовать исходные материалы.

## ИИ

Три переданных владельцем секрета зашифрованы Fernet в `.local/secrets.enc`, master
key отдельно0600, не в Git/.env. Назначение второго ИИ-секрета пока не подтверждено;
он никуда не отправлялся. API совместимого провайдера задан владельцем;
GET `/models` явно разрешён, но proxy вернул403 Forbidden. Сетевой hostname добавлен
в draft. Нужны применение сетевых настроек, реальный model ID и данные о квоте/цене.
Responses/Chat Completions adapters проверены на mocks, живой inference не проверен.
AI_ENABLED=false, денежный бюджет0, max LLM calls0. Базовый скоринг работает без LLM.

## Ограничения среды

Корневой служебный диск32GB заполнен. Новые Docker containers/БД не создаются;
существующие n8n/PostgreSQL работают. Без удаления volumes проверены безопасные
очистки task cache/own unused worker image — места недостаточно. Worker работает
на host; `.venv` сейчас symlink в `/tmp/lead-hunter-venv`, media в
`/tmp/lead-hunter-media`, тестовые backups в `/tmp/lh-backups`. Эти временные данные
не считать гарантированно сохраняющимися после завершения/восстановления среды.
Нужен свободный диск перед fresh install/полным restore acceptance/permanent deploy.

Dump app/n8n и инструкции резервирования есть; автоматический backup не собирает
локальный vault/master key. Их надо сохранить отдельно и раздельно — deferred Minor
независимого ревью. Само сохранение draft не применяет его и не публикует snapshot.

OSM: сохранён bounded config Саратов/кафе, источник выключен до доступности сети;
в /sources статус NEEDS_NETWORK_ACCESS. Draft сети повторно сохранён с точными
адресами Telegram, ИИ, Overpass, сайта и Threads; применение/публикация ещё нужны.

## Следующий живой тест

Владелец открывает бота и отправляет `/start`, `/leads`, `/find maps_demo`, `/stats`.
DEMO явно вымышленный. Для реальных источников: разрешённые chat IDs/feeds, bbox/tag,
сеть к Overpass; для формы — серверная интеграция с consent; для соцсетей — OAuth
собственных аккаунтов. Весь реальный исходящий контакт с клиентом остаётся ручным.

Переносимость: [хостинг](HOSTING.md), [Railway](RAILWAY_DEPLOY.md),
[контент/медиа/секреты](PUBLISHING_AND_MEDIA.md). Владелец выбрал текущую сессию для
теста; аккаунт Railway/Cloudflare не создавался, платные услуги не подключались.
