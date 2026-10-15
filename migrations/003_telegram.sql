CREATE TABLE IF NOT EXISTS command_results(update_id bigint PRIMARY KEY REFERENCES processed_updates ON DELETE CASCADE,result jsonb NOT NULL,queued boolean NOT NULL DEFAULT false);
CREATE OR REPLACE FUNCTION handle_command(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings; l leads; v_id bigint; v_cmd text; v_text text:=''; v_rows jsonb:='[]';
  v_version integer; v_payload jsonb; v_source text; v_niche text; v_city text; v_result jsonb;
BEGIN
  SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
  v_id:=(c->>'update_id')::bigint;
  IF v_id IS NULL THEN RETURN jsonb_build_object('ignored',true); END IF;
  INSERT INTO processed_updates(update_id) VALUES(v_id) ON CONFLICT DO NOTHING;
  IF NOT FOUND THEN
    SELECT result INTO v_result FROM command_results WHERE update_id=v_id AND NOT queued;
    IF FOUND THEN RETURN v_result; END IF;
    RETURN jsonb_build_object('ignored',true,'update_id',v_id);
  END IF;
  IF coalesce((c->>'ignored')::boolean,true) OR s.admin_id IS NULL OR
    (c->>'user_id')::bigint IS DISTINCT FROM s.admin_id OR (c->>'chat_id')::bigint IS DISTINCT FROM s.admin_id
    OR c->>'chat_type'<>'private' THEN RETURN jsonb_build_object('ignored',true,'update_id',v_id); END IF;
  v_cmd:=c->>'command';
  IF v_cmd='stop' THEN
    UPDATE app_settings SET stopped=true,updated_at=now() WHERE id=true;
    v_text:='STOP: сбор, AI-вызовы и очередь остановлены. Возобновление: /resume';
  ELSIF v_cmd='resume' THEN
    UPDATE app_settings SET stopped=false,updated_at=now() WHERE id=true;
    v_text:='Работа возобновлена владельцем.';
  ELSIF v_cmd='start' THEN
    v_text:='LEAD HUNTER AI · '||CASE WHEN s.stopped THEN 'STOPPED' ELSE 'RUNNING' END||E'\n/find maps_demo — вымышленные примеры\n/today /leads /sources /stats /budget\n/lead ID · /draft ID текст · /approve ID версия · /reject ID\n/stop /resume\nВнешняя отправка КП и публикации отключены.';
  ELSIF v_cmd IN ('lead','draft','approve','reject','edit') THEN
    SELECT * INTO l FROM leads WHERE lead_id=(c->>'lead_id')::uuid FOR UPDATE;
    IF NOT FOUND THEN v_text:='Лид не найден.';
    ELSIF v_cmd='reject' THEN
      UPDATE leads SET status='DNC',owner_approved=false WHERE lead_id=l.lead_id;
      UPDATE action_approvals SET revoked_at=now() WHERE lead_id=l.lead_id AND revoked_at IS NULL;
      UPDATE notification_outbox SET state='CANCELLED' WHERE lead_id=l.lead_id AND state IN ('PENDING','SENDING');
      INSERT INTO lead_events(lead_id,kind) VALUES(l.lead_id,'DNC');
      v_text:='DNC: не беспокоить. Ожидающие действия отменены.';
    ELSIF v_cmd='lead' THEN v_rows:=jsonb_build_array(to_jsonb(l));
    ELSIF l.status='DNC' THEN v_text:='DNC: действия по этому лиду запрещены.';
    ELSIF s.stopped AND v_cmd IN ('draft','approve') THEN v_text:='STOPPED. Сначала /resume.';
    ELSIF v_cmd='edit' THEN v_text:='/draft '||l.lead_id::text||' Новый текст черновика';
    ELSIF v_cmd='draft' THEN
      UPDATE leads SET draft_message=CASE WHEN coalesce(c->>'draft','')<>'' THEN left(c->>'draft',2000) ELSE draft_message END,
        draft_version=draft_version+1,owner_approved=false,
        status=CASE WHEN status='APPROVED' THEN 'REVIEW' ELSE status END
        WHERE lead_id=l.lead_id RETURNING * INTO l;
      UPDATE action_approvals SET revoked_at=now() WHERE lead_id=l.lead_id AND revoked_at IS NULL;
      INSERT INTO lead_events(lead_id,kind) VALUES(l.lead_id,'DRAFT_CHANGED');
      v_rows:=jsonb_build_array(to_jsonb(l));
    ELSE
      v_version:=(c->>'version')::integer;
      IF v_version IS NULL OR v_version<1 THEN v_text:='Укажите явную версию черновика: /approve ID версия';
      ELSIF v_version<>l.draft_version THEN v_text:='Черновик изменился: откройте свежую карточку и одобрите её версию.';
      ELSE
        INSERT INTO action_approvals(lead_id,draft_version,action,approved_by)
          VALUES(l.lead_id,v_version,'manual_outreach',s.admin_id)
          ON CONFLICT(lead_id,draft_version,action) DO UPDATE SET revoked_at=NULL,approved_at=now();
        UPDATE leads SET owner_approved=true,status='APPROVED',next_action='Ручная отправка владельцем'
          WHERE lead_id=l.lead_id;
        INSERT INTO lead_events(lead_id,kind,detail) VALUES(l.lead_id,'APPROVED',jsonb_build_object('version',v_version));
        v_text:='Одобрена версия '||v_version||'. КП НЕ отправлено: отправка в этапе A только вручную.';
      END IF;
    END IF;
  ELSIF v_cmd IN ('leads','today') THEN
    SELECT coalesce(jsonb_agg(to_jsonb(q)),'[]') INTO v_rows FROM (
      SELECT * FROM leads WHERE status<>'DNC' AND score_0_100>=40
        AND (v_cmd<>'today' OR (created_at AT TIME ZONE 'Europe/Saratov')::date=(now() AT TIME ZONE 'Europe/Saratov')::date)
        AND (coalesce(c->>'args','') NOT IN ('high','medium') OR
          ((c->>'args'='high' AND score_0_100>=90) OR (c->>'args'='medium' AND score_0_100 BETWEEN 40 AND 89)))
      ORDER BY score_0_100 DESC,created_at DESC LIMIT 5) q;
    IF jsonb_array_length(v_rows)=0 THEN v_text:='Подходящих лидов пока нет. /find maps_demo'; END IF;
  ELSIF v_cmd='find' THEN
    IF s.stopped THEN v_text:='STOPPED. Сначала /resume.';
    ELSE
      v_source:=coalesce(nullif(split_part(c->>'args',' ',1),''),'maps_demo');
      IF v_source NOT IN ('maps_demo','demo') THEN
        SELECT access_status||': '||detail INTO v_text FROM source_registry WHERE source_type=v_source;
        v_text:=coalesce(v_text,'Источник недоступен. /sources');
      ELSE
        v_niche:=trim(split_part(substring(coalesce(c->>'args','') FROM position(' ' IN coalesce(c->>'args',''))+1),'|',1));
        IF position(' ' IN coalesce(c->>'args',''))=0 THEN v_niche:=''; END IF;
        v_city:=trim(split_part(coalesce(c->>'args',''),'|',2));
        SELECT coalesce(jsonb_agg(d),'[]') INTO v_payload FROM demo_dataset, jsonb_array_elements(payload) d
          WHERE (v_niche='' OR position(lower(v_niche) IN lower(d->>'niche'))>0)
            AND (v_city='' OR position(lower(v_city) IN lower(d->>'city'))>0);
        INSERT INTO import_requests(payload,origin) VALUES(v_payload,'telegram_demo');
        v_text:='DEMO-поиск поставлен в очередь: '||jsonb_array_length(v_payload)||' вымышленных записей. Сборщик обработает его в течение минуты. Повторные лиды не уведомляются снова.';
      END IF;
    END IF;
  ELSIF v_cmd='sources' THEN
    SELECT string_agg(name||' — '||access_status,E'\n' ORDER BY source_type) INTO v_text FROM source_registry;
  ELSIF v_cmd='stats' THEN
    SELECT 'Всего: '||count(*)||' · DEMO: '||count(*) FILTER(WHERE is_demo)||
      ' · score≥70: '||count(*) FILTER(WHERE score_0_100>=70)||
      ' · REPLIED: '||count(*) FILTER(WHERE status='REPLIED')||
      ' · WON: '||count(*) FILTER(WHERE status='WON')||
      ' · DNC: '||count(*) FILTER(WHERE status='DNC') INTO v_text FROM leads;
  ELSIF v_cmd='budget' THEN
    SELECT 'Лимит/сутки: $'||s.daily_api_budget_usd||' · вызовов: '||s.max_llm_calls_per_day||
      ' · использовано: '||coalesce(u.calls,0)||' · резерв: $'||coalesce(u.reserved_usd,0)||
      E'\nРезерв — приблизительная защита, не биллинг провайдера.' INTO v_text
      FROM (SELECT 1) q LEFT JOIN daily_usage u ON u.day=(now() AT TIME ZONE 'UTC')::date;
  ELSIF v_cmd IN ('threads','instagram','videos') THEN
    v_text:=CASE v_cmd WHEN 'threads' THEN 'Threads Search: NEEDS_APP_REVIEW. Публикации: PLANNED.'
      WHEN 'instagram' THEN 'Instagram: PLANNED; нужен Professional account и официальный API/Postiz.'
      ELSE 'Video Factory: PLANNED, этап C. Платная генерация отключена.' END;
  ELSE v_text:='Команды: /start /today /find maps_demo /leads /lead ID /draft ID текст /approve ID версия /reject ID /sources /stats /budget /stop /resume';
  END IF;
  v_result:=jsonb_build_object('update_id',v_id,'ignored',false,'text',v_text,'leads',v_rows,'callback_id',c->>'callback_id');
  INSERT INTO command_results(update_id,result) VALUES(v_id,v_result);
  RETURN v_result;
END $$;

CREATE OR REPLACE FUNCTION queue_replies(v_update bigint,messages jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE item jsonb; i integer:=0; n integer:=0;
BEGIN
  IF v_update IS NOT NULL THEN
    FOR item IN SELECT value FROM jsonb_array_elements(messages) LOOP
      INSERT INTO notification_outbox(dedupe_key,payload)
        VALUES('update:'||v_update||':'||i,jsonb_build_object('type','message','data',item))
        ON CONFLICT(dedupe_key) DO NOTHING;
      IF FOUND THEN n:=n+1; END IF; i:=i+1;
    END LOOP;
  END IF;
  UPDATE command_results SET queued=true WHERE update_id=v_update;
  UPDATE app_settings SET telegram_offset=greatest(telegram_offset,v_update+1) WHERE id=true AND v_update IS NOT NULL;
  RETURN jsonb_build_object('ok',true,'queued',n);
END $$;

CREATE OR REPLACE FUNCTION transport_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings; job notification_outbox; v_jobs jsonb:='[]'; v_allowed boolean;
BEGIN
  SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
  IF c->>'action'='status' THEN RETURN jsonb_build_object('offset',s.telegram_offset,'admin_id',s.admin_id,'stopped',s.stopped); END IF;
  IF c->>'action'='claim' THEN
    IF s.admin_id IS NULL THEN RETURN jsonb_build_object('jobs','[]'::jsonb); END IF;
    UPDATE notification_outbox SET state='UNCERTAIN',last_error='Delivery interrupted; review before any manual retry'
      WHERE state='SENDING' AND next_attempt_at<now()-interval '10 minutes';
    FOR job IN SELECT o.* FROM notification_outbox o LEFT JOIN leads l ON l.lead_id=o.lead_id
      WHERE o.state='PENDING' AND o.next_attempt_at<=now() AND (l.lead_id IS NULL OR l.status<>'DNC')
        AND (NOT s.stopped OR o.payload->>'type'='message')
      ORDER BY o.id LIMIT 5 FOR UPDATE OF o SKIP LOCKED LOOP
      UPDATE notification_outbox SET state='SENDING',attempts=attempts+1,next_attempt_at=now() WHERE id=job.id;
      v_jobs:=v_jobs||jsonb_build_array(jsonb_build_object('id',job.id,'payload',job.payload,'chat_id',s.admin_id));
    END LOOP;
    RETURN jsonb_build_object('jobs',v_jobs);
  ELSIF c->>'action'='check' THEN
    SELECT EXISTS(SELECT 1 FROM notification_outbox o LEFT JOIN leads l ON l.lead_id=o.lead_id
      WHERE o.id=(c->>'id')::bigint AND o.state='SENDING' AND (l.lead_id IS NULL OR l.status<>'DNC')
        AND (NOT s.stopped OR o.payload->>'type'='message')) INTO v_allowed;
    RETURN jsonb_build_object('allowed',v_allowed);
  ELSIF c->>'action'='report' THEN
    IF c->>'state' NOT IN ('SENT','UNCERTAIN','FAILED','PENDING') THEN RAISE EXCEPTION 'Invalid delivery state'; END IF;
    UPDATE notification_outbox SET state=CASE WHEN c->>'state'='PENDING' AND attempts>=3 THEN 'FAILED' ELSE c->>'state' END,
      last_error=left(c->>'error',300),next_attempt_at=now()+make_interval(secs=>least(3600,greatest(5,coalesce((c->>'retry_after')::integer,30))))
      WHERE id=(c->>'id')::bigint AND state='SENDING';
    RETURN jsonb_build_object('ok',true);
  END IF;
  RAISE EXCEPTION 'Unknown transport action';
END $$;
