# Implementation ledger

Plan: docs/superpowers/plans/2026-10-15-lead-hunter-ai.md

- Execution: inline, user approved both specification and plan.
- Isolation: existing cloud checkout, unborn work branch; no extra worktree.
- Pre-flight 1→3: application PostgreSQL credentials are provisioned by setup and bound by workflow import.
- Pre-flight 2→3: CommonJS pure modules are embedded into n8n Code nodes by the workflow builder; tests exercise the same functions.
- Pre-flight 3→4→5: SQL functions own atomic state, updates and budget; workflows only orchestrate.
- Pre-flight 1→6: setup is noninteractive and never replaces an existing .env.
- Ruling: packaged execution helper scripts are unavailable as local executables; keep this durable ledger and execute documented task checks directly. Cost: progress is maintained manually.
- Ruling: no local commits or remote push during development; leave reviewable files in the existing checkout. Cost: unpublished files must be retained in the environment snapshot or explicitly committed later.
- Task 1: complete — Compose services healthy; 3 setup/database tests passed, including no superuser and no n8n DB access. Init mount permissions corrected after reproducing PostgreSQL's permission error.
- Task 2: complete — normalization/cards and restricted-VM regression passed; n8n explicitly allows only crypto/url builtins.
- Task 3: complete — 3 integration tests passed (JSON and CSV actual n8n executions, import, deduplication, DNC and changed-draft revocation). New optional scoring subflow also executed successfully with AI disabled.
- Task 4: complete — 5 real n8n webhook/SQL tests and 2 local HTTP transport tests passed, including recovered command result after queue failure and no blind retry after ambiguous delivery.
- Ruling: use a small Python polling/delivery adapter because the standard n8n Telegram integration uses webhooks; n8n still owns business logic, state and schedules. Cost: one additional optional transport process must restart with the environment.
- Ruling: template 15411 is inaccessible through the network policy, so the imported workflow is independently implemented from standard nodes and is not called an adaptation. Cost: requested upstream-template reuse remains unverified.
- Task 5: complete — actual n8n HTTP-node mock test passed for valid JSON, cache, invalid JSON, 429 and 20-second timeout; six concurrent SQL reservations admitted exactly one final daily call. External API calls were not made.
- Configuration draft saved: tested install/start steps and seven custom documentation/runtime domains. Save confirmed; publication and runtime policy application were not claimed.
- Final review: fresh independent reviewer found five Important issues, no Critical issues and no deferred Minor findings. All five accepted for the single fix pass: identity collisions, versionless approval, early polling acknowledgement, stale factual projections and stale AI-cache priority.
- Final: fixed identity collisions/DEMO separation — new normalization regressions RED→GREEN; fixed versionless approval — parser and SQL/webhook regressions RED→GREEN; fixed early offset — queue-failure regression RED→GREEN; fixed stale facts — reimport regression RED→GREEN; fixed stale cache priority — post-assessment policy regression RED→GREEN. Full suite passed: 23 Node + 19 Python tests, zero skipped/failed.
- Final Ruling: live Telegram/OpenAI behavior remains NEEDS_KEY — no bindings are available and the agreed scope allows DEMO — cost if wrong: connecting an account can expose an integration issue, so run the documented checks before use.
- Final Ruling: API billing protection is approximate — configured model prices plus conservative token reservations, not provider billing authority — cost if wrong: set provider-side spending limits as well.
- Final Ruling: public HTTPS deployment was not exercised — polling supports the agreed MVP without a domain — cost if wrong: owner must verify their domain, proxy and webhook registration before switching transport.
- Final Ruling: ARM is supported by published image manifests, not validated by execution here — this machine is amd64 — cost if wrong: test on the chosen ARM host before relying on it.
- Final Ruling: Stage B/C channels remain PLANNED — the approved delivery is the working Stage A slice — cost if wrong: this MVP does not autonomously search real maps/social networks or create/publish videos.
- Task 6: complete — backup/restore, secret scan and manifest checks passed; saved install script executed successfully after PostgreSQL restart; all three DEMO lead IDs/statuses plus STOP/admin/offset/budget settings survived; repeated DEMO returned 3 cards with 0 inserts.
- Final state: two healthy containers, four imported local workflows, only fictional DEMO records; no Telegram owner or paid OpenAI account connected. Configuration draft saved, not published; new-task restoration untested. Undelivered fictional notification rows reset after test cleanup so future owner connection can receive them.


## Завершение B/C, 2026-10-15

Спецификации completion/sources/publishing/media и четыре плана одобрены сообщением
«Все тут делаем». Владелец расширил услуги: РФ/все ниши, сайты, маркетинг, CRM,
лидогенерация звонками, продажи/обучение, ИИ-контент; бюджет пока бесплатный.
Добавлены10 collector workflows (9 способов + Threads), worker/form/reminders,
content/media webhooks: всего19. PostgreSQL migrations005–010 добавочные.
Источники: OSM, разрешённые feeds/import, monitoring с allowlist, bounded HTML,
подписанные формы и нишевые предложения. Postiz/Threads проверены по source
commit, HTTP contracts покрыты mocks. FFmpeg настоящий, видео decode/probe и
5-card Cyrillic carousel проходят. Telegram getMe собственного бота работает,
публичное имя @LeadMagnetic67_bot, существующего webhook нет.

