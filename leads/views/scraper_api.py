"""
leads/views/scraper_api.py — スクレイパー向け内部 API

認証: Authorization: Bearer <SCRAPER_API_TOKEN>
外部からは呼ばれない。スクレイパープロセスのみが使用する。
"""
import logging
import os
from datetime import datetime

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from ..models import CarAssessmentRequest
from .utils import _generate_application_number

logger = logging.getLogger(__name__)


def _check_token(request) -> bool:
    token = os.getenv('SCRAPER_API_TOKEN', '')
    if not token:
        return False
    auth = request.headers.get('Authorization', '')
    return auth == f'Bearer {token}'


@csrf_exempt
@require_POST
def scraper_ingest_navikuru(request):
    """
    ナビクルスクレイパーからのデータ受信エンドポイント。

    Request body (JSON):
        external_service_id  : str  — ナビクル側の申込ID（必須）
        application_datetime : str  — ISO 8601形式 例: "2026-04-22T10:30:00+09:00"
        customer_name        : str
        phone_number         : str
        email                : str  (任意)
        postal_code          : str  (任意)
        address              : str  (任意)
        maker                : str  (任意)
        car_model            : str  (任意)
        year                 : str  (任意)
        mileage              : str  (任意)
        desired_sale_timing  : str  (任意)
        external_status      : str  — ナビクル側ステータス (任意)

    Response:
        {"created": bool, "id": int, "application_number": str}
    """
    if not _check_token(request):
        return JsonResponse({'error': 'Unauthorized'}, status=401)

    import json
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    external_service_id = payload.get('external_service_id', '').strip()
    if not external_service_id:
        return JsonResponse({'error': 'external_service_id is required'}, status=400)

    customer_name = payload.get('customer_name', '').strip()
    phone_number  = payload.get('phone_number', '').strip()
    if not customer_name or not phone_number:
        return JsonResponse({'error': 'customer_name and phone_number are required'}, status=400)

    # 申込日時のパース
    try:
        app_dt_raw = payload.get('application_datetime', '')
        app_dt = datetime.fromisoformat(app_dt_raw)
        if app_dt.tzinfo is None:
            app_dt = timezone.make_aware(app_dt)
    except (ValueError, TypeError):
        app_dt = timezone.now()

    # 重複チェック: channel_type + external_service_id で既存を検索
    existing = CarAssessmentRequest.objects.filter(
        channel_type=CarAssessmentRequest.CHANNEL_NAVIKURU,
        external_service_id=external_service_id,
    ).first()

    if existing:
        # 既存レコードの外部ステータスとスクレイピング日時だけ更新
        update_fields = ['scraped_at', 'updated_at']
        existing.scraped_at = timezone.now()
        if payload.get('external_status'):
            existing.external_status = payload['external_status']
            update_fields.append('external_status')
        existing.save(update_fields=update_fields)
        return JsonResponse({
            'created': False,
            'id': existing.pk,
            'application_number': existing.application_number,
        })

    # 新規登録
    today = app_dt.date()
    application_number = _generate_application_number(
        CarAssessmentRequest.CHANNEL_NAVIKURU, today
    )

    obj = CarAssessmentRequest.objects.create(
        application_number   = application_number,
        application_datetime = app_dt,
        channel_type         = CarAssessmentRequest.CHANNEL_NAVIKURU,
        external_service_id  = external_service_id,
        external_status      = payload.get('external_status', ''),
        customer_name        = customer_name,
        phone_number         = phone_number,
        email                = payload.get('email', ''),
        postal_code          = payload.get('postal_code', ''),
        address              = payload.get('address', ''),
        maker                = payload.get('maker', ''),
        car_model            = payload.get('car_model', ''),
        year                 = payload.get('year', ''),
        mileage              = payload.get('mileage', ''),
        desired_sale_timing  = payload.get('desired_sale_timing', ''),
        scraped_at           = timezone.now(),
    )
    logger.info(f'[scraper] 新規登録: {application_number} ({external_service_id})')

    return JsonResponse({
        'created': True,
        'id': obj.pk,
        'application_number': application_number,
    }, status=201)
