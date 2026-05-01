"""
査定システム（satei.u-car.co.jp）からのスクレイピングサービス。

フロー:
    1. ログイン（POST /index.do）
    2. 査定IDで検索（code フィールド）
    3. 検索結果から内部IDを取得
    4. 詳細ページ（/editDetail.do?id=...）から車両情報を抽出
"""
import time
import logging
from datetime import date

import requests
from bs4 import BeautifulSoup
from django.conf import settings

logger = logging.getLogger(__name__)

ERA_BASE   = {'R': 2018, 'H': 1988, 'S': 1925, 'T': 1911}
ERA_ABBREV = {'令和': 'R', '平成': 'H', '昭和': 'S', '大正': 'T'}


# ---------------------------------------------------------------------------
# パース補助
# ---------------------------------------------------------------------------

def _get_text(soup: BeautifulSoup, element_id: str) -> str:
    el = soup.find(id=element_id)
    return el.get_text(strip=True) if el else ''


def _get_input_value(soup: BeautifulSoup, name: str) -> str:
    el = soup.find('input', {'name': name})
    return el.get('value', '').strip() if el else ''


def _parse_inspection_date(era: str, date_str: str) -> date | None:
    """era='R', date_str='09/06/25' → date(2027, 6, 25)"""
    era = (era or '').strip()
    date_str = (date_str or '').strip()
    if not era or not date_str:
        return None
    base = ERA_BASE.get(era)
    if base is None:
        return None
    parts = date_str.split('/')
    if len(parts) < 2:
        return None
    try:
        year  = base + int(parts[0])
        month = int(parts[1])
        day   = int(parts[2]) if len(parts) > 2 else 1
        return date(year, month, day)
    except (ValueError, IndexError):
        return None


def _build_year_string(era_text: str, year_num: str, month: str) -> str:
    """era_text='平成', year_num='20', month='06' → 'H20/06'"""
    abbrev   = ERA_ABBREV.get(era_text.strip(), era_text.strip()[:1])
    year_num = year_num.strip()
    month    = month.strip()
    return f'{abbrev}{year_num}/{month}' if month else f'{abbrev}{year_num}'


def _parse_price(value: str) -> int | None:
    """'39,000' → 39000  /  '25.0' → 25  /  '' → None"""
    cleaned = (value or '').replace(',', '').strip()
    if not cleaned:
        return None
    try:
        return int(float(cleaned))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# メイン処理
# ---------------------------------------------------------------------------

