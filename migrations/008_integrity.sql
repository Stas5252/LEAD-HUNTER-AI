CREATE FUNCTION account_changed() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NEW.integration_id IS DISTINCT FROM OLD.integration_id OR NEW.channel IS DISTINCT FROM OLD.channel THEN
  IF EXISTS(SELECT 1 FROM content_items WHERE account_id=OLD.account_id AND state IN ('PUBLISHING','SUBMITTED','UNCERTAIN')) THEN RAISE EXCEPTION 'Reconcile pending publications before changing account';END IF;
  UPDATE content_items SET state='DRAFT',version=version+1,approved_version=NULL,approved_by=NULL,approved_at=NULL WHERE account_id=OLD.account_id AND state IN ('DRAFT','APPROVED','SCHEDULED');
 END IF;RETURN NEW;
END $$;
CREATE TRIGGER publishing_account_changed BEFORE UPDATE ON publishing_accounts FOR EACH ROW EXECUTE FUNCTION account_changed();
CREATE OR REPLACE FUNCTION valid_content_media(ids jsonb) RETURNS boolean LANGUAGE sql STABLE AS $$
 WITH RECURSIVE dependencies(asset_id) AS (
  SELECT jsonb_array_elements_text(ids)
  UNION
  SELECT child.value FROM dependencies d JOIN media_assets a ON a.asset_id=d.asset_id
   CROSS JOIN LATERAL jsonb_array_elements_text(coalesce(a.manifest->'rights'->'dependencies','[]'))child
 )
 SELECT jsonb_typeof(ids)='array' AND jsonb_array_length(ids)<=10 AND NOT EXISTS(
 SELECT 1 FROM dependencies d LEFT JOIN media_assets a USING(asset_id) WHERE a.asset_id IS NULL OR a.revoked_at IS NOT NULL);
$$;
ALTER FUNCTION content_action(jsonb) RENAME TO content_action_media;
CREATE FUNCTION content_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE i content_items;
BEGIN
 IF c->>'action' IN ('approve','schedule','check') THEN
  SELECT * INTO i FROM content_items WHERE content_id=(c->>'content_id')::uuid;
  IF FOUND THEN
   IF NOT i.is_demo AND EXISTS(SELECT 1 FROM jsonb_array_elements_text(i.media_ids) x JOIN media_assets a ON a.asset_id=x WHERE a.manifest->'is_demo'='true'::jsonb) THEN RETURN '{"status":"DEMO_MEDIA_CANNOT_PUBLISH","allowed":false}';END IF;
   IF EXISTS(SELECT 1 FROM publishing_accounts WHERE account_id=i.account_id AND channel='instagram') AND jsonb_array_length(i.media_ids)=0 THEN RETURN '{"status":"INSTAGRAM_NEEDS_MEDIA","allowed":false}';END IF;
  END IF;
 END IF;
 RETURN content_action_media(c);
END $$;
ALTER FUNCTION media_action(jsonb) RENAME TO media_action_base;
CREATE FUNCTION media_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE r jsonb;
BEGIN
 IF c->>'action'='verify_assets' THEN RETURN jsonb_build_object('allowed',valid_content_media(c->'asset_ids'));END IF;
 r:=media_action_base(c);
 IF c->>'action'='revoke' THEN
  UPDATE content_items SET approved_version=NULL,state='DRAFT',version=version+1 WHERE state IN ('DRAFT','APPROVED','SCHEDULED') AND NOT valid_content_media(media_ids);
 END IF;
 RETURN r;
END $$;
ALTER FUNCTION transport_action(jsonb) RENAME TO transport_action_base;
CREATE FUNCTION transport_action(c jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
BEGIN
 IF c->>'action' IN ('claim','check') THEN
  UPDATE notification_outbox SET state='CANCELLED',last_error='Media rights revoked' WHERE state IN ('PENDING','SENDING') AND payload->>'type'='media_preview' AND NOT valid_content_media(payload->'data'->'_asset_ids');
 END IF;RETURN transport_action_base(c);
END $$;
