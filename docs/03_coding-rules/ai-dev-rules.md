# AI Dev Rules (Django + Bootstrap UI)

## Sources of truth
- docs/ui-style-guide.md
- static/ui/tokens.css
- static/ui/bootstrap-overrides.css
- static/ui/responsive.css

## Must follow
- Use Bootstrap layout/components (container, row, col, table, form-control, btn)
- Visual rules (colors/sizes/radius/hover) must follow tokens + overrides
- Do NOT introduce new colors/sizes unless requested
- Button hover must be visible (already enforced by overrides)
- Primary buttons: recommended 1 per screen, allow up to 2 (avoid more)

## When coding templates
- Prefer Bootstrap classes for layout
- For status labels use: ui-badge + ui-badge--(success|warning|danger|info)

---

## レスポンシブ対応ルール

このシステムは PC・スマホ両方に対応する。新機能追加時も必ずPC・スマホ両方で動作するよう実装すること。

### ブレークポイント
| 幅 | 対象 | Bootstrap プレフィックス |
|---|---|---|
| ≦ 767.98px | スマホ・小型タブレット | （無印 / `d-md-none`） |
| ≧ 768px | タブレット〜PC | `md`, `lg`, `xl` |

### タッチターゲット
- ボタン最小高さ: `44px`（`btn` クラスで自動適用済）
- フォーム入力最小高さ: `44px`、`font-size: 16px`（iOS zoom 防止。`responsive.css` で自動適用済）

### 一覧画面（テーブル）
- テーブルには必ず `mobile-card-table` クラスを追加する
- `<tbody>` の各 `<td>` に `data-label="列名"` を付ける（スマホでラベルとして表示される）
- 先頭 `<td>` には `card-title` クラスを付ける（カードのタイトル行になる）
- スマホで非表示にしたい列の `<td>` には `d-mobile-none` クラスを付ける
- 行クリックで詳細遷移する場合は `<tr style="cursor:pointer" onclick="location.href='...'">` を付ける

```html
<table class="table table-hover mb-0 mobile-card-table">
  <thead>...</thead>
  <tbody>
    <tr style="cursor:pointer" onclick="location.href='/path/'">
      <td class="card-title">顧客名（タイトル）</td>
      <td data-label="電話">090-xxxx-xxxx</td>
      <td data-label="ステータス"><span class="badge ...">...</span></td>
      <td class="d-mobile-none">PCのみ表示する列</td>
    </tr>
  </tbody>
</table>
```

### JS 動的テーブル（assessment_list など）
- デスクトップ用 `<table>` に `d-none d-md-block` でラップ
- スマホ用カードコンテナ `<div class="d-md-none" id="...CardContainer">` を追加
- `renderTable` 関数内でデスクトップ（tbody）・スマホ（cardContainer）両方を描画する
- モバイルカードは `assessment-card-item` クラスを使う

### モーダル
- スマホでは CSS により全モーダルが自動的に全画面表示になる（`responsive.css` が自動適用）
- 追加の対応は不要

### ナビタブ
- `nav-tabs` は `responsive.css` により自動的に横スクロール対応になる

### サイドバー
- offcanvas は `responsive.css` により自動的にスマホで全画面になる

### 電話番号
- スマホでタップ発信できるよう `<a href="tel:xxx">` でリンクにする

---

## Django モデル設計ルール

### フィールド定義
- 全フィールドに `verbose_name` を付ける
- `null=True, blank=True` は任意項目のみ。必須項目には付けない
- `choices` は必ずモデルクラス変数として定義する（例: `FUEL_TYPE_CHOICES = [...]`）
- 選択肢の値はスネークケース英字（例: `'in_progress'`）、表示名は日本語

### 全モデル共通フィールド（必須）
```python
created_at = models.DateTimeField(auto_now_add=True, verbose_name='作成日時')
updated_at = models.DateTimeField(auto_now=True,     verbose_name='更新日時')
updated_by = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True, blank=True,
    related_name='updated_<モデル名複数形>',
    verbose_name='更新者',
)
```

### class Meta（必須）
```python
class Meta:
    db_table = 'テーブル名（スネークケース・複数形）'
    verbose_name = '日本語単数形'
    verbose_name_plural = '日本語複数形'
```

### 部分更新パターン
- モデルの一部フィールドだけ更新する場合は `save(update_fields=[...])` を使う
- `update_fields` には必ず `'updated_by'` も含める

---

## Django View ルール

### デコレーター
- 全ビューに `@login_required` を付ける（認証必須）
- POST のみ受け付ける API には `@require_POST` を付ける
- GET のみ受け付ける API には `@require_GET` を付ける

### 画面ビュー（HTML を返す）
- `render(request, 'template.html', context)` で返す
- コンテキストキーは snake_case

### API ビュー（JSON を返す）
- `JsonResponse(...)` で返す
- レスポンス形式は以下で統一する:

```python
# 成功時
return JsonResponse({'success': True, 'data': ..., 'message': '...'})

# 失敗時
return JsonResponse({'success': False, 'message': 'エラー内容'}, status=400)
```

### DB 変更処理
- 複数テーブルをまたぐ書き込みは必ず `with transaction.atomic():` で囲む

