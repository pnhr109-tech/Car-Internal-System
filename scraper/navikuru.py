"""
scraper/navikuru.py — ナビクル スクレイパー

ナビクル（https://www.navikul.com）にログインし、
新着査定申込一覧を取得する。

NOTE: parse_entries() の HTML パース部分は実際のポータルの
      DOM 構造が確定したら実装する。現時点ではスタブを返す。
"""
import logging
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

from . import config

logger = logging.getLogger(__name__)


class NavikuruScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; GigiScraper/1.0)'})
        self._logged_in = False

    # ──────────────────────────────────────────────
    # 認証
    # ──────────────────────────────────────────────

    def login(self) -> None:
        """ナビクルにログインしてセッション Cookie を取得する。"""
        logger.info('[navikuru] ログイン開始')

        # GET でログインフォームの CSRF トークンを取得
        resp = self.session.get(config.NAVIKURU_LOGIN_URL, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'lxml')
        csrf_token = self._extract_csrf(soup)

        payload = {
            'username': config.NAVIKURU_USERNAME,
            'password': config.NAVIKURU_PASSWORD,
        }
        if csrf_token:
            payload['_token'] = csrf_token   # フォームフィールド名は実際の DOM に合わせて変更

        resp = self.session.post(config.NAVIKURU_LOGIN_URL, data=payload, timeout=15)
        resp.raise_for_status()

        # ログイン成功判定: ログインページへのリダイレクトが残っていれば失敗とみなす
        if config.NAVIKURU_LOGIN_URL in resp.url:
            raise RuntimeError('ナビクル: ログイン失敗（認証エラーまたは UI 変更）')

        self._logged_in = True
        logger.info('[navikuru] ログイン成功')

    def ensure_logged_in(self) -> None:
        if not self._logged_in:
            self.login()

    # ──────────────────────────────────────────────
    # 一覧取得
    # ──────────────────────────────────────────────

    def fetch_new_entries(self) -> list[dict]:
        """
        ナビクル査定申込一覧ページから未処理エントリを取得する。

        Returns:
            list of entry dicts compatible with api_client.ingest()
        """
        self.ensure_logged_in()
        logger.info('[navikuru] 一覧取得開始')

        resp = self.session.get(config.NAVIKURU_LIST_URL, timeout=15)
        if resp.status_code == 401 or resp.status_code == 403:
            # セッション切れ → 再ログイン
            self._logged_in = False
            self.login()
            resp = self.session.get(config.NAVIKURU_LIST_URL, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'lxml')
        entries = self._parse_entries(soup)
        logger.info(f'[navikuru] {len(entries)} 件取得')
        return entries

    # ──────────────────────────────────────────────
    # HTML パース（TODO: 実際の DOM 構造に合わせて実装）
    # ──────────────────────────────────────────────

    def _parse_entries(self, soup: BeautifulSoup) -> list[dict]:
        """
        査定申込一覧ページを解析してエントリリストを返す。

        TODO: ナビクル管理画面の実際の HTML 構造を確認し、
              セレクタ・フィールドマッピングを実装する。
              現時点では空リストを返す（ループ起動テスト用）。
        """
        entries = []

        # 実装例（セレクタは実際の DOM に合わせて変更）:
        # rows = soup.select('table.assessment-list tbody tr')
        # for row in rows:
        #     cells = row.select('td')
        #     if len(cells) < 10:
        #         continue
        #     entries.append({
        #         'external_service_id': cells[0].get_text(strip=True),
        #         'application_datetime': _parse_datetime(cells[1].get_text(strip=True)),
        #         'customer_name':        cells[2].get_text(strip=True),
        #         'phone_number':         cells[3].get_text(strip=True),
        #         'email':                cells[4].get_text(strip=True),
        #         'postal_code':          cells[5].get_text(strip=True),
        #         'address':              cells[6].get_text(strip=True),
        #         'maker':                cells[7].get_text(strip=True),
        #         'car_model':            cells[8].get_text(strip=True),
        #         'year':                 cells[9].get_text(strip=True),
        #         'mileage':              cells[10].get_text(strip=True) if len(cells) > 10 else '',
        #         'desired_sale_timing':  cells[11].get_text(strip=True) if len(cells) > 11 else '',
        #         'external_status':      cells[12].get_text(strip=True) if len(cells) > 12 else '',
        #     })

        return entries

    # ──────────────────────────────────────────────
    # ヘルパー
    # ──────────────────────────────────────────────

    @staticmethod
    def _extract_csrf(soup: BeautifulSoup) -> str | None:
        tag = soup.find('input', {'name': '_token'})
        if tag:
            return tag.get('value')
        meta = soup.find('meta', {'name': 'csrf-token'})
        if meta:
            return meta.get('content')
        return None
