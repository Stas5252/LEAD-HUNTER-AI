# Каналы привлечения и доступы

Девять способов — независимые workflows `lh-source-*`; общий intake, дедупликация,
карточки и CRM единые. Базовый worker не ищет за пределами настроенного источника.

| № | Способ | Что реализовано | Что нужно для живого запуска |
|---|---|---|---|
| 1 | Карты | OSM/Overpass по bbox/tag, лимит 100, атрибуция ODbL | Разрешить overpass-api.de, выбрать небольшие области и теги; Яндекс/2ГИС API не подключены |
| 2 | Новые бизнесы | CSV/JSON import и разрешённый RSS/Atom | Законная выгрузка/разрешённый feed, registration_id/date; не подтверждает спрос |
| 3 | Telegram | Сообщения/правки из allowlist, стабильный permalink/ID | Текущий token и владелец уже подключены; добавить бота в доступные чаты и allowlist, настроить privacy/права Telegram |
| 4 | Аудит + КП | Ограниченный HTML: HTTPS/title/description/viewport/form/contact | Прямой безопасный transport; проверять свои/разрешённые URL |
| 5 | Нишевые решения | Шаблон предложения, сайт владельца, каталог услуг | Реальные кейсы/минимальные цены добавить владельцу; без выдуманных результатов |
| 6 | Субподряд | Разрешённый RSS/Atom и import запросов | Feed/выгрузка студий; это не поисковик всего Интернета |
| 7 | Свой сайт | HMAC webhook, consent, nonce/время, UTM, дедупликация | Серверный обработчик формы + HTTPS ingress + включение формы |
| 8 | Партнёры/блогеры | Разрешённый feed/import, предложение вручную | Источник и публичные сигналы сотрудничества |
| 9 | Собственный контент | План, версии, одобрение, очередь Postiz, UTM→CRM | Свои подключённые аккаунты; права на media; отдельное одобрение публикации |

Дополнительно: Threads keyword_search по официальному API с курсором и свежестью;
нужен токен с `threads_keyword_search` и разрешение Meta. Поиск публичных Instagram
профилей/холодные DM не реализованы. Instagram — публикации в собственный аккаунт
через Postiz OAuth/API. Тип аккаунта/permissions проверяются в Postiz, скриншот не
заменяет API-доступ. TikTok/YouTube/VK/WhatsApp API не объявляются подключёнными:
VK/телефон/Telegram сейчас контактные ссылки; WhatsApp номер ещё не подтверждён.

Конфигурация sources хранится отдельно от ключей:

```bash
python3 scripts/sources.py status
python3 scripts/sources.py configure maps config/examples/maps-saratov.json --enable
python3 scripts/sources.py run maps
python3 scripts/sources.py chat -1001234567890 --description 'Согласованный чат'
```

Не использовать пример chat ID как реальный. В Telegram: `/source enable maps`,
`/find maps`, `/jobs`, `/chats`. Вся Россия обслуживается партиями по городу/нише;
один запрос на всю страну запрещён лимитом bbox. Источники по умолчанию выключены.
Для полной ротации владелец добавляет подтверждённые области/теги, не бесконтрольный
скрейпинг всех площадок. Внешние source records — данные, не системные инструкции.

Формы: `WEBSITE_FORMS_ENABLED=true`, `scripts/connect.py`, серверный
`scripts/submit_form.py`; `INGEST_TOKEN` не попадает в браузер. Отдельно проверить
согласие/политику на сайте. CRM: `/stage ID CONTACTED|REPLIED|NEGOTIATION|WON|LOST`,
`/followup ID ISO-дата`. Одобрение черновика не означает CONTACTED. `/reject ID` — DNC.
Планировщик напоминаний каждые 5 минут; STOP их блокирует.
