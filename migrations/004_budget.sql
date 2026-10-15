CREATE TABLE llm_settings (
  id boolean PRIMARY KEY DEFAULT true CHECK(id),enabled boolean NOT NULL DEFAULT false,
  has_credentials boolean NOT NULL DEFAULT false,model text NOT NULL DEFAULT 'gpt-4.1-mini',
  input_price numeric(12,6) NOT NULL DEFAULT 0 CHECK(input_price>=0),
  output_price numeric(12,6) NOT NULL DEFAULT 0 CHECK(output_price>=0),
  mock_mode boolean NOT NULL DEFAULT false
);
INSERT INTO llm_settings(id) VALUES(true);
CREATE TABLE llm_inflight(cache_key text PRIMARY KEY,created_at timestamptz NOT NULL DEFAULT now());

CREATE FUNCTION reserve_score(input jsonb,key text,input_tokens integer,body jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings; cfg llm_settings; cost numeric(12,6); cached jsonb; d date;
BEGIN
  SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
  SELECT * INTO cfg FROM llm_settings WHERE id=true;
  IF s.stopped OR NOT cfg.enabled OR (input->'lead'->>'score_0_100')::integer<40 OR
    (NOT cfg.mock_mode AND (NOT cfg.has_credentials OR cfg.input_price<=0 OR cfg.output_price<=0)) OR
    (cfg.mock_mode AND NOT coalesce((input->'lead'->>'is_demo')::boolean,false)) OR input_tokens<1 OR input_tokens>100000 THEN
    RETURN input||jsonb_build_object('mode','FALLBACK','reason','disabled, prefilter or missing limits');
  END IF;
  SELECT result INTO cached FROM llm_cache WHERE cache_key=key;
  IF FOUND THEN RETURN input||jsonb_build_object('mode','CACHE','cached',cached); END IF;
  DELETE FROM llm_inflight WHERE cache_key=key AND created_at<now()-interval '10 minutes';
  INSERT INTO llm_inflight(cache_key) VALUES(key) ON CONFLICT DO NOTHING;
  IF NOT FOUND THEN RETURN input||jsonb_build_object('mode','FALLBACK','reason','in-flight'); END IF;
  cost:=ceil(((input_tokens*cfg.input_price+600*cfg.output_price)/1000000)*1000000)/1000000;
  IF cfg.mock_mode THEN cost:=0; END IF;
  d:=(now() AT TIME ZONE 'UTC')::date;
  IF s.max_llm_calls_per_day<1 OR cost>s.daily_api_budget_usd THEN
    DELETE FROM llm_inflight WHERE cache_key=key;
    RETURN input||jsonb_build_object('mode','FALLBACK','reason','budget');
  END IF;
  INSERT INTO daily_usage(day,calls,reserved_usd) VALUES(d,1,cost)
    ON CONFLICT(day) DO UPDATE SET calls=daily_usage.calls+1,reserved_usd=daily_usage.reserved_usd+cost
    WHERE daily_usage.calls<s.max_llm_calls_per_day AND daily_usage.reserved_usd+cost<=s.daily_api_budget_usd;
  IF NOT FOUND THEN
    DELETE FROM llm_inflight WHERE cache_key=key;
    RETURN input||jsonb_build_object('mode','FALLBACK','reason','budget');
  END IF;
  RETURN input||jsonb_build_object('mode','CALL','cache_key',key,'mock',cfg.mock_mode,'reserved_usd',cost,
    'request_body',body||jsonb_build_object('model',cfg.model),
    'endpoint',CASE WHEN cfg.mock_mode THEN 'http://127.0.0.1:9099/responses' ELSE 'https://api.openai.com/v1/responses' END);
END $$;

CREATE OR REPLACE FUNCTION finish_score(decision jsonb,assessment jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE v_lead jsonb; v_result jsonb;
BEGIN
  v_lead:=decision->'lead';
  IF assessment IS NOT NULL AND assessment<>'null'::jsonb THEN
    v_result:=assessment||jsonb_build_object('scoring_method',CASE WHEN (decision->>'mock')::boolean THEN 'openai_mock' ELSE 'openai' END,
      'status',CASE WHEN (assessment->>'score_0_100')::integer<40 THEN 'REVIEW' ELSE 'NEW' END);
    INSERT INTO llm_cache(cache_key,result) VALUES(decision->>'cache_key',v_result)
      ON CONFLICT(cache_key) DO NOTHING;
    v_lead:=v_lead||v_result||jsonb_build_object('estimated_cost',(decision->>'reserved_usd')::numeric);
  ELSE
    v_lead:=v_lead||jsonb_build_object('scoring_error','API_FAILURE_OR_INVALID_RESPONSE');
  END IF;
  DELETE FROM llm_inflight WHERE cache_key=decision->>'cache_key';
  RETURN jsonb_build_object('request_id',decision->>'request_id','lead',v_lead);
END $$;
