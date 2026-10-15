CREATE TABLE import_requests (
  request_id uuid PRIMARY KEY DEFAULT gen_random_uuid(), payload jsonb NOT NULL,
  origin text NOT NULL DEFAULT 'manual', created_at timestamptz NOT NULL DEFAULT now(),
  state text NOT NULL DEFAULT 'PENDING' CHECK(state IN ('PENDING','RUNNING','STORED','DONE','FAILED')),
  result jsonb, updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE demo_dataset(id boolean PRIMARY KEY DEFAULT true CHECK(id),payload jsonb NOT NULL);

CREATE FUNCTION claim_import(fallback jsonb) RETURNS TABLE(request_id uuid,payload jsonb,max_leads integer)
LANGUAGE plpgsql AS $$
DECLARE r import_requests; s app_settings;
BEGIN
  SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
  IF s.stopped THEN RETURN; END IF;
  SELECT * INTO r FROM import_requests q WHERE q.state='PENDING' ORDER BY q.created_at LIMIT 1 FOR UPDATE SKIP LOCKED;
  IF NOT FOUND THEN
    IF fallback IS NULL THEN RETURN; END IF;
    INSERT INTO import_requests(payload,origin) VALUES(fallback,'manual_demo') RETURNING * INTO r;
  END IF;
  UPDATE import_requests q SET state='RUNNING',updated_at=now() WHERE q.request_id=r.request_id;
  RETURN QUERY SELECT r.request_id,r.payload,s.max_leads_per_run;
END $$;

CREATE OR REPLACE FUNCTION ingest_batch(batch jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings; d jsonb; l leads; changed boolean; inserted integer:=0; rows jsonb:='[]';
BEGIN
  SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
  IF s.stopped THEN RAISE EXCEPTION 'STOPPED'; END IF;
  IF jsonb_typeof(batch) <> 'array' OR jsonb_array_length(batch)>s.max_leads_per_run THEN
    RAISE EXCEPTION 'Invalid batch or lead limit exceeded';
  END IF;
  FOR d IN SELECT value FROM jsonb_array_elements(batch) LOOP
    SELECT * INTO l FROM leads WHERE dedupe_key=d->>'dedupe_key' FOR UPDATE;
    IF FOUND THEN
      changed:=l.content_hash IS DISTINCT FROM d->>'content_hash';
      IF changed THEN
        UPDATE action_approvals SET revoked_at=now() WHERE lead_id=l.lead_id AND revoked_at IS NULL;
      END IF;
      UPDATE leads SET last_seen_at=now(),
        source=d->>'source',source_type=d->>'source_type',source_url=d->>'source_url',
        company_name=d->>'company_name',niche=coalesce(d->>'niche',''),city=coalesce(d->>'city',''),
        website=d->>'website',website_status=coalesce(d->>'website_status','UNKNOWN'),
        public_contact=d->>'public_contact',contact_source_url=d->>'contact_source_url',
        offer_type=d->>'offer_type',attribution=coalesce(d->'attribution','{}'),tags=coalesce(d->'tags','[]'),
        estimated_cost=leads.estimated_cost+coalesce((d->>'estimated_cost')::numeric,0),
        content_hash=d->>'content_hash', data=d,
        proof_quote=d->>'proof_quote', need_detected=coalesce(d->>'need_detected',''),
        score_0_100=(d->>'score_0_100')::integer,confidence_0_1=(d->>'confidence_0_1')::numeric,
        classification=d->>'classification',why_relevant=d->>'why_relevant',
        scoring_method=coalesce(d->>'scoring_method','heuristic'),
        draft_message=CASE WHEN changed THEN d->>'draft_message' ELSE leads.draft_message END,
        draft_version=leads.draft_version+CASE WHEN changed THEN 1 ELSE 0 END,
        owner_approved=CASE WHEN changed THEN false ELSE leads.owner_approved END,
        status=CASE WHEN leads.status='APPROVED' AND changed THEN 'REVIEW' ELSE leads.status END
      WHERE lead_id=l.lead_id RETURNING * INTO l;
    ELSE
      INSERT INTO leads(dedupe_key,source,source_type,source_url,company_name,niche,city,website,website_status,
        public_contact,contact_source_url,need_detected,proof_quote,score_0_100,confidence_0_1,classification,
        why_relevant,offer_type,draft_message,status,next_action,attribution,tags,is_demo,content_hash,scoring_method,estimated_cost,data)
      VALUES(d->>'dedupe_key',d->>'source',d->>'source_type',d->>'source_url',d->>'company_name',
        coalesce(d->>'niche',''),coalesce(d->>'city',''),d->>'website',coalesce(d->>'website_status','UNKNOWN'),
        d->>'public_contact',d->>'contact_source_url',coalesce(d->>'need_detected',''),d->>'proof_quote',
        (d->>'score_0_100')::integer,(d->>'confidence_0_1')::numeric,d->>'classification',d->>'why_relevant',
        d->>'offer_type',d->>'draft_message',coalesce(d->>'status','NEW'),coalesce(d->>'next_action','Проверить источник'),
        coalesce(d->'attribution','{}'),coalesce(d->'tags','[]'),coalesce((d->>'is_demo')::boolean,false),
        d->>'content_hash',coalesce(d->>'scoring_method','heuristic'),coalesce((d->>'estimated_cost')::numeric,0),d) RETURNING * INTO l;
      inserted:=inserted+1;
      INSERT INTO lead_events(lead_id,kind) VALUES(l.lead_id,'IMPORTED');
    END IF;
    IF l.score_0_100>=40 AND l.status<>'DNC' THEN
      INSERT INTO notification_outbox(lead_id,dedupe_key,payload)
        VALUES(l.lead_id,'lead:'||l.lead_id::text,to_jsonb(l)) ON CONFLICT(dedupe_key)
        DO UPDATE SET payload=EXCLUDED.payload WHERE notification_outbox.state='PENDING';
    END IF;
    rows:=rows||jsonb_build_array(to_jsonb(l));
  END LOOP;
  RETURN jsonb_build_object('inserted',inserted,'leads',rows);
END $$;

CREATE OR REPLACE FUNCTION complete_import(request uuid,batch jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_result jsonb;
BEGIN
  PERFORM 1 FROM import_requests WHERE request_id=request AND state='RUNNING' FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'Import not RUNNING'; END IF;
  v_result:=ingest_batch(batch)||jsonb_build_object('request_id',request);
  UPDATE import_requests SET state='STORED',result=v_result,updated_at=now() WHERE request_id=request;
  RETURN v_result;
END $$;
