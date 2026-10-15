# Operations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Завершить согласованный проект в текущей сессии; live-подключения честно отделять от проверок на контролируемых данных.

**Architecture:** n8n планирует независимые сценарии, PostgreSQL хранит задания и подтверждения. Небольшой Python worker выполняет ограниченные HTTP/media адаптеры, общий существующий intake сохраняет leads.

**Tech Stack:** n8n 2.43.6, PostgreSQL 17, Python 3.12+, Node 24, FFmpeg, Pillow, httpx/HTML parser.

## Global Constraints

- AUTOPUBLISH=false, AUTO_OUTREACH=false, VIDEO_GENERATION_PAID=false.
- DAILY_API_BUDGET_USD=1, MAX_LLM_CALLS_PER_DAY=50, MAX_LEADS_PER_RUN=100, MAX_PUBLIC_POSTS_PER_DAY=2.
- STOP, DNC, idempotency, versioned approvals; UNKNOWN не означает отсутствие сайта.
- Никаких секретов в логах; TLS и proxy сохраняются; запрещены private/metadata URL.
- Внешние публикации/оплаты/аккаунты требуют отдельного явного решения. Пользователь разрешил исполнение всех планов здесь без повторных согласований.

## Review Focus

- Падение worker после внешнего POST: UNCERTAIN и сверка, без повторной публикации.
- Изменение/правка исходного сообщения: тот же lead, старое одобрение отозвано.
- Злонамеренный URL/redirect или HTML: fail closed, лимиты и отсутствие credentials.
- Удалённый/изменённый media asset: нельзя отправить старое одобрение или выйти за media root.
- STOP во время работы: результат можно сохранить, новую внешнюю отправку нельзя начать.

**Spec:** ../specs/2026-10-15-completion-design.md

---

### Task 8: Безопасное развёртывание и полная проверка

**Files:** scripts/import-workflows.py; Dockerfile.worker; docker-compose.yml; scripts/cloud-compose.py; docs/*; tests/test_operations.py

**Interfaces:** backup workflow IDs before overwrite; worker health; secure provider config; reusable onboarding. Существующий intake принимает массив raw lead dictionaries; нормализация и скоринг остаются в n8n.

- [ ] Написать поведенческие тесты: TLS/proxy CA; backup/restore app+n8n+media registry; повторная установка; resource limits; Windows/Ubuntu docs; новый полный набор тестов; независимый final review.
- [ ] Запустить целевые тесты до реализации. Expected: FAIL на отсутствующей новой возможности.
- [ ] Реализовать названные интерфейсы в указанных файлах, сохранив существующие ограничения.
- [ ] Запустить целевые тесты и существующий suite. Expected: PASS, реальные результаты записаны в ledger.
- [ ] Зафиксировать результат задачи в docs/IMPLEMENTATION_LOG.md; локальные git checkpoints только после secret scan, без push.


Runtime/session completed. Restore/new containers/fresh deploy remain environment-blocked by ENOSPC; see docs/STATUS.md. Full source/test history recorded; no automatic publication/push.
