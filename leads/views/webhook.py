"""
views/webhook.py — 外部サービス Webhook ビュー

- gmail_push_notification : Gmail Push通知受信エンドポイント（Google Cloud Pub/Sub）
"""
import base64
import json
import logging

from django.core.cache import cache
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def gmail_push_notification(request):
    """
    Gmail Push通知を受信するWebhookエンドポイント

    Google Cloud Pub/Subからのメッセージを受信し、新着メールを取得する
    """
    lock_key = 'gmail_push:fetch_lock'
    lock_acquired = False
    dedupe_key = None

    try:
        logger.info(f'Received request body: {request.body}')

        envelope = json.loads(request.body.decode('utf-8'))
        logger.info(f'Parsed envelope: {envelope}')

        if 'message' not in envelope:
            logger.warning('No message field in request')
            return HttpResponse(status=400)

        message = envelope['message']

        if 'data' in message:
            data = base64.b64decode(message['data']).decode('utf-8')
            notification_data = json.loads(data)

            logger.info(f'Received push notification: {notification_data}')

            email_address = notification_data.get('emailAddress')
            history_id    = notification_data.get('historyId')

            logger.info(f'Email: {email_address}, HistoryID: {history_id}')

            if email_address and history_id:
                dedupe_key = f'gmail_push:history:{email_address}:{history_id}'
                is_new_notification = cache.add(dedupe_key, '1', timeout=600)  # 10分
                if not is_new_notification:
                    logger.info(f'Duplicate push notification skipped: {dedupe_key}')
                    return HttpResponse(status=200)

        lock_acquired = cache.add(lock_key, '1', timeout=300)  # 5分
        if not lock_acquired:
            logger.info('fetch_gmail is already running. Skip this push trigger.')
            return HttpResponse(status=200)

        from django.core.management import call_command
        try:
            call_command('fetch_gmail', '--days', '1', '--max', '10')
            logger.info('Email fetch triggered successfully')
        except Exception as e:
            if dedupe_key:
                cache.delete(dedupe_key)
            logger.error(f'Failed to fetch emails: {str(e)}')

        return HttpResponse(status=200)

    except json.JSONDecodeError as e:
        logger.error(f'JSON decode error: {str(e)}')
        return HttpResponse(status=400)
    except Exception as e:
        logger.error(f'Unexpected error in push notification: {str(e)}')
        return HttpResponse(status=500)
    finally:
        if lock_acquired:
            cache.delete(lock_key)
