CREATE FUNCTION content_has_demo(ids jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH RECURSIVE dependencies(asset_id) AS (SELECT jsonb_array_elements_text(ids) UNION SELECT child.value FROM dependencies d JOIN media_assets a ON a.asset_id=d.asset_id CROSS JOIN LATERAL jsonb_array_elements_text(coalesce(a.manifest->'rights'->'dependencies','[]'))child)
 SELECT EXISTS(SELECT 1 FROM dependencies d JOIN media_assets a USING(asset_id) WHERE a.manifest->'is_demo'='true'::jsonb);
$$;
ALTER FUNCTION content_action(jsonb) RENAME TO content_action_before_review;
CREATE FUNCTION content_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE i content_items;
BEGIN
 -- Serialize rights checks with revoke, STOP, claim and approval before reading.
 PERFORM 1 FROM app_settings WHERE id=true FOR UPDATE;
 IF c->>'action' IN ('approve','schedule','check') THEN
  SELECT * INTO i FROM content_items WHERE content_id=(c->>'content_id')::uuid FOR UPDATE;
  IF FOUND THEN
   IF NOT valid_content_media(i.media_ids) THEN RETURN '{"status":"MEDIA_RIGHTS_REQUIRED","allowed":false}';END IF;
   IF NOT i.is_demo AND content_has_demo(i.media_ids) THEN RETURN '{"status":"DEMO_MEDIA_CANNOT_PUBLISH","allowed":false}';END IF;
   IF c->>'action'='check' AND NOT EXISTS(SELECT 1 FROM publishing_accounts WHERE account_id=i.account_id AND enabled) THEN RETURN '{"status":"ACCOUNT_DISABLED","allowed":false}';END IF;
  END IF;
 END IF;
 RETURN content_action_before_review(c);
END $$;
ALTER FUNCTION monitor_update(jsonb) RENAME TO monitor_update_before_review;
CREATE FUNCTION monitor_update(u jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE m jsonb;v_chat bigint;v_text text;identity text;l leads;
BEGIN
 PERFORM 1 FROM app_settings WHERE id=true FOR UPDATE;
 m:=coalesce(u->'edited_channel_post',u->'edited_message');
 IF m IS NOT NULL AND NOT EXISTS(SELECT 1 FROM processed_updates WHERE update_id=(u->>'update_id')::bigint) THEN
  v_chat:=(m->'chat'->>'id')::bigint;v_text:=coalesce(m->>'text',m->>'caption','');
  IF EXISTS(SELECT 1 FROM monitored_chats WHERE chat_id=v_chat AND enabled) AND (length(v_text) NOT BETWEEN 3 AND 12000 OR (SELECT stopped FROM app_settings WHERE id=true)) THEN
   identity:=encode(digest('real:external:telegram_monitor:'||v_chat||':'||(m->>'message_id'),'sha256'),'hex');
   FOR l IN SELECT * FROM leads WHERE dedupe_key=identity FOR UPDATE LOOP
    UPDATE action_approvals SET revoked_at=now() WHERE lead_id=l.lead_id AND revoked_at IS NULL;
    UPDATE notification_outbox SET state='CANCELLED' WHERE lead_id=l.lead_id AND state IN ('PENDING','SENDING');
    UPDATE leads SET owner_approved=false,draft_version=draft_version+1,draft_message='',proof_quote='',need_detected='',classification='IRRELEVANT',score_0_100=0,
     why_relevant='Источник изменён: запрос отсутствует, не помещается в лимит или изменён во время STOP; нужна повторная проверка.',
     status=CASE WHEN status IN ('NEW','REVIEW','APPROVED') THEN 'REVIEW' ELSE status END,next_followup_at=NULL,
     content_hash=encode(digest(content_hash||':'||(u->>'update_id'),'sha256'),'hex'),
     data=data||jsonb_build_object('text','','proof_quote','','source_content_removed',true) WHERE lead_id=l.lead_id;
    INSERT INTO lead_events(lead_id,kind) VALUES(l.lead_id,'SOURCE_EVIDENCE_INVALIDATED');
   END LOOP;
  END IF;
 END IF;
 RETURN monitor_update_before_review(u);
END $$;
CREATE OR REPLACE FUNCTION enqueue_configured(kind text,force_run boolean DEFAULT false) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE c connector_configs;
BEGIN
 PERFORM 1 FROM app_settings WHERE id=true FOR UPDATE;
 SELECT * INTO c FROM connector_configs WHERE source_type=kind FOR UPDATE;
 IF NOT FOUND OR NOT c.enabled OR c.config='{}'::jsonb THEN RETURN '{"status":"NEEDS_CONFIGURATION"}';END IF;
 IF c.last_enqueued_at>now()-interval '5 minutes' OR (NOT force_run AND c.last_enqueued_at>now()-make_interval(mins=>c.interval_minutes)) THEN RETURN '{"status":"CACHED"}';END IF;
 UPDATE connector_configs SET last_enqueued_at=now() WHERE source_type=kind;
 RETURN enqueue_connector(kind,c.config||c.cursor||jsonb_build_object('_config_hash',encode(digest(c.config::text,'sha256'),'hex')),'schedule:'||kind||':'||gen_random_uuid()::text);
END $$;
ALTER FUNCTION connector_action(jsonb) RENAME TO connector_action_before_review;
CREATE FUNCTION connector_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE j connector_jobs;cfg connector_configs;
BEGIN
 PERFORM 1 FROM app_settings WHERE id=true FOR UPDATE;
 IF c->>'action'='finish' AND c ? 'cursor' THEN
  SELECT * INTO j FROM connector_jobs WHERE job_id=(c->>'job_id')::uuid;
  SELECT * INTO cfg FROM connector_configs WHERE source_type=j.source_type;
  IF j.config->>'_config_hash' IS DISTINCT FROM encode(digest(cfg.config::text,'sha256'),'hex') THEN c:=c-'cursor';END IF;
 END IF;
 RETURN connector_action_before_review(c);
END $$;
