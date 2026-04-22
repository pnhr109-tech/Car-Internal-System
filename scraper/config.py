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
POLL_INTERVAL_SEC      = int(os.getenv('POLL_INTERVAL_SEC', '60'))
SESSION_REFRESH_MIN    = int(os.getenv('SESSION_REFRESH_MIN', '30'))
MAX_CONSECUTIVE_ERRORS = int(os.getenv('MAX_CONSECUTIVE_ERRORS', '5'))
