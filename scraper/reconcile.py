"""
scraper/reconcile.py — 日次差分照合スクリプト

Cloud Scheduler から 1 日 1 回呼び出す。
ナビクル一覧を全件取得し、Django API を通じてステータスを同期する。
ポーリングループが取りこぼしたエントリを補完する目的で使用。

実行方法:
    python -m scraper.reconcile
"""
import logging
import sys

from . import api_client
from .navikuru import NavikuruScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def run():
    logger.info('[reconcile] 日次照合開始')
    scraper = NavikuruScraper()

    try:
        scraper.login()
    except Exception as e:
        logger.error(f'[reconcile] ログイン失敗: {e}')
        sys.exit(1)

    try:
        entries = scraper.fetch_new_entries()
    except Exception as e:
        logger.error(f'[reconcile] 一覧取得失敗: {e}')
        sys.exit(1)

    created = updated = errors = 0
    for entry in entries:
        try:
            result = api_client.ingest(entry)
            if result.get('created'):
                created += 1
            else:
                updated += 1
        except Exception as e:
            errors += 1
            logger.error(f'[reconcile] インジェスト失敗 (external_id={entry.get("external_service_id")}): {e}')

    logger.info(f'[reconcile] 完了 — 新規: {created}, 更新: {updated}, エラー: {errors}')
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    run()
