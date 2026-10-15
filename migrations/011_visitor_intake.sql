CREATE TABLE visitor_sessions (
 user_id bigint PRIMARY KEY CHECK(user_id>0), session_id uuid NOT NULL DEFAULT gen_random_uuid(),
 stage text NOT NULL CHECK(stage IN ('CONSENT','REQUEST','CONTACT','DONE','CANCELLED')),
 entrypoint text NOT NULL CHECK(length(entrypoint)<=64), request_text text CHECK(length(request_text)<=2000),
 consent_at timestamptz, consent_version text, expires_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE visitor_submissions (
 submission_id uuid PRIMARY KEY, user_id bigint NOT NULL, import_id uuid NOT NULL REFERENCES import_requests,
 submitted_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX visitor_submission_user_time ON visitor_submissions(user_id,submitted_at);

-- Public intake is independent of owner commands. Only trusted Telegram private
-- updates enter here; no caller-controlled recipient or owner action is accepted.
CREATE FUNCTION visitor_update(u jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE m jsonb:=u->'message'; actor bigint; uid bigint; s app_settings; sess visitor_sessions;
 txt text; answer text; r jsonb; markup jsonb; old_result command_results;
 contact_value text; person text; request_id uuid; submission uuid; payload jsonb;
BEGIN
 IF m IS NULL OR m->'chat'->>'type' IS DISTINCT FROM 'private' OR coalesce((m->'from'->>'is_bot')::boolean,false) THEN RETURN '{"handled":false}';END IF;
 actor:=(m->'from'->>'id')::bigint;uid:=(u->>'update_id')::bigint;
 IF actor IS NULL OR actor<=0 OR uid IS NULL OR uid<0 OR actor IS DISTINCT FROM (m->'chat'->>'id')::bigint THEN RETURN '{"handled":false}';END IF;
 SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
 IF actor=s.admin_id OR s.stopped OR s.admin_id IS NULL THEN RETURN '{"handled":false}';END IF;
 SELECT * INTO old_result FROM command_results WHERE update_id=uid;
 IF FOUND THEN
  IF old_result.result->>'visitor_chat_id'=actor::text AND NOT old_result.queued THEN RETURN jsonb_build_object('handled',true,'result',old_result.result);END IF;
  RETURN jsonb_build_object('handled',true,'result',jsonb_build_object('ignored',true,'update_id',uid));
 END IF;
 txt:=trim(coalesce(m->>'text',''));
 IF length(txt)>2000 THEN txt:='';END IF;
 SELECT * INTO sess FROM visitor_sessions WHERE user_id=actor FOR UPDATE;
 IF txt ~ '^/start(@[A-Za-z0-9_]+)?( web_(general|landing|multi|expert|site|marketing|crm|sales|ai))?$' THEN
  IF (SELECT count(*) FROM visitor_submissions WHERE user_id=actor AND submitted_at>now()-interval '1 day')>=5 THEN
   answer:='За сутки уже принято 5 заявок. По существующей заявке свяжитесь со Станиславом: @Butov52.';
  ELSE
   INSERT INTO visitor_sessions(user_id,stage,entrypoint) VALUES(actor,'CONSENT',coalesce(nullif(split_part(txt,' ',2),''),'web_general'))
   ON CONFLICT(user_id) DO UPDATE SET session_id=gen_random_uuid(),stage='CONSENT',entrypoint=EXCLUDED.entrypoint,request_text=NULL,consent_at=NULL,consent_version=NULL,expires_at=now()+interval '24 hours',updated_at=now() RETURNING * INTO sess;
   answer:=E'Здравствуйте! Здесь можно оставить заявку Станиславу Бутову на сайт, маркетинг, CRM, продажи или ИИ-контент.\n\nДля обработки заявки и ответа Станислав получит её текст и выбранный вами контакт. Политика: https://stanislavweb.ru/privacy.html\n\nНажмите «Согласен», если согласны на такую обработку. Для выхода — «Отмена».';
  END IF;
 ELSIF sess.user_id IS NULL THEN RETURN '{"handled":false}';
 ELSIF txt IN ('/cancel','Отмена') THEN
  UPDATE visitor_sessions SET stage='CANCELLED',request_text=NULL,consent_at=NULL,consent_version=NULL,updated_at=now() WHERE user_id=actor RETURNING * INTO sess;
  answer:='Приём новой заявки отменён. Начать заново: /start. По ранее отправленной заявке: @Butov52.';
 ELSIF sess.expires_at<now() THEN
  UPDATE visitor_sessions SET stage='CANCELLED',request_text=NULL,consent_at=NULL,consent_version=NULL,updated_at=now() WHERE user_id=actor RETURNING * INTO sess;
  answer:='Время заполнения истекло. Начните заново: /start.';
 ELSIF txt LIKE '/%' THEN answer:='Это бот для заявок. Начать: /start. Отменить: /cancel.';
 ELSIF sess.stage='CONSENT' THEN
  IF txt='Согласен' THEN
   UPDATE visitor_sessions SET stage='REQUEST',consent_at=now(),consent_version='stanislavweb-privacy-2026-10-15',updated_at=now() WHERE user_id=actor RETURNING * INTO sess;
   answer:='Опишите задачу: что нужно сделать, для какого бизнеса и города. Можно указать бюджет и сроки. До 2000 символов.';
  ELSE answer:='Для передачи заявки Станиславу сначала нажмите «Согласен» или «Отмена».';END IF;
 ELSIF sess.stage='REQUEST' THEN
  IF length(txt)<3 THEN answer:='Опишите задачу текстом от 3 до 2000 символов. Отмена: /cancel.';
  ELSE
   UPDATE visitor_sessions SET request_text=txt,stage='CONTACT',updated_at=now() WHERE user_id=actor RETURNING * INTO sess;
   answer:='Как с вами связаться? Нажмите «Ответить мне в Telegram» или отправьте ваш телефон, email либо @username. Отмена: /cancel.';
  END IF;
 ELSIF sess.stage='CONTACT' THEN
  IF m->'contact' IS NOT NULL AND (m->'contact'->>'user_id')::bigint=actor THEN
   contact_value:=left(m->'contact'->>'phone_number',300);
  ELSIF txt='Ответить мне в Telegram' THEN
   contact_value:=CASE WHEN m->'from'->>'username' ~ '^[A-Za-z0-9_]{5,32}$' THEN 'https://t.me/'||(m->'from'->>'username') ELSE NULL END;
  ELSIF length(txt)<=300 AND (txt ~ '^@[A-Za-z0-9_]{5,32}$' OR txt ~ '^[^[:space:]@]+@[^[:space:]@]+\.[^[:space:]@]+$' OR (txt ~ '^\+?[0-9 ()-]+$' AND length(regexp_replace(txt,'[^0-9]','','g')) BETWEEN 7 AND 15)) THEN contact_value:=txt;
  END IF;
  IF contact_value IS NULL OR sess.consent_at IS NULL THEN answer:='Нужен доступный контакт. Если в Telegram нет публичного username, отправьте телефон, email или поделитесь своим номером кнопкой ниже.';
  ELSIF (SELECT count(*) FROM visitor_submissions WHERE user_id=actor AND submitted_at>now()-interval '1 day')>=5 THEN answer:='Лимит: 5 заявок в сутки. Связь со Станиславом: @Butov52.';
  ELSE
   submission:=sess.session_id;person:=left(trim(coalesce(m->'from'->>'first_name','')||' '||coalesce(m->'from'->>'last_name','')),180);
   payload:=jsonb_build_object('source','telegram_inbound','source_type','website_forms','source_url','https://t.me/LeadMagnetic67_bot?start='||sess.entrypoint,
    'external_id','visitor:'||submission,'company_name',coalesce(nullif(person,''),'Заявка в Telegram'),'public_contact',contact_value,
    'proof_quote',sess.request_text,'published_at',now(),'consent',true,'is_demo',false,
    'attribution',jsonb_build_object('intake','telegram_inbound','consent',true,'consent_at',sess.consent_at,'consent_version',sess.consent_version,'entrypoint',sess.entrypoint,'landing_url','https://stanislavweb.ru','origin_verified',false));
   INSERT INTO import_requests(payload,origin) VALUES(jsonb_build_array(payload),'telegram_inbound') RETURNING import_requests.request_id INTO request_id;
   INSERT INTO visitor_submissions(submission_id,user_id,import_id) VALUES(submission,actor,request_id);
   UPDATE visitor_sessions SET stage='DONE',request_text=NULL,updated_at=now() WHERE user_id=actor RETURNING * INTO sess;
   answer:='Заявка принята и передана Станиславу. Он ответит по указанному контакту. Номер: '||left(submission::text,8)||'. Связь напрямую: @Butov52.';
  END IF;
 ELSE answer:='Новая заявка: /start. Связаться напрямую: @Butov52.';
 END IF;
 IF sess.stage='CONSENT' THEN markup:='{"keyboard":[[{"text":"Согласен"},{"text":"Отмена"}]],"resize_keyboard":true,"one_time_keyboard":true}';
 ELSIF sess.stage='CONTACT' THEN markup:='{"keyboard":[[{"text":"Ответить мне в Telegram"}],[{"text":"Поделиться моим номером","request_contact":true}],[{"text":"Отмена"}]],"resize_keyboard":true,"one_time_keyboard":true}';
 ELSE markup:='{"remove_keyboard":true}';END IF;
 r:=jsonb_build_object('update_id',uid,'ignored',false,'text',answer,'reply_markup',markup,'visitor_chat_id',actor,'visitor_stage',coalesce(sess.stage,'CANCELLED'));
 INSERT INTO processed_updates(update_id) VALUES(uid) ON CONFLICT DO NOTHING;
 INSERT INTO command_results(update_id,result) VALUES(uid,r) ON CONFLICT DO NOTHING;
 RETURN jsonb_build_object('handled',true,'result',r);
END $$;

CREATE FUNCTION queue_visitor_replies(v_update bigint,messages jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE result command_results; actor bigint; item jsonb;i integer:=0;n integer:=0;
BEGIN
 SELECT * INTO result FROM command_results WHERE update_id=v_update FOR UPDATE;
 IF NOT FOUND OR result.queued THEN RETURN '{"ok":true,"queued":0}';END IF;
 actor:=(result.result->>'visitor_chat_id')::bigint;
 IF actor IS NULL OR NOT EXISTS(SELECT 1 FROM visitor_sessions WHERE user_id=actor) THEN RAISE EXCEPTION 'Unknown visitor';END IF;
 IF jsonb_typeof(messages)<>'array' OR jsonb_array_length(messages)>1 THEN RAISE EXCEPTION 'Invalid visitor replies';END IF;
 FOR item IN SELECT value FROM jsonb_array_elements(messages) LOOP
  IF item ? '_method' OR item ? 'chat_id' THEN RAISE EXCEPTION 'Visitor reply cannot override destination or method';END IF;
  INSERT INTO notification_outbox(dedupe_key,payload) VALUES('visitor-update:'||v_update||':'||i,jsonb_build_object('type','visitor_reply','visitor_chat_id',actor,'data',item)) ON CONFLICT(dedupe_key) DO NOTHING;
  IF FOUND THEN n:=n+1;END IF;i:=i+1;
 END LOOP;
 UPDATE command_results SET queued=true WHERE update_id=v_update;
 UPDATE app_settings SET telegram_offset=greatest(telegram_offset,v_update+1) WHERE id=true;
 RETURN jsonb_build_object('ok',true,'queued',n);
END $$;
ALTER FUNCTION queue_replies(bigint,jsonb) RENAME TO queue_owner_replies;
CREATE FUNCTION queue_replies(v_update bigint,messages jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM command_results WHERE update_id=v_update AND result ? 'visitor_chat_id') THEN RETURN queue_visitor_replies(v_update,messages);END IF;
 RETURN queue_owner_replies(v_update,messages);
END $$;
ALTER FUNCTION transport_action(jsonb) RENAME TO transport_action_before_visitors;
CREATE FUNCTION transport_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE r jsonb;j jsonb;jobs jsonb:='[]';actor bigint;
BEGIN
 r:=transport_action_before_visitors(c);
 IF c->>'action'='claim' THEN
  FOR j IN SELECT value FROM jsonb_array_elements(coalesce(r->'jobs','[]')) LOOP
   IF j->'payload'->>'type'='visitor_reply' THEN
    actor:=(j->'payload'->>'visitor_chat_id')::bigint;
    IF NOT EXISTS(SELECT 1 FROM visitor_sessions WHERE user_id=actor) THEN
     UPDATE notification_outbox SET state='CANCELLED',last_error='Unknown visitor destination' WHERE id=(j->>'id')::bigint;CONTINUE;
    END IF;
    j:=j||jsonb_build_object('chat_id',actor);
   END IF;
   jobs:=jobs||jsonb_build_array(j);
  END LOOP;
  r:=r||jsonb_build_object('jobs',jobs);
 END IF;
 RETURN r;
END $$;
UPDATE source_registry SET access_status='TELEGRAM_INTAKE_READY',detail='Статический сайт → Telegram deep link → явное согласие → задача → контакт → CRM. Подписанный HTTP webhook формы включается отдельно.' WHERE source_type='website_forms';

-- A voluntarily submitted inbound request is already qualified by its consent
-- flow. It must reach the owner without model fees or model-based filtering.
ALTER FUNCTION reserve_score(jsonb,text,integer,jsonb) RENAME TO reserve_score_before_visitors;
CREATE FUNCTION reserve_score(input jsonb,key text,input_tokens integer,body jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
 IF input->'lead'->>'source'='telegram_inbound' AND input->'lead'->>'source_type'='website_forms'
  AND input->'lead'->'attribution'->>'intake'='telegram_inbound' AND input->'lead'->'attribution'->'consent'='true'::jsonb THEN
  RETURN input||jsonb_build_object('mode','FALLBACK','reason','consented inbound; no model call');
 END IF;
 RETURN reserve_score_before_visitors(input,key,input_tokens,body);
END $$;
