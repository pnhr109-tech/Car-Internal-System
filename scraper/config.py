"""
scraper/config.py — スクレイパー設定

環境変数（.env または OS env）から読み込む。
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── ナビクル ログイン情報 ─────────────────────────────────────────
NAVIKURU_LOGIN_URL = os.getenv('NAVIKURU_LOGIN_URL', 'https://www.navikul.com/login')
NAVIKURU_LIST_URL  = os.getenv('NAVIKURU_LIST_URL',  'https://www.navikul.com/assessments')
NAVIKURU_USERNAME  = os.getenv('NAVIKURU_USERNAME', '')
NAVIKURU_PASSWORD  = os.getenv('NAVIKURU_PASSWORD', '')

# ── 社内システム Django API ──────────────────────────────────────
DJANGO_BASE_URL      = os.getenv('DJANGO_BASE_URL', 'http://localhost:8000')
SCRAPER_API_TOKEN    = os.getenv('SCRAPER_API_TOKEN', '')
NAVIKURU_INGEST_PATH = '/sateiinfo/internal/scraper/navikuru/'

# ── ポーリング設定 ────────────────────────────────────────────────
POLL_INTERVAL_SEC   = int(os.getenv('POLL_INTERVAL_SEC', '60'))   # 新着チェック間隔
SESSION_REFRESH_MIN = int(os.getenv('SESSION_REFRESH_MIN', '30')) # セッション再ログイン間隔（分）
MAX_CONSECUTIVE_ERRORS = int(os.getenv('MAX_CONSECUTIVE_ERRORS', '5'))  # 連続エラー上限