def scrape_vehicle_data(assessment_system_id: str) -> dict:
    """
    査定システムにログインし、指定の査定ID（10桁）の車両情報を返す。

    Returns:
        {
            'vehicle':          { maker, car_model, year, mileage, grade, color,
                                  displacement, chassis_number, registration_number,
                                  passenger_count, body_type, drive_type, inspection_expiry },
            'assessment_price': int | None,
            'recycle_amount':   int | None,
        }
    Raises:
        requests.HTTPError, ValueError
    """
    base_url = settings.ASSESSMENT_SYSTEM_BASE_URL
    session  = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (compatible; internal-system)'})

    # 1. GETでログインページを取得してセッショントークンを確立
    logger.info('査定システム: ログインページ取得中')
    login_page_resp = session.get(f'{base_url}/index.do', timeout=30)
    login_page_resp.raise_for_status()

    # ログインフォームの hidden フィールドをすべて収集
    login_page_soup = BeautifulSoup(login_page_resp.text, 'html.parser')
    login_form_data = _get_form_data(login_page_soup, 'id') or _get_form_data(login_page_soup, 'pwd') or {}
    login_form_data.update({
        'id':     settings.ASSESSMENT_SYSTEM_USER,
        'pwd':    settings.ASSESSMENT_SYSTEM_PASSWORD,
        'Submit': 'ログイン',
    })

    # ログインフォームの action を動的解決
    login_url = _resolve_form_url(base_url, login_page_soup, 'id') or f'{base_url}/index.do'

    # 2. ログイン POST
    logger.info('査定システム: ログイン中 (%s)', assessment_system_id)
    login_resp = session.post(
        login_url,
        data=login_form_data,
        headers={'Referer': login_page_resp.url},
        timeout=30,
    )
    login_resp.raise_for_status()

    # 3. 検索フォームを探してサブミット
    landing_soup = BeautifulSoup(login_resp.text, 'html.parser')
    search_url   = _resolve_search_url(base_url, landing_soup)
    logout_url   = _resolve_logout_url(base_url, landing_soup)

    search_form_data = _get_form_data(landing_soup, 'code')
    search_form_data['code']       = assessment_system_id
    search_form_data['query_type'] = '1'   # 直接検索（査定IDで絞り込み）

    try:
        logger.info('査定システム: 検索中 (url=%s, code=%s)', search_url, assessment_system_id)
        search_resp = session.post(
            search_url,
            data=search_form_data,
            headers={'Referer': login_resp.url},
            timeout=30,
        )
        search_resp.raise_for_status()

        # ログインページへリダイレクトされた場合はGETで再試行
        if _is_login_page(search_resp):
            logger.warning('査定システム: POST検索でセッション切れ → GETで再試行')
            search_resp = session.get(
                search_url,
                params={'code': assessment_system_id},
                headers={'Referer': login_resp.url},
                timeout=30,
            )
            search_resp.raise_for_status()


        # 4. 検索結果から内部IDを取得
        result_soup = BeautifulSoup(search_resp.text, 'html.parser')
        # ログアウトURLが未取得の場合、検索結果ページから再試行
        if not logout_url:
            logout_url = _resolve_logout_url(base_url, result_soup)

        internal_id = _find_internal_id(result_soup, assessment_system_id)
        if not internal_id:
            raise ValueError(f'査定ID {assessment_system_id} のレコードが見つかりませんでした')

        # 4. 詳細ページ取得
        timestamp  = int(time.time() * 1000)
        detail_url = f'{base_url}/editDetail.do?id={internal_id}&{timestamp}'
        logger.info('査定システム: 詳細ページ取得 (%s)', detail_url)
        detail_resp = session.get(detail_url, timeout=30)
        detail_resp.raise_for_status()

        # 5. データ抽出
        detail_soup = BeautifulSoup(detail_resp.text, 'html.parser')
        return _extract_data(detail_soup)

    finally:
        # 6. 必ずログアウト（セッション残留によるログインエラーを防ぐ）
        _logout(session, base_url, logout_url)


def _resolve_form_url(base_url: str, soup: BeautifulSoup, anchor_field: str) -> str | None:
    """anchor_field を含むフォームの action URL を返す。"""
    anchor = soup.find('input', {'name': anchor_field})
    if not anchor:
        return None
    form = anchor.find_parent('form')
    if not form:
        return None
    action = (form.get('action', '') or '').strip()
    if not action:
        return None
    return action if action.startswith('http') else f'{base_url}{action}'



def _is_login_page(resp: requests.Response) -> bool:
    """レスポンスがログインページかどうかを判定する。"""
    return 'login.css' in resp.text or 'ログイン' in resp.text[:200]


def _get_form_data(soup: BeautifulSoup, anchor_field: str) -> dict:
    """anchor_field を含むフォームの全 input/select 値を返す。"""
    anchor = soup.find('input', {'name': anchor_field})
    if not anchor:
        return {}
    form = anchor.find_parent('form')
    if not form:
        return {}
    data = {}
    for inp in form.find_all('input'):
        name  = inp.get('name', '')
        value = inp.get('value', '')
        itype = inp.get('type', '').lower()
        # submit/image も含める（Java Struts はボタン名でアクションを判定することがある）
        if name and itype != 'reset':
            data[name] = value
    for sel in form.find_all('select'):
        name = sel.get('name', '')
        if name:
            selected = sel.find('option', selected=True)
            data[name] = selected.get('value', '') if selected else ''
    return data


def _resolve_search_url(base_url: str, soup: BeautifulSoup) -> str:
    """ログイン後ページから検索フォームのURLを動的に解決する。"""
    code_input = soup.find('input', {'name': 'code'})
    if code_input:
        form   = code_input.find_parent('form')
        action = (form.get('action', '') if form else '').strip()
        if action:
            return action if action.startswith('http') else f'{base_url}{action}'
    return f'{base_url}/search.do'


