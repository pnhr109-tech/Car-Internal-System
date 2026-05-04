"""
scraper/main.py — ナビクル スクレイパー メインループ

supervisord から起動されることを想定。
シグナル受信で graceful shutdown する。

ポーリング戦略:
  営業時間内（ACTIVE_HOURS_START〜ACTIVE_HOURS_END JST）
    → POLL_INTERVAL_ACTIVE_SEC ごとにpage1のみ取得して変更検知。
      最新エントリIDが変化した時だけ fetch_entries_until_id() でフルフェッチ（ページネーション対応）。
  営業時間外
    → POLL_INTERVAL_IDLE_SEC ごとに fetch_entries_until_id() でフルフェッチ。
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
JST = timezone(timedelta(hours=9))


def _handle_signal(signum, frame):
    global _shutdown
    logger.info(f'[main] シグナル {signum} 受信 — シャットダウン準備中')
    _shutdown = True


signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)


def is_active_hours() -> bool:
    """現在時刻が営業時間内（ACTIVE_HOURS_START〜ACTIVE_HOURS_END JST）かどうか"""
    now = datetime.now(JST)
    sh, sm = map(int, config.ACTIVE_HOURS_START.split(':'))
    eh, em = map(int, config.ACTIVE_HOURS_END.split(':'))
    start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
    end   = now.replace(hour=eh, minute=em, second=0, microsecond=0)
    return start <= now < end


def _ingest_entries(entries: list[dict]) -> int:
    """エントリをインジェストし、新規件数を返す。"""
    new_count = 0
    for entry in entries:
        result = api_client.ingest(entry)
        if result.get('created'):
            new_count += 1
    return new_count


def run():
    logger.info('[main] スクレイパー起動')
    scraper = NavikuruScraper()
    consecutive_errors = 0
    last_login_at: datetime | None = None
    last_known_id: str | None = None  # 変更検知 & ID打ち切りの基準

    while not _shutdown:
        now = datetime.now(timezone.utc)
        active = is_active_hours()
        poll_interval = config.POLL_INTERVAL_ACTIVE_SEC if active else config.POLL_INTERVAL_IDLE_SEC

        # セッション維持・再ログイン
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
                _sleep(poll_interval)
                continue

        try:
            if active:
                # ── 営業時間内: 変更検知 → 新着時のみフルフェッチ ──────────────
                page1 = scraper.fetch_new_entries(max_pages=1)
                if not page1 or page1[0]['external_service_id'] == last_known_id:
                    logger.debug('[main] 変更なし — スキップ')
                    consecutive_errors = 0
                    _sleep(poll_interval)
                    continue

                # 新着あり: ID打ち切りでフルフェッチ（ページネーション対応）
                new_entries = (
                    scraper.fetch_entries_until_id(last_known_id)
                    if last_known_id is not None
                    else page1  # 初回起動時はpage1のみ使用
                )
            else:
                # ── 営業時間外: ID打ち切りでフルフェッチ（ページネーション対応）──
                new_entries = (
                    scraper.fetch_entries_until_id(last_known_id)
                    if last_known_id is not None
                    else scraper.fetch_new_entries(max_pages=1)  # 初回起動時
                )

            new_count = _ingest_entries(new_entries)
            if new_entries:
                last_known_id = new_entries[0]['external_service_id']
            if new_count:
                logger.info(f'[main] 新規登録: {new_count} 件')
            consecutive_errors = 0

        except Exception as e:
            consecutive_errors += 1
            logger.error(f'[main] 取得/インジェスト失敗 ({consecutive_errors}/{config.MAX_CONSECUTIVE_ERRORS}): {e}')
            if consecutive_errors >= config.MAX_CONSECUTIVE_ERRORS:
                logger.critical('[main] 連続エラー上限に達しました。プロセスを終了します。')
                sys.exit(1)

        _sleep(poll_interval)

    logger.info('[main] シャットダウン完了')


def _sleep(seconds: int):
    """シグナルで中断できるよう 1 秒刻みでスリープ。"""
    for _ in range(seconds):
        if _shutdown:
            break
        time.sleep(1)


if __name__ == '__main__':
    run()
