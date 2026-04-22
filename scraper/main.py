"""
scraper/main.py — ナビクル スクレイパー メインループ

supervisord から起動されることを想定。
シグナル受信で graceful shutdown する。
"""
import logging
import signal
import sys
import time
from datetime import datetime, timedelta, timezone

from . import api_client, config
from .navikuru import NavikuruScraper

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s %(message)s',
    datefmt='%Y-%m-%dT%H:%M:%S',
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_shutdown = False


def _handle_signal(signum, frame):
    global _shutdown
    logger.info(f'[main] シグナル {signum} 受信 — シャットダウン準備中')
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def run():
    logger.info('[main] スクレイパー起動')
    scraper = NavikuruScraper()
    consecutive_errors = 0
    last_login_at = None

    while not _shutdown:
        now = datetime.now(timezone.utc)

        # 定期的にセッションを再ログイン
        needs_relogin = (
            last_login_at is None
            or (now - last_login_at) >= timedelta(minutes=config.SESSION_REFRESH_MIN)
        )
        if needs_relogin:
            try:
                scraper.login()
                last_login_at = now
                consecutive_errors = 0
            except Exception as e:
                consecutive_errors += 1
                logger.error(f'[main] ログイン失敗 ({consecutive_errors}/{config.MAX_CONSECUTIVE_ERRORS}): {e}')
                if consecutive_errors >= config.MAX_CONSECUTIVE_ERRORS:
                    logger.critical('[main] 連続エラー上限に達しました。プロセスを終了します。')
                    sys.exit(1)
                _sleep(config.POLL_INTERVAL_SEC)
                continue

        # 新着取得 & インジェスト
        try:
            entries = scraper.fetch_new_entries()
            new_count = 0
            for entry in entries:
                result = api_client.ingest(entry)
                if result.get('created'):
                    new_count += 1
            if new_count:
                logger.info(f'[main] 新規登録: {new_count} 件')
            consecutive_errors = 0
        except Exception as e:
            consecutive_errors += 1
            logger.error(f'[main] 取得/インジェスト失敗 ({consecutive_errors}/{config.MAX_CONSECUTIVE_ERRORS}): {e}')
            if consecutive_errors >= config.MAX_CONSECUTIVE_ERRORS:
                logger.critical('[main] 連続エラー上限に達しました。プロセスを終了します。')
                sys.exit(1)

        _sleep(config.POLL_INTERVAL_SEC)

    logger.info('[main] シャットダウン完了')


def _sleep(seconds: int):
    """シグナルで中断できるよう 1 秒刻みでスリープ。"""
    for _ in range(seconds):
        if _shutdown:
            break
        time.sleep(1)


if __name__ == '__main__':
    run()
