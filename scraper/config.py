"""
scraper/config.py — スクレイパー設定

環境変数（.env または OS env）から読み込む。
設定変更は .env ファイルを編集すること。
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── ナビクル（おとくる）接続情報 ────────────────────────────────────
# 変更する場合は .env の NAVIKURU_BASE_URL / NAVIKURU_LIST_PATH を編集する
NAVIKURU_BASE_URL  = os.getenv('NAVIKURU_BASE_URL', 'https://coop-admin.otokuru.com')
NAVIKURU_LIST_PATH = os.getenv('NAVIKURU_LIST_PATH', '/member/satei')
NAVIKURU_USERNAME  = os.getenv('NAVIKURU_USERNAME', '')
NAVIKURU_PASSWORD  = os.getenv('NAVIKURU_PASSWORD', '')

# ── 導出 URL ─────────────────────────────────────────────────────────
NAVIKURU_LIST_URL = NAVIKURU_BASE_URL + NAVIKURU_LIST_PATH

# ── 社内システム Django API ──────────────────────────────────────────
DJANGO_BASE_URL      = os.getenv('DJANGO_BASE_URL', 'http://localhost:8000')
SCRAPER_API_TOKEN    = os.getenv('SCRAPER_API_TOKEN', '')
NAVIKURU_INGEST_PATH = '/sateiinfo/internal/scraper/navikuru/'

# ── ポーリング設定 ────────────────────────────────────────────────────
# 営業時間内（ACTIVE_HOURS_START〜ACTIVE_HOURS_END JST）は短い間隔で変更検知、
# 営業時間外はフルフェッチのみ実施する。
POLL_INTERVAL_ACTIVE_SEC = int(os.getenv('POLL_INTERVAL_ACTIVE_SEC', '30'))    # 営業時間内
POLL_INTERVAL_IDLE_SEC   = int(os.getenv('POLL_INTERVAL_IDLE_SEC',   '3600'))  # 営業時間外
ACTIVE_HOURS_START       = os.getenv('ACTIVE_HOURS_START', '08:30')            # JST HH:MM
ACTIVE_HOURS_END         = os.getenv('ACTIVE_HOURS_END',   '21:00')            # JST HH:MM
SESSION_REFRESH_MIN      = int(os.getenv('SESSION_REFRESH_MIN', '30'))
MAX_CONSECUTIVE_ERRORS   = int(os.getenv('MAX_CONSECUTIVE_ERRORS', '5'))

# ── 日次リカバリー設定 ────────────────────────────────────────────────
# reconcile.py が遡る時間数（デフォルト25時間: 1日 + 1時間の余裕）
RECONCILE_LOOKBACK_HOURS = int(os.getenv('RECONCILE_LOOKBACK_HOURS', '25'))