### ヘルパー関数
- ビュー間で共通化できるロジックは `_` プレフィックス付きのモジュールレベル関数として切り出す
  - 例: `_sync_customer_from_contract(...)`, `_generate_application_number(...)`

---

## Views パッケージ分割ルール

ビュー数が増えると `views.py` が肥大化するため、業務フェーズ単位でモジュール分割する。

### ディレクトリ構成

```
leads/views/
├── __init__.py    # 全ビューを re-export（urls.py を変更不要にする）
├── utils.py       # ビュー内共通ヘルパー（外部から直接 import しない）
├── assessment.py  # 査定申込フェーズ
├── case.py        # 案件・商談フェーズ
├── contract.py    # 契約・承認フェーズ
├── customer.py    # 顧客マスタ管理
└── webhook.py     # 外部 Webhook（Gmail Push 通知など）
```

### 分割の基準

| モジュール | 含めるビュー |
|---|---|
| `assessment.py` | 査定申込の一覧・詳細・作成・編集・関連 API |
| `case.py` | 案件（Assessment）詳細・各種情報更新 API |
| `contract.py` | 契約・承認フェーズの画面・API |
| `customer.py` | 顧客マスタの一覧・詳細・直接編集 API |
| `webhook.py` | CSRF 不要な外部受信エンドポイント（`@csrf_exempt`）|
| `utils.py` | `_` プレフィックス付きヘルパー。ビュー関数を含めない |

### インポート規則

```python
# 各サブモジュール内
from ..models import Customer, Assessment    # leads/models.py
from .utils import _require_manager          # leads/views/utils.py

# __init__.py — urls.py から透過的に使えるよう re-export
from .assessment import assessment_list, ...
from .case import case_list, ...
```

- `urls.py` は `from . import views` のままで変更不要
- `utils.py` のヘルパーは他の views モジュールからのみ import する（テンプレートや urls からは参照しない）

---

## URL 設計ルール

### 命名規則
| 種別 | パターン | 例 |
|---|---|---|
| 画面（一覧） | `/sateiinfo/resource/` | `/sateiinfo/cases/` |
| 画面（詳細） | `/sateiinfo/resource/<pk>/` | `/sateiinfo/cases/42/` |
| API（操作） | `/sateiinfo/api/resource/<pk>/action/` | `/sateiinfo/api/cases/42/update/` |
| API（一覧取得） | `/sateiinfo/api/resource/` | `/sateiinfo/api/assessments/` |

### URL name の命名
- 画面: `verb_resource`（例: `case_list`, `case_detail`, `assessment_create`）
- API: `verb_resource`（例: `update_assessment_info`, `create_contract`）
- ネームスペース `app_name = 'leads'` を使い、テンプレートでは `{% url 'leads:name' %}` で参照する

---

## マイグレーション ルール

- 必ず `--name` オプションで説明的な名前を付ける
  ```bash
  python manage.py makemigrations --name add_furigana_to_customer
  ```
- 1 マイグレーション = 1 つの変更テーマ（複数モデルをまたいでも「同一目的」ならまとめてよい）
- マイグレーションは作成後、Docker コンテナ内で必ず `python manage.py migrate` を実行して適用する

---

## ロギング ルール

- 各 Python ファイルの冒頭で `logger = logging.getLogger(__name__)` を宣言する
- エラーは `logger.error(...)` または `logger.exception(...)` で記録する
- デバッグ用の `print()` は残さない

## JS / CSS の配置ルール

### 原則: HTML への直書き禁止
- `<style>` タグによるインライン CSS は書かない
- `<script>` タグへの関数・ロジック直書きは書かない
- Bootstrap クラスで対応できないスタイルは `static/ui/` 配下の既存ファイルに追加する

### JS ファイル構成 (`static/js/`)

| ファイル | 役割 |
|---|---|
| `app.js` | 全ページ共通ユーティリティ (`getCsrf`, `showToast`, `apiFetch`) |
| `sidebar.js` | 勤怠タイマー・通知ポーリング（`internal_base.html` 経由で全ページロード） |
| `{page_name}.js` | 画面固有のロジック（案件詳細・顧客詳細など） |

- `app.js` と `sidebar.js` は `internal_base.html` でグローバルロード済み。新規ページからは自由に使える
- 新しい画面を作る場合、JS は `static/js/{page_name}.js` として切り出し、テンプレートの `{% block extra_scripts %}` で読み込む
- 画面ごとに異なる Django テンプレート変数（PK など）だけをインライン `<script>` で宣言し、ロジックはすべて外部ファイルに置く

### テンプレートでの書き方（パターン）
```html
{% block extra_scripts %}
{# Django テンプレート変数のみインライン宣言 #}
<script>const RECORD_ID = {{ object.pk }};</script>
{# ロジックはすべて外部ファイル #}
<script src="{% static 'js/page_name.js' %}"></script>
{% endblock %}
```

### CSRF トークン
- `getCsrf()` を使う（`app.js` 定義済み、`<meta name="csrf-token">` から取得）
- 各ページで `const CSRF = '{{ csrf_token }}'` を宣言しない

### fetch 呼び出し
- `apiFetch(url, options)` を使う（CSRF・Content-Type・credentials を自動付与）
- 生の `fetch()` は CSRF を手動付与する必要があるため原則使わない