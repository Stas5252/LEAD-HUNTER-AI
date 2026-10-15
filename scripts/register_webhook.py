#!/usr/bin/env python3
"""Explicit owner action: register a public HTTPS Telegram webhook."""
import argparse
from urllib.parse import urlsplit
from telegram_transport import settings,BotAPI


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',required=True)
    p.add_argument('--apply',action='store_true',required=True)
    p.add_argument('--replace-existing',action='store_true')
    args=p.parse_args();u=urlsplit(args.url)
    if u.scheme!='https' or not u.hostname or u.username or u.password or u.query or u.fragment or u.path!='/webhook/lh-telegram':
        raise SystemExit('Expected public HTTPS URL ending in /webhook/lh-telegram, without credentials/query')
    cfg=settings()
    if not cfg.get('TELEGRAM_BOT_TOKEN') or not cfg.get('TELEGRAM_WEBHOOK_SECRET'):
        raise SystemExit('NEEDS_CREDENTIALS: configure Telegram securely first')
    api=BotAPI(cfg['TELEGRAM_BOT_TOKEN'])
    try:
        prior=api.call('getWebhookInfo',{})
        old=prior.get('result',{}).get('url')
        if old and old!=args.url and not args.replace_existing:
            raise SystemExit('Different webhook exists; replacement requires --replace-existing')
        result=api.call('setWebhook',{'url':args.url,'secret_token':cfg['TELEGRAM_WEBHOOK_SECRET'],
            'allowed_updates':['message','edited_message','channel_post','edited_channel_post','callback_query'],'drop_pending_updates':False})
    except (OSError,ValueError):raise SystemExit('Webhook registration failed; secret values are not logged') from None
    if not result.get('ok'):raise SystemExit('Bot API rejected webhook registration')
    print('Webhook registered. Start delivery worker with --webhook; do not use getUpdates concurrently.')


if __name__=='__main__':main()
