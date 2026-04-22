"""
scraper/api_client.py — Django 内部 API クライアント
"""
import logging
import requests
from . import config

logger = logging.getLogger(__name__)

INGEST_URL = f'{config.DJANGO_BASE_URL}{config.NAVIKURU_INGEST_PATH}'
HEADERS = {
    'Authorization': f'Bearer {config.SCRAPER_API_TOKEN}',
    'Content-Type': 'application/json',
}


def ingest(entry: dict) -> dict:
    """
    エントリを Django 内部 API に送信する。

    Args:
        entry: {
            'external_service_id': str,
            'application_datetime': str (ISO 8601),
            'customer_name': str,
            'phone_number': str,
            'email': str,
            'postal_code': str,
            'address': str,
            'maker': str,
            'car_model': str,
            'year': str,
            'mileage': str,
            'desired_sale_timing': str,
            'external_status': str,
        }

    Returns:
        {'created': bool, 'id': int, 'application_number': str}

    Raises:
        requests.HTTPError: API がエラーを返した場合
        requests.ConnectionError: 接続できない場合
    """
    response = requests.post(INGEST_URL, json=entry, headers=HEADERS, timeout=10)
    response.raise_for_status()
    result = response.json()
    if result.get('created'):
        logger.info(f"[api_client] 新規登録: {result.get('application_number')} (外部ID: {entry.get('external_service_id')})")
    return result
