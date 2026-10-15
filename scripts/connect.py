#!/usr/bin/env python3
"""Apply explicit owner/budget settings without printing secrets or calling external APIs."""
from common import config, sql, literal


def main():
    cfg=config();admin=cfg.get('TELEGRAM_ADMIN_ID','')
    if admin and (not admin.isdigit() or int(admin)<=0):
        raise SystemExit('TELEGRAM_ADMIN_ID must be a positive numeric private user ID')
    for name in ('MAX_LLM_CALLS_PER_DAY','MAX_LEADS_PER_RUN'):
        if not cfg[name].isdigit():raise SystemExit(name+' must be a non-negative integer')
    from decimal import Decimal,InvalidOperation
    try: budget=Decimal(cfg['DAILY_API_BUDGET_USD'])
    except InvalidOperation:raise SystemExit('Invalid budget') from None
    if not budget.is_finite() or budget<0:raise SystemExit('Budget must be finite and non-negative')
    sql(f"UPDATE app_settings SET admin_id={int(admin) if admin else 'NULL'},daily_api_budget_usd={budget},max_llm_calls_per_day={int(cfg['MAX_LLM_CALLS_PER_DAY'])},max_leads_per_run={int(cfg['MAX_LEADS_PER_RUN'])},updated_at=now() WHERE id=true;")
    enabled=cfg.get('AI_ENABLED','false').lower()=='true'
    provider=bool(cfg.get('AI_PROVIDER_MODEL'))
    key=bool(cfg.get('AI_ACCESS_KEY')) if provider else bool(cfg.get('LH_OPENAI_API_KEY') or cfg.get('OPENAI_API_KEY'))
    style=cfg.get('AI_PROVIDER_STYLE','chat_completions') if provider else 'responses'
    if style not in ('responses','chat_completions'):raise SystemExit('Invalid AI API style')
    base=cfg.get('AI_PROVIDER_BASE_URL','') if provider else 'https://api.openai.com/v1'
    if base not in ('https://api.openai.com/v1','https://shprotoness-ai.jq9gfk.workers.dev/v1'):raise SystemExit('Unconfirmed provider base URL')
    endpoint=base+('/responses' if style=='responses' else '/chat/completions')
    free=cfg.get('AI_FREE_QUOTA_CONFIRMED','false').lower()=='true'
    try:
        price_in=Decimal(cfg.get('OPENAI_INPUT_USD_PER_MILLION','0'))
        price_out=Decimal(cfg.get('OPENAI_OUTPUT_USD_PER_MILLION','0'))
    except InvalidOperation:raise SystemExit('Invalid model prices') from None
    if any(not p.is_finite() or p<0 for p in (price_in,price_out)):raise SystemExit('Prices must be finite and non-negative')
    if enabled and (not key or (not free and (price_in<=0 or price_out<=0))):raise SystemExit('AI_ENABLED requires a key and explicit positive model prices')
    sql(f"UPDATE llm_settings SET enabled={str(enabled).lower()},has_credentials={str(key).lower()},model={literal(cfg['AI_PROVIDER_MODEL'] if provider else cfg.get('OPENAI_MODEL','gpt-4.1-mini'))},input_price={price_in},output_price={price_out},mock_mode=false,api_style={literal(style)},endpoint={literal(endpoint)},free_quota_confirmed={str(free).lower()} WHERE id=true;")
    sql(f"UPDATE form_settings SET signing_key={literal(cfg['INGEST_TOKEN'])},enabled={str(cfg.get('WEBSITE_FORMS_ENABLED','false').lower()=='true').lower()} WHERE id=true;")
    sql(f"UPDATE app_settings SET max_public_posts_per_day={int(cfg.get('MAX_PUBLIC_POSTS_PER_DAY','2'))} WHERE id=true;")
    print('Owner binding:', 'SET' if admin else 'MISSING', '· Budget limits applied. No external requests sent.')


if __name__=='__main__':main()
