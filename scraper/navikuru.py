"""
scraper/navikuru.py — ナビクル（おとくる）スクレイパー

https://coop-admin.otokuru.com にログインし、
査定顧客一覧（/member/satei）から申込エントリを取得する。

ログイン仕様:
  - フォームフィールド: signin[username] / signin[password]
  - CSRF: <meta name="csrf-token"> または <input name="_token">
  - ログイン後は /member/satei にリダイレクト

一覧ページ構造:
  - テーブル: table.custom-table tbody tr.d-flex
  - 各行の td 順: [申込情報, 個人情報, 車種情報, ステータス, メモ, 更新]
  - ページネーション: ?page=N
"""
import logging
import re
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString

from . import config

logger = logging.getLogger(__name__)


class NavikuruScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (compatible; GigiScraper/1.0)',
            'Accept-Language': 'ja,en;q=0.9',
        })
        self._logged_in = False

    # ──────────────────────────────────────────────
    # 認証
    # ──────────────────────────────────────────────

    def login(self) -> None:
        """
        /member/satei にアクセスし、ログインフォームが表示されていれば
        認証情報を送信する。既にログイン済みであればスキップ。
        """
        logger.info('[navikuru] ログイン開始')

        resp = self.session.get(config.NAVIKURU_LIST_URL, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'lxml')

        if not self._needs_login(soup):
            logger.info('[navikuru] 既にログイン済み')
            self._logged_in = True
            return

        # フォームを探す
        form = None
        for f in soup.find_all('form'):
            if f.find('input', {'name': 'signin[username]'}):
                form = f
                break

        if form is None:
            raise RuntimeError('ナビクル: ログインフォームが見つかりません（HTML 構造変更の可能性）')

        action = form.get('action') or config.NAVIKURU_LIST_URL
        action_url = urljoin(config.NAVIKURU_BASE_URL, action)

        payload = {
            'signin[username]': config.NAVIKURU_USERNAME,
            'signin[password]': config.NAVIKURU_PASSWORD,
        }

        csrf = self._extract_csrf(soup)
        if csrf:
            payload['_token'] = csrf

        resp = self.session.post(action_url, data=payload, timeout=15, allow_redirects=True)
        resp.raise_for_status()

        soup_after = BeautifulSoup(resp.text, 'lxml')
        if self._needs_login(soup_after):
            raise RuntimeError('ナビクル: ログイン失敗（ID/パスワードが正しいか確認してください）')

        self._logged_in = True
        logger.info('[navikuru] ログイン成功')

    def ensure_logged_in(self) -> None:
        if not self._logged_in:
            self.login()

    # ──────────────────────────────────────────────
    # 一覧取得
    # ──────────────────────────────────────────────

    def fetch_new_entries(self, max_pages: int = 1) -> list[dict]:
        """
        査定顧客一覧ページから申込エントリを取得する。

        Args:
            max_pages: 取得するページ数（デフォルト1=最新ページのみ）
                       日次照合など全件取得したい場合は大きい値を指定

        Returns:
            list of entry dicts compatible with api_client.ingest()
        """
        self.ensure_logged_in()
        logger.info(f'[navikuru] 一覧取得開始 (max_pages={max_pages})')

        all_entries = []
        for page in range(1, max_pages + 1):
            url = config.NAVIKURU_LIST_URL if page == 1 else f'{config.NAVIKURU_LIST_URL}?page={page}'
            resp = self.session.get(url, timeout=15)

            if self._needs_login(BeautifulSoup(resp.text, 'lxml')):
                logger.warning('[navikuru] セッション切れ — 再ログイン')
                self._logged_in = False
                self.login()
                resp = self.session.get(url, timeout=15)

            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, 'lxml')
            entries = self._parse_entries(soup)
            all_entries.extend(entries)

            # 次ページが存在しない場合は終了
            if not self._has_next_page(soup, page):
                break

        logger.info(f'[navikuru] {len(all_entries)} 件取得')
        return all_entries

    # ──────────────────────────────────────────────
    # HTML パース
    # ──────────────────────────────────────────────

    def _parse_entries(self, soup: BeautifulSoup) -> list[dict]:
        """
        査定顧客一覧ページを解析してエントリリストを返す。

        各行の td 構成:
          tds[0] col-2: 申込情報 (ID・日時・バッジ)
          tds[1] col-4: 個人情報 (氏名・電話・メール・住所)
          tds[2] col-3: 車種情報 (メーカー・車種・年式・走行距離)
          tds[3] col-3: ステータス (社内管理用 - スクレイプ不要)
          tds[4] col-3: メモ
          tds[5] col-1: 更新ボタン
        """
        entries = []
        rows = soup.select('table.custom-table tbody tr.d-flex')

        for row in rows:
            try:
                entry = self._parse_row(row)
                if entry:
                    entries.append(entry)
            except Exception as e:
                logger.warning(f'[navikuru] 行パース失敗: {e}')

        return entries

    def _parse_row(self, row) -> dict | None:
        tds = row.find_all('td')
        if len(tds) < 3:
            return None

        # ── td[0]: 申込情報 ──────────────────────
        td_app = tds[0]

        # 申込番号 (external_service_id)
        id_link = td_app.find('a', {'data-js-selecter': 'm_member_satei_id'})
        if not id_link:
            return None
        external_id = id_link.get_text(strip=True)

        # 申込日時
        date_span = td_app.find('span', attrs={'data-js-selecter': lambda v: v and v.endswith('_created_at')})
        datetime_str = self._parse_datetime(date_span.get_text(strip=True)) if date_span else ''

        # 外部ステータス（バッジ: 直近層 / 検討層）
        spans = td_app.find_all('span', class_='d-block')
        external_status = ''
        if len(spans) >= 3:
            external_status = self._clean(spans[2].get_text())

        # ── td[1]: 個人情報 ──────────────────────
        td_personal = tds[1]
        info_spans = td_personal.find_all('span', class_='d-block', recursive=False)

        customer_name = ''
        phone_number = ''
        email = ''
        postal_code = ''
        address = ''

        if len(info_spans) >= 1:
            customer_name = self._clean(info_spans[0].get_text())
            # " 様" を除去
            customer_name = re.sub(r'\s*様\s*$', '', customer_name).strip()

        if len(info_spans) >= 2:
            phone_link = info_spans[1].find('a', href=lambda h: h and h.startswith('tel:'))
            phone_number = phone_link.get_text(strip=True) if phone_link else self._clean(info_spans[1].get_text())

        if len(info_spans) >= 3:
            email = self._clean(info_spans[2].get_text())

        if len(info_spans) >= 4:
            addr_text = self._clean(info_spans[3].get_text())
            # "〒3020032 茨城県笠間市" → postal_code="3020032", address="茨城県笠間市"
            match = re.match(r'〒?(\d+)\s*(.*)', addr_text)
            if match:
                postal_code = match.group(1)
                address = match.group(2).strip()
            else:
                address = addr_text

        # ── td[2]: 車種情報 ──────────────────────
        td_vehicle = tds[2]

        maker = ''
        car_model = ''
        year = ''
        mileage = ''

        inner_div = td_vehicle.find('div', class_='d-block')
        if inner_div:
            div_spans = inner_div.find_all('span')
            if div_spans:
                maker = self._clean(div_spans[0].get_text())
            car_name_span = inner_div.find('span', class_='car-name')
            if car_name_span:
                car_model = car_name_span.get_text(strip=True)

        # 年式（直接テキストのみ取得し、元号表記は除く）
        year_mileage_spans = td_vehicle.find_all('span', class_='d-block py-1', recursive=False)
        if len(year_mileage_spans) >= 1:
            year_span = year_mileage_spans[0]
            # "2013年" のみ抽出（"平成25年" の wareki スパンは無視）
            year_texts = []
            for child in year_span.children:
                if isinstance(child, NavigableString):
                    t = self._clean(str(child))
                    if t:
                        year_texts.append(t)
            raw_year = ' '.join(year_texts).strip()
            # "2013年" → "2013"
            year = re.sub(r'[年\s]', '', raw_year).strip()

        if len(year_mileage_spans) >= 2:
            mileage = self._clean(year_mileage_spans[1].get_text())

        return {
            'external_service_id': external_id,
            'application_datetime': datetime_str,
            'customer_name':        customer_name,
            'phone_number':         phone_number,
            'email':                email,
            'postal_code':          postal_code,
            'address':              address,
            'maker':                maker,
            'car_model':            car_model,
            'year':                 year,
            'mileage':              mileage,
            'desired_sale_timing':  '',
            'external_status':      external_status,
        }

    # ──────────────────────────────────────────────
    # ヘルパー
    # ──────────────────────────────────────────────

    @staticmethod
    def _needs_login(soup: BeautifulSoup) -> bool:
        """ログインフォームが存在するかどうかを判定する。"""
        return bool(soup.find('input', {'name': 'signin[username]'}))

    @staticmethod
    def _extract_csrf(soup: BeautifulSoup) -> str | None:
        # Rails / Laravel 形式の meta タグ
        meta = soup.find('meta', {'name': 'csrf-token'})
        if meta:
            return meta.get('content')
        # input hidden タグ
        tag = soup.find('input', {'name': '_token'})
        if tag:
            return tag.get('value')
        return None

    @staticmethod
    def _has_next_page(soup: BeautifulSoup, current_page: int) -> bool:
        """次のページが存在するか確認する。"""
        next_href = f'?page={current_page + 1}'
        return bool(soup.find('a', href=lambda h: h and next_href in h))

    @staticmethod
    def _clean(text: str) -> str:
        """テキストからアイコン残留スペースや改行を除去する。"""
        # \xa0 (non-breaking space) と余分な空白を除去
        return re.sub(r'[\s\xa0]+', ' ', text).strip()

    @staticmethod
    def _parse_datetime(text: str) -> str:
        """
        "2026/04/22 (水) 13:01" → "2026-04-22T13:01:00"
        変換に失敗した場合は元テキストをそのまま返す。
        """
        # 曜日を除去
        cleaned = re.sub(r'\([^)]+\)', '', text).strip()
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()
        try:
            dt = datetime.strptime(cleaned, '%Y/%m/%d %H:%M')
            return dt.isoformat()
        except ValueError:
            return text