def _resolve_logout_url(base_url: str, soup: BeautifulSoup) -> str | None:
    """
    ページからログアウトリンクのURLを取得する。
    <img alt="ログアウト"> を含む <a> タグの href を探す。
    """
    img = soup.find('img', alt='ログアウト')
    if img:
        a_tag = img.find_parent('a')
        if a_tag and a_tag.get('href'):
            href = a_tag['href'].strip()
            if href and href != '#' and not href.startswith('javascript'):
                return href if href.startswith('http') else f'{base_url}{href}'
    return None


def _logout(session: requests.Session, base_url: str, logout_url: str | None) -> None:
    """ログアウトを実行してセッションを破棄する。"""
    url = logout_url or f'{base_url}/logout.do'
    try:
        session.get(url, timeout=10)
        logger.info('査定システム: ログアウト完了 (%s)', url)
    except Exception:
        logger.warning('査定システム: ログアウト失敗 (%s)', url)


def _find_internal_id(soup: BeautifulSoup, assessment_system_id: str) -> str | None:
    """
    検索結果の hdnResultJsonCache hidden input からJSON解析して内部IDを返す。
    {"datas": [{"id": "12810950", "code": "2604280006", ...}]}
    """
    import html as _html
    import json as _json

    cache_el = soup.find('input', {'id': 'hdnResultJsonCache'})
    if cache_el:
        raw = cache_el.get('value', '')
        if raw:
            try:
                data = _json.loads(_html.unescape(raw))
                for row in data.get('datas', []):
                    if str(row.get('code', '')) == assessment_system_id:
                        logger.info('査定システム: 内部ID発見 (%s → %s)', assessment_system_id, row['id'])
                        return str(row['id'])
                logger.warning('査定システム: datas内に code=%s が見つからない (件数=%d)', assessment_system_id, len(data.get('datas', [])))
            except Exception as e:
                logger.warning('査定システム: JSONキャッシュパース失敗 %s', e)

    return None


def _extract_data(soup: BeautifulSoup) -> dict:
    """詳細ページHTMLから車両情報・価格を抽出する。"""
    # 年式
    era_text = _get_text(soup, 'CAR_ERA')
    year_num = _get_input_value(soup, 'car_year')
    month    = _get_text(soup, 'DIV_CARMONTH')
    year     = _build_year_string(era_text, year_num, month)

    # 登録番号（4分割を結合）
    reg_parts = [
        _get_input_value(soup, 'reg_number1'),
        _get_input_value(soup, 'reg_number2'),
        _get_input_value(soup, 'reg_number3'),
        _get_input_value(soup, 'reg_number4'),
    ]
    registration_number = ' '.join(p for p in reg_parts if p)

    # 車検有効期限
    inspection_era      = _get_text(soup, 'INSPECTION_ERA')
    inspection_date_str = _get_input_value(soup, 'inspection_date')
    inspection_expiry   = _parse_inspection_date(inspection_era, inspection_date_str)

    # ボディタイプ（span要素）
    body_type_el = soup.find(id='txtBodyType')
    body_type    = body_type_el.get_text(strip=True) if body_type_el else ''

    return {
        'vehicle': {
            'maker':               _get_text(soup, 'DIV_MAKER'),
            'car_model':           _get_text(soup, 'DIV_CARNAME'),
            'year':                year,
            'mileage':             _get_input_value(soup, 'distance'),
            'grade':               _get_text(soup, 'DIV_GRADE'),
            'color':               _get_input_value(soup, 'color_name'),
            'displacement':        _get_input_value(soup, 'engine_displacement'),
            'chassis_number':      _get_input_value(soup, 'syadai_no'),
            'registration_number': registration_number,
            'passenger_count':     _get_input_value(soup, 'capacity'),
            'body_type':           body_type,
            'drive_type':          _get_input_value(soup, 'drive'),
            'inspection_expiry':   inspection_expiry,
        },
        'assessment_price': _parse_price(_get_input_value(soup, 'nyuuko_price')),
        'recycle_amount':   _parse_price(_get_input_value(soup, 'result_recycling_price')),
    }
