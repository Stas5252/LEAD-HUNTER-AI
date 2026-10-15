-- Only the explicitly supplied provider origin or official OpenAI is eligible.
ALTER TABLE llm_settings ADD COLUMN api_style text NOT NULL DEFAULT 'responses' CHECK(api_style IN ('responses','chat_completions'));
ALTER TABLE llm_settings ADD COLUMN endpoint text NOT NULL DEFAULT 'https://api.openai.com/v1/responses' CHECK(endpoint IN ('https://api.openai.com/v1/responses','https://api.openai.com/v1/chat/completions','https://shprotoness-ai.jq9gfk.workers.dev/v1/responses','https://shprotoness-ai.jq9gfk.workers.dev/v1/chat/completions'));
ALTER TABLE llm_settings ADD COLUMN free_quota_confirmed boolean NOT NULL DEFAULT false;
CREATE OR REPLACE FUNCTION reserve_score(input jsonb,key text,input_tokens integer,body jsonb) RETURNS jsonb LANGUAGE plpgsql AS $$
DECLARE s app_settings; cfg llm_settings; cost numeric(12,6); cached jsonb; d date;
BEGIN
  SELECT * INTO s FROM app_settings WHERE id=true FOR UPDATE;
  SELECT * INTO cfg FROM llm_settings WHERE id=true;
  IF s.stopped OR NOT cfg.enabled OR (input->'lead'->>'score_0_100')::integer<40 OR
    (NOT cfg.mock_mode AND (NOT cfg.has_credentials OR (NOT cfg.free_quota_confirmed AND (cfg.input_price<=0 OR cfg.output_price<=0)))) OR
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
    'endpoint',CASE WHEN cfg.mock_mode THEN 'http://127.0.0.1:9099/responses' ELSE cfg.endpoint END);
END $$;

