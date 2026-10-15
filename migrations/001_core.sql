CREATE TABLE app_settings (
  id boolean PRIMARY KEY DEFAULT true CHECK(id),
  stopped boolean NOT NULL DEFAULT false,
  admin_id bigint,
  max_leads_per_run integer NOT NULL DEFAULT 100 CHECK(max_leads_per_run BETWEEN 1 AND 1000),
  daily_api_budget_usd numeric(12,6) NOT NULL DEFAULT 1 CHECK(daily_api_budget_usd >= 0),
  max_llm_calls_per_day integer NOT NULL DEFAULT 50 CHECK(max_llm_calls_per_day >= 0),
  telegram_offset bigint NOT NULL DEFAULT 0,
  updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO app_settings(id) VALUES(true);
CREATE TABLE source_registry (
  source_type text PRIMARY KEY, name text NOT NULL, enabled boolean NOT NULL DEFAULT false,
  access_status text NOT NULL, detail text NOT NULL
);
INSERT INTO source_registry VALUES
 ('maps_demo','Карты: DEMO',true,'DEMO','Вымышленные примеры; не настоящий поиск'),
 ('maps','Карты и локальный бизнес',false,'NEEDS_ACCESS','Разрешённый провайдер или импорт владельца'),
 ('new_business','Новые бизнесы',false,'PLANNED','Официальная выгрузка/разрешённый агрегатор'),
 ('telegram_monitor','Telegram-сообщества',false,'PLANNED','Только сообщества с предоставленным доступом'),
 ('audit','Аудит и предложение',false,'PLANNED','В MVP черновик по имеющимся доказательствам'),
 ('niche','Нишевые решения',true,'RULES_ONLY','Подбор предложения; портфолио не выдумывается'),
 ('subcontract','Субподряд студий',false,'PLANNED','Импорт публичных запросов'),
 ('website_forms','Формы собственного сайта',false,'PLANNED','Требуется форма и согласие'),
 ('partners','Блогеры и партнёры',false,'PLANNED','Импорт публичных предложений'),
 ('content','Собственный контент',false,'PLANNED','Черновики и Postiz на следующем этапе'),
 ('threads_search','Threads Search',false,'NEEDS_APP_REVIEW','Meta permission threads_keyword_search'),
 ('instagram','Instagram',false,'PLANNED','Professional account и официальный API/Postiz'),
 ('video','Video Factory',false,'PLANNED','Разрешённые клипы и монтаж, этап C');
CREATE TABLE leads (
  lead_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  dedupe_key text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(), last_seen_at timestamptz NOT NULL DEFAULT now(),
  source text NOT NULL, source_type text NOT NULL, source_url text NOT NULL,
  company_name text NOT NULL, niche text NOT NULL DEFAULT '', city text NOT NULL DEFAULT '',
  website text, website_status text NOT NULL DEFAULT 'UNKNOWN',
  public_contact text, contact_source_url text,
  need_detected text NOT NULL DEFAULT '', proof_quote text NOT NULL DEFAULT '',
  score_0_100 integer NOT NULL CHECK(score_0_100 BETWEEN 0 AND 100),
  confidence_0_1 numeric NOT NULL CHECK(confidence_0_1 BETWEEN 0 AND 1),
  classification text NOT NULL CHECK(classification IN ('DIRECT_REQUEST','LIKELY_NEED','PARTNER','COMPETITOR','IRRELEVANT')),
  why_relevant text NOT NULL, offer_type text NOT NULL, draft_message text NOT NULL DEFAULT '',
  draft_version integer NOT NULL DEFAULT 1,
  status text NOT NULL DEFAULT 'NEW' CHECK(status IN ('NEW','REVIEW','APPROVED','CONTACTED','REPLIED','NEGOTIATION','WON','LOST','DNC')),
  next_action text NOT NULL DEFAULT 'Проверить источник', next_followup_at timestamptz,
  owner_approved boolean NOT NULL DEFAULT false,
  estimated_cost numeric(12,6) NOT NULL DEFAULT 0,
  attribution jsonb NOT NULL DEFAULT '{}', tags jsonb NOT NULL DEFAULT '[]',
  is_demo boolean NOT NULL DEFAULT false, content_hash text NOT NULL,
  scoring_method text NOT NULL DEFAULT 'heuristic', data jsonb NOT NULL
);
CREATE TABLE lead_events (
  event_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  lead_id uuid REFERENCES leads, created_at timestamptz NOT NULL DEFAULT now(),
  kind text NOT NULL, detail jsonb NOT NULL DEFAULT '{}'
);
CREATE TABLE notification_outbox (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  lead_id uuid REFERENCES leads, dedupe_key text NOT NULL UNIQUE,
  payload jsonb NOT NULL, state text NOT NULL DEFAULT 'PENDING'
    CHECK(state IN ('PENDING','SENDING','SENT','UNCERTAIN','FAILED','CANCELLED')),
  attempts integer NOT NULL DEFAULT 0, next_attempt_at timestamptz NOT NULL DEFAULT now(),
  last_error text, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE processed_updates (update_id bigint PRIMARY KEY, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE action_approvals (
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY, lead_id uuid NOT NULL REFERENCES leads,
  draft_version integer NOT NULL, action text NOT NULL CHECK(action='manual_outreach'),
  approved_by bigint NOT NULL, approved_at timestamptz NOT NULL DEFAULT now(),
  revoked_at timestamptz, UNIQUE(lead_id,draft_version,action)
);
CREATE TABLE llm_cache (cache_key text PRIMARY KEY, result jsonb NOT NULL, created_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE daily_usage (
  day date PRIMARY KEY, calls integer NOT NULL DEFAULT 0, reserved_usd numeric(12,6) NOT NULL DEFAULT 0
);
CREATE INDEX leads_score_created ON leads(score_0_100 DESC,created_at DESC);
CREATE INDEX notification_pending ON notification_outbox(state,next_attempt_at);
