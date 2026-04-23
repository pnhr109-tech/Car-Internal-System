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
from datetime import datetime, timezone
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Comment, NavigableString

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
        # 401 はログインページ自体が返すケースがあるため、ここでは raise しない
        logger.info(f'[navikuru] GET status={resp.status_code} url={resp.url}')

        soup = BeautifulSoup(resp.text, 'lxml')

        if not self._needs_login(soup):
            logger.info('[navikuru] 既にログイン済み')
            self._logged_in = True
            return

        logger.info(f'[navikuru] ログインページURL: {resp.url}')

        # フォームと全 hidden フィールドを列挙して診断ログに出す
        all_forms = soup.find_all('form')
        logger.info(f'[navikuru] フォーム数: {len(all_forms)}')
        for i, f in enumerate(all_forms):
            inputs = [(inp.get('name'), inp.get('type')) for inp in f.find_all('input')]
            logger.info(f'[navikuru] form[{i}] action={f.get("action")!r} inputs={inputs}')

        # ログインフォームを探す
        form = None
        for f in soup.find_all('form'):
            if f.find('input', {'name': 'signin[username]'}):
                form = f
                break

        if form is None:
            # フォームが見つからない場合、ページ冒頭を出力して原因調査
            logger.error(f'[navikuru] ログインフォーム未検出。ページ冒頭:\n{resp.text[:1000]}')
            raise RuntimeError('ナビクル: ログインフォームが見つかりません（HTML 構造変更の可能性）')

        # resp.url はリダイレクト後の実際のURL（ホストが変わっている場合に対応）
        action = form.get('action') or resp.url
        action_url = urljoin(resp.url, action)
        logger.info(f'[navikuru] POST先: {action_url}')

        # CSRF トークンをフォームの meta / hidden input から取得
        csrf_name, csrf_value = self._extract_csrf(soup)
        logger.info(f'[navikuru] CSRF: name={csrf_name!r}, found={csrf_value is not None}')

        payload = {
            'signin[username]': config.NAVIKURU_USERNAME,
            'signin[password]': config.NAVIKURU_PASSWORD,
        }
        if csrf_name and csrf_value:
            payload[csrf_name] = csrf_value

        logger.info(f'[navikuru] 送信フィールド: {list(payload.keys())}')

        post_resp = self.session.post(
            action_url, data=payload, timeout=15, allow_redirects=True,
            headers={'Referer': resp.url},
        )
        if not post_resp.ok:
            logger.error(f'[navikuru] POST失敗 status={post_resp.status_code} body冒頭:\n{post_resp.text[:500]}')
        post_resp.raise_for_status()
        resp = post_resp

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

    def fetch_entries_since(self, since_dt: datetime) -> list[dict]:
        """
        since_dt 以降に申し込まれたエントリを全ページから取得する。
        一覧は新着順なので、ページ内の最古エントリが since_dt を下回った時点で終了する。

        Args:
            since_dt: この日時以降のエントリのみ返す（タイムゾーン付き推奨）

        Returns:
            list of entry dicts
        """
        self.ensure_logged_in()
        if since_dt.tzinfo is None:
            since_dt = since_dt.replace(tzinfo=timezone.utc)

        logger.info(f'[navikuru] 差分取得開始 (since={since_dt.isoformat()})')
        all_entries = []
        page = 1

        while True:
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

            if not entries:
                break

            # 新着順なので、このページの最古エントリで打ち切り判断
            stop_after_this_page = False
            page_entries = []
            for entry in entries:
                entry_dt = self._parse_entry_datetime(entry.get('application_datetime', ''))
                if entry_dt is None or entry_dt >= since_dt:
                    page_entries.append(entry)
                else:
                    stop_after_this_page = True

            all_entries.extend(page_entries)
            logger.info(f'[navikuru] page={page}: {len(entries)} 件取得, うち対象 {len(page_entries)} 件')

            if stop_after_this_page or not self._has_next_page(soup, page):
                break

            page += 1

        logger.info(f'[navikuru] 差分取得完了: 合計 {len(all_entries)} 件')
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
            external_status = self._clean(self._text(spans[2]))

        # ── td[1]: 個人情報 ──────────────────────
        td_personal = tds[1]
        info_spans = td_personal.find_all('span', class_='d-block', recursive=False)

        customer_name = ''
        phone_number = ''
        email = ''
        postal_code = ''
        address = ''

        if len(info_spans) >= 1:
            customer_name = self._clean(self._text(info_spans[0]))
            # " 様" を除去
            customer_name = re.sub(r'\s*様\s*$', '', customer_name).strip()

        if len(info_spans) >= 2:
            phone_link = info_spans[1].find('a', href=lambda h: h and h.startswith('tel:'))
            phone_number = phone_link.get_text(strip=True) if phone_link else self._clean(self._text(info_spans[1]))

        if len(info_spans) >= 3:
            email = self._clean(self._text(info_spans[2]))

        if len(info_spans) >= 4:
            addr_text = self._clean(self._text(info_spans[3]))
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
                maker = self._clean(self._text(div_spans[0]))
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
                if isinstance(child, NavigableString) and not isinstance(child, Comment):
                    t = self._clean(str(child))
                    if t:
                        year_texts.append(t)
            raw_year = ' '.join(year_texts).strip()
            # "2013年" → "2013"
            year = re.sub(r'[年\s]', '', raw_year).strip()

        if len(year_mileage_spans) >= 2:
            mileage = self._clean(self._text(year_mileage_spans[1]))

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
    def _text(tag) -> str:
        """FontAwesome Comment ノードを除いてテキストを結合する。"""
        return ''.join(
            str(s) for s in tag.strings
            if not isinstance(s, Comment)
        )

    @staticmethod
    def _needs_login(soup: BeautifulSoup) -> bool:
        """ログインフォームが存在するかどうかを判定する。"""
        return bool(soup.find('input', {'name': 'signin[username]'}))

    @staticmethod
    def _extract_csrf(soup: BeautifulSoup) -> tuple[str | None, str | None]:
        """(フィールド名, トークン値) を返す。見つからない場合は (None, None)。"""
        # Rails 形式の meta タグ
        meta_token = soup.find('meta', {'name': 'csrf-token'})
        if meta_token:
            meta_param = soup.find('meta', {'name': 'csrf-param'})
            name = meta_param.get('content', 'authenticity_token') if meta_param else 'authenticity_token'
            return name, meta_token.get('content')
        # hidden input でフィールド名に "token" か "csrf" を含むものをすべて候補にする
        # 例: signin[_csrf_token], authenticity_token, _token, csrf_token など
        for tag in soup.find_all('input', {'type': 'hidden'}):
            name = tag.get('name', '')
            if 'token' in name.lower() or 'csrf' in name.lower():
                return name, tag.get('value')
        return None, None

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
    def _parse_entry_datetime(iso_str: str) -> datetime | None:
        """fetch_entries_since 用: ISO文字列をawareなdatetimeに変換する。失敗時はNone。"""
        if not iso_str:
            return None
        try:
            dt = datetime.fromisoformat(iso_str)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            return None

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