Независимое ревью (fresh gpt-6-astra): Critical0, Important8 + DTO addendum1.
Все воспроизведены RED→GREEN: протокольный обрыв POST; malformed media response;
короткая/удалённая Telegram-правка; disabled account; гонка revoke/check с реальными
транзакциями; наследование DEMO; сохранение optional credential вместо placeholder
и encrypted backup; курсор следующего запроса; Chat JSON schema envelope.
Minor deferred: backup.py не собирает локальный vault/master key автоматически;
документировано раздельное сохранение. Повторное ревью не запускалось.

Отдельно исправлен URL browser global в изолированном n8n Code: VM-test RED→GREEN.
Первый suite B/C29Node+53Python passed; после расширений ещё идёт итоговый прогон.
Секреты владельца введены getpass и сохранены в Fernet vault, master0600 отдельно,
не в исходниках/argv/.env. Пользователь явно разрешил текущий TG token без ротации
для теста и отдельно GET/models первым AI key на конкретный workers.dev endpoint.
Второй opaque secret не пересылался. GET/models блокируется proxy403; генерацияOFF.

Текущая среда: rootdisk32GB full; новый Docker worker не создаётся, n8n+PostgreSQL
остаются healthy. Без удаления volumes/пользовательских данных проверены task cache
cleanup/own unused image removal; место не восстановилось. Venv перенесён в /tmp
через symlink, тестовый backup target=/tmp/lh-backups. Для сессионного теста worker
и polling запускаются Python на host, после полного suite/привязки владельца.
Saved environment draft не равен applied runtime или published snapshot.
Railway trial изучен, подготовлены3 Dockerfile/config/bootstrap; реального signup,
deploy и fresh-stack test не было. Владелец выбрал текущую сессию для теста.

Финал сессионного запуска: owner binding применён после остановки интеграционных
проверок, запущены host worker/polling. Telegram getMe + getChat successful.
Две старые точно отклонённые HTTP400 DEMO notifications проверены отдельно, успешная
доставка подтверждена (в том числе native n8n transport render); SENT сохранён.
Собственный синтетический DEMO asset зарегистрирован, video job
6d6012ad-8e5f-48fa-8158-807d11db2c29 DONE, Telegram media outbox SENT. Для host media
в свободном /tmp добавлен общий media_root параметр BotAPI, новый тест RED→GREEN,
transport tests green. start-local.py проверен --check и повторным стартом, duplicates0.
Крупные source/AI/publishing suites после подключения owner не запускаются.
Окончательный remaining failure — restore CREATE DATABASE ENOSPC, а не скрытый PASS.


### Решения при выполнении и последствия

- Ruling: native cloud checkout is isolated branch work (unborn), preserve all Stage A files and DB — no worktree needed; cost if wrong: manual diff of initial files.
- Ruling: skill helper scripts are remote resources, ledger/test logs implemented locally — same completion contract; cost if wrong: less automatic bookkeeping.
- Task 1: adapters 8/8 RED→GREEN, public/private DNS validation and bounded OSM/feed/registration/niche/audit behavior. SafeHTTPx research found proxy bypass of its pinning and fallback DNS; chose http.client pinned IP on direct VPS, fail closed for untrusted sites in proxy cloud. Ruling: audit unavailable behind untrusted CONNECT resolution rather than weakening protection — cost: cloud audits NEEDS_SAFE_TRANSPORT until suitable direct server.
- Ruling: preserve native execution and previous Stage A data, no git commits until final secret scan — cost: ledger and local private snapshots remain recovery points before commit.
- Ruling: official current Meta sample uses graph.threads.com while Postiz still uses graph.threads.net; search uses official sample origin, both hostnames documented — cost: must revalidate actual Meta token permission/live endpoint before enabling.
- Ruling: Postiz current selfhost brings Redis/Temporal plus databases, so keep optional external existing Postiz; free test server uses3 core services, not the full Postiz stack — cost: live social publication needs separately connected Postiz deployment/account. Native social client only Threads search/read implemented; no invented IG discovery.
- Ruling: root32GB filesystem/daemon hit ENOSPC, normal sandbox bwrap cannot initialize. Safe cleanup only task build cache/dangling images/own unused worker image did not restore space; no user volumes touched. Python venv moved to /tmp via symlink; backup destination override LH_BACKUP_DIR=/tmp/lh-backups. Existing postgres+n8n healthy. Start Python adapters on host for requested session test; Docker worker startup/new Railway fresh-stack test unavailable due environment disk, not reported as passed. Cost if wrong: host processes require restart after session suspension and venv must be rebuilt after fresh-task restore.

Входящая настоящая команда /start и ответ владельцу подтверждены по persisted command_results/outbox. Live OSM probe завершился ADAPTER_PROXYERROR; реальные leads не выдумывались. Startup draft сохранён; применение/публикация не заявлены.
