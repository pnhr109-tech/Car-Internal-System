# gigicompany社内システム アーキテクチャ

**プロジェクト名**: gigicompany-system  
**作成日**: 2026年2月13日  
**バージョン**: 1.0.0

---

## 📋 目次

1. [システム概要](#システム概要)
2. [アプリケーション構成](#アプリケーション構成)
3. [ビジネスフロー](#ビジネスフロー)
4. [データベース設計](#データベース設計)
5. [URL設計](#url設計)
6. [今後の開発予定](#今後の開発予定)

---

## システム概要

gigicompanyの業務を統合管理する社内システム。
車買取ビジネスを中心に、顧客管理、従業員管理、勤怠管理、営業管理などを一元化。

### 技術スタック
- **Framework**: Django 5.0.1
- **Database**: MySQL 8.0
- **Frontend**: Bootstrap 5 + Vanilla JavaScript
- **External API**: Google Calendar API, Google Chat API

---

## アプリケーション構成

### 📁 プロジェクト構造

```
gigicompany-system/
├── config/                      # Djangoプロジェクト設定
│   ├── settings.py             # 環境設定
│   ├── urls.py                 # ルーティング統合
│   └── wsgi.py                 # WSGIエントリーポイント
│
├── core/                        # 共通基盤
│   ├── models.py               # 共通抽象モデル
│   ├── mixins.py               # 共通Mixin
│   ├── utils.py                # 共通ユーティリティ
│   └── middleware.py           # カスタムミドルウェア
│
├── employees/                   # 従業員管理 🔨未実装
│   ├── models.py               # Employee, Department, Position
│   ├── views.py                # 従業員CRUD
│   ├── admin.py
│   └── templates/employees/
│
├── customers/                   # 顧客管理 🔨未実装
│   ├── models.py               # Customer, Contact
│   ├── views.py                # 顧客情報管理
│   └── templates/customers/
│
├── leads/                       # 査定申込管理 ✅実装済み
│   ├── models.py               # Lead, AssessmentRequest
│   ├── views.py                # 査定申込一覧・詳細
│   └── templates/leads/
│       └── assessment_list.html
│
├── sales/                       # 査定・商談管理 🔨未実装
│   ├── models.py               # Negotiation, Contract, SalesRecord
│   ├── views.py                # 査定・商談・契約・売上管理
│   ├── reports.py              # レポート生成
│   └── templates/sales/
│
├── vehicles/                    # 車両管理 🔨未実装
│   ├── models.py               # Vehicle, Purchase, Sale, Inventory
│   ├── views.py                # 在庫管理・買取売却
│   └── templates/vehicles/
│
├── attendance/                  # 勤怠管理 🔨未実装
│   ├── models.py               # AttendanceRecord, Leave, Overtime
│   ├── views.py                # 打刻・勤怠承認
│   ├── management/commands/    # 月次集計コマンド
│   └── templates/attendance/
│
├── dashboard/                   # ダッシュボード 🔨未実装
│   ├── views.py                # KPI表示・統計
│   └── templates/dashboard/
│       └── index.html          # 社内システムTOP
│
├── admin_panel/                 # 管理者機能 🔨未実装
│   ├── views.py                # システム設定・ユーザー管理
│   └── templates/admin_panel/
│
├── accounts/                    # 認証機能 ✅実装済み
│   ├── views.py                # Googleログイン / ログアウト
│   ├── urls.py                 # /login, /logout
│   └── templates/accounts/
│       └── google_login.html
│
├── static/                      # 共通静的ファイル
│   ├── css/
│   │   └── common.css
│   ├── js/
│   │   └── common.js
│   └── images/
│       └── logo.png
│
├── templates/                   # 共通テンプレート
│   ├── base.html               # ベーステンプレート
│   ├── navigation.html         # グローバルナビゲーション
│   ├── 404.html
│   └── 500.html
│
├── docker-compose.yml
├── requirements.txt
├── .gitignore
├── .env
├── README.md
└── ARCHITECTURE.md             # このファイル
```

---

## アプリケーション一覧

### 基盤系

| アプリ | ステータス | 役割 | 主なモデル | URL |
|--------|----------|------|-----------|-----|
| **core** | 🔨未実装 | 共通基盤・ユーティリティ | BaseModel, TimestampMixin | - |
| **employees** | 🔨未実装 | 従業員マスタ管理 | Employee, Department, Position | /employees/ |
| **customers** | 🔨未実装 | 顧客マスタ管理 | Customer, Contact | /customers/ |
| **dashboard** | 🔨未実装 | 統合ダッシュボード | - | / |
| **admin_panel** | 🔨未実装 | システム管理者機能 | SystemConfig, AuditLog | /admin-panel/ |
| **accounts** | ✅実装済み | Google認証・ログイン制御 | User(Django標準) | /login/, /logout/ |

### 業務系

| アプリ | ステータス | 役割 | 主なモデル | URL |
|--------|----------|------|-----------|-----|
| **leads** | ✅実装済み | 査定申込管理 | Lead, AssessmentRequest | /leads/ |
| **sales** | 🔨未実装 | 査定・商談・契約管理 | Negotiation, Contract, SalesRecord | /sales/ |
| **vehicles** | 🔨未実装 | 車両管理（買取・在庫・売却） | Vehicle, Purchase, Sale, Inventory | /vehicles/ |
| **attendance** | 🔨未実装 | 勤怠管理 | AttendanceRecord, Leave, Overtime | /attendance/ |

---

## ビジネスフロー

### 車買取ビジネスの流れ

```
┌─────────────┐
│1. 査定申込  │  leads/ (査定申込管理)
│ (新規申込)  │  - ナビクルから自動取得（スクレイパー）
└──────┬──────┘  - 手動登録
       │
       ▼
┌─────────────┐
│2. 査定・商談│  sales/ (査定・商談管理)
│ (現地査定)  │  - 査定履歴・商談記録
└──────┬──────┘  - ステータス管理（査定中、見積提示、交渉中など）
       │
       ▼
┌─────────────┐
│ 3. 契約     │  sales/ (契約管理)
│  (買取契約) │  - 契約書管理
└──────┬──────┘  - 入金確認
       │
       ▼
┌─────────────┐
│ 4. 買取     │  vehicles/ (車両管理)
│  (在庫化)   │  - 車両情報登録
└──────┬──────┘  - 在庫管理
       │
       ▼
┌─────────────┐
│ 5. 売却     │  vehicles/ (売却管理)
│  (販売完了) │  - 販売記録
└─────────────┘  - 利益計算
       │
       ▼
┌─────────────┐
│ 顧客化      │  customers/ (顧客管理)
│  (リピート) │  - 顧客情報統合
└─────────────┘  - 次回査定申込へ
```

### データ移行パターン

**パターン1: ステータス更新**
- 同じテーブル内でステータスカラムを更新
- 例: Lead.status = '申込' → '商談中' → '契約済み'

**パターン2: テーブル移行**
- ステージが変わったら別テーブルに移動
- 例: AssessmentRequest → Negotiation → Contract → Vehicle
- 関連を外部キーで保持: Vehicle.original_lead_id

---

## データベース設計

### 主要モデル一覧

#### 基盤系

**Employee (従業員)**
```python
- id: 主キー
- user: Djangoユーザー (OneToOne: User) ※ログイン情報
- employee_number: 社員番号
- name: 氏名
- email: メールアドレス
- department: 部署 (FK)
- position: 役職
- role: 権限レベル ('admin', 'manager', 'staff')
- hire_date: 入社日
- is_active: 在籍フラグ
- created_at: 登録日時
```

**User (ログインユーザー) - Django標準 + 拡張**
```python
- id: 主キー
- username: ログインID（社員番号と同じ）
- password: パスワード（ハッシュ化）
- email: メールアドレス
- is_staff: スタッフフラグ
- is_active: アクティブフラグ
- groups: 権限グループ (ManyToMany)
- last_login: 最終ログイン日時
```

**Customer (顧客)**
```python
- id: 主キー
- customer_number: 顧客番号
- name: 氏名
- phone: 電話番号
- email: メールアドレス
- address: 住所
- created_at: 登録日
```

#### 業務系

**AssessmentRequest (査定申込) - leads/**
```python
- id: 主キー
- application_number: お申込番号
- application_datetime: お申込日時
- customer_name: お名前
- phone: 電話番号
- email: メールアドレス
- address: 住所
- maker: メーカー名
- car_model: 車種名
- year: 年式
- mileage: 走行距離
- source: 取得元 ('navikuru', 'manual')
- status: ステータス ('new', 'contacted', 'negotiating', 'contracted', 'canceled')
- assigned_to: 担当者 (FK: Employee)
- created_at: 作成日時
```

**Negotiation (査定・商談) - sales/**
```python
- id: 主キー
- assessment_request: 査定申込 (FK: AssessmentRequest)
- customer: 顧客 (FK: Customer)
- employee: 担当営業 (FK: Employee)
- status: 査定・商談ステータス ('scheduled', 'assessed', 'negotiating', 'offer_made', 'closed_won', 'closed_lost')
- assessment_date: 査定日
- assessment_location: 査定場所
- estimated_price: 査定額
- notes: 査定・商談メモ
- created_at: 作成日時
```

**Vehicle (車両) - vehicles/**
```python
- id: 主キー
- vehicle_number: 車両管理番号
- original_lead: 元の査定申込 (FK: AssessmentRequest)
- customer: 買取元顧客 (FK: Customer)
- maker: メーカー ※ログイン時に自動記録
- clock_out: 退勤時刻 ※ログアウト時に自動記録
- break_minutes: 休憩時間（分）
- work_hours: 勤務時間（自動計算）
- overtime_hours: 残業時間（自動計算）
- login_based: ログイン連動フラグ (True/False)
- status: ステータス ('pending', 'approved', 'rejected')
- approved_by: 承認者 (FK: Employee, nullable)
- approved_at: 承認日時
- notes: 備考
- created_at: 記録日時
- updated_at: 更新日時
```

**ログイン連動の仕組み:**
1. ユーザーがログイン → 自動的に`clock_in`記録
2. ユーザーがログアウト → 自動的に`clock_out`記録
3. `work_hours = clock_out - clock_in - break_minutes`を自動計算
4. 所定労働時間（8時間）を超えた分を`overtime_hours`として記録urchased_at: 買取日
- sold_at: 売却日
```

**AttendanceRecord (勤怠記録) - attendance/**
```python
- id: 主キー
- employee: 従業員 (FK: Employee)
- date: 勤務日
- clock_in: 出勤時刻
- clock_out: 退勤時刻※ログイン後
/login/                        # ログイン画面
/logout/                       # ログアウト
/admin/                        # Django管理画面

# 基盤系
/employees/                    # 従業員一覧（管理者のみ）
/employees/<id>/               # 従業員詳細（管理者のみ）
/employees/me/                 # 自分の情報（全員）
/customers/                    # 顧客一覧（管理者・マネージャー）
/customers/<id>/               # 顧客詳細

# 業務系 - 査定申込管理
/leads/                        # 査定申込一覧（全員）
/leads/<id>/                   # 査定申込詳細
/leads/create/                 # 手動登録
/leads/my/                     # 自分の担当査定申込（一般）

# 業務系 - 査定・商談管理
/sales/                        # 査定・商談管理TOP（全員）
/sales/negotiations/           # 査定・商談一覧
/sales/negotiations/<id>/      # 査定・商談詳細
/sales/contracts/              # 契約一覧
/sales/contracts/<id>/         # 契約詳細
/sales/reports/                # 営業レポート（マネージャー以上）
/sales/my/                     # 自分の営業実績（一般）

# 業務系 - 車両管理
/vehicles/                     # 車両管理TOP（全員）
/vehicles/inventory/           # 在庫一覧
/vehicles/<id>/                # 車両詳細
/vehicles/purchase/            # 買取登録
/vehicles/sale/<id>/           # 売却登録

# 業務系 - 勤怠管理
/attendance/                   # 勤怠管理TOP（全員）
/attendance/me/                # 自分の勤怠（全員）
/attendance/list/              # 勤怠一覧（マネージャー以上）
/attendance/approve/           # 承認画面（マネージャー以上）
/attendance/report/            # 勤怠レポート（マネージャー以上）

# 管理者機能
/admin-panel/                  # 管理者TOP（管理者のみ）
/admin-panel/users/            # ユーザー管理
/admin-panel/permissions/      # 権限
/vehicles/sale/<id>/           # 売却登録

# 業務系 - 勤怠管理
/attendance/                   # 勤怠管理TOP
/attendance/record/            # 打刻（出退勤）
/attendance/list/              # 勤怠一覧
/attendance/approve/           # 承認画面（管理者）
/attendance/report/            # 勤怠レポート

# 管理者機能
/admin-panel/                  # 管理者TOP
/admin-panel/users/            # ユーザー管理
/admin-panel/settings/         # システム設定
/admin-panel/audit-log/        # 操作ログ
```

---

## 技術仕様

### 認証・認可

**認証システム:**
- Django標準認証 + カスタムユーザーモデル
- ログイン・ログアウト機能
- **ログイン時に自動的に出勤打刻、ログアウト時に退勤打刻**
- セッション管理（自動ログアウト: 8時間）

**権限レベル:**

| 権限レベル | 役割 | アクセス範囲 |
|-----------|------|--------------|
| **代表取締役 (admin)** | 管理者・システム管理者 | 全機能アクセス可能 |
| **役職者 (manager)** | 部門長・管理職 | 承認機能、レポート閲覧、自部門編集 |
| **一般 (staff)** | 一般従業員・営業担当者 | 営業系機能、自分の担当のみ編集、勤怠入力、自分の情報閲覧のみ |

**アクセス制御マトリクス:**

| 機能 | admin | manager | staff |
|------|-------|---------|-------|
| **従業員管理** | ✅ 全て | ✅ 閲覧のみ | ❌ |
| **顧客管理** | ✅ 全て | ✅ 閲覧・編集 | ✅ 閲覧のみ |
| **査定申込管理** | ✅ 全て | ✅ 全て | ✅ 自分の担当のみ |
| **査定・商談管理** | ✅ 全て | ✅ 全て | ✅ 自分の担当のみ |
| **車両管理** | ✅ 全て | ✅ 全て | ✅ 閲覧・編集可 |
| **勤怠管理** | ✅ 全て | ✅ 承認権限あり | ✅ 自分のみ |
| **ダッシュボード** | ✅ 全データ | ✅ 自部門データ | ✅ 自分のデータ |
| **管理者機能** | ✅ 全て | ❌ | ❌ |
- [ ] ログイン・ログアウト機能
- [ ] 権限グループ設定（admin/manager/staff）
- [ ] ログイン連動の勤怠自動記録
- [ ] アクセス制御（デコレータ・ミドルウェア）
- [ ] employeesアプリ実装（従業員管理）

### Phase 3: 査定・商談管理
- [ ] salesアプリ実装（査定・商談・契約管理）
- [ ] 査定申込から査定・商談へのステータス遷移
- [ ] 査定・営業レポート機能
- [ ] 権限による表示制御（自分の担当のみ/全て）

### Phase 4: 車両管理
- [ ] vehiclesアプリ実装（在庫管理）
- [ ] 買取・売却フロー
- [ ] 利益計算機能

### Phase 5: 人事・勤怠
- [ ] attendanceアプリ実装（勤怠管理）
- [ ] 勤怠承認フロー（マネージャー権限）
- [ ] 月次集計・レポート
- [ ] 給与計算連携準備

### Phase 6: 顧客管理・ダッシュボード
- [ ] customersアプリ実装
- [ ] dashboardアプリ実装（KPI表示）
- [ ] 権限別ダッシュボード（admin/manager/staff）
- [ ] レポート自動生成

### Phase 7: 管理者機能
- [ ] admin_panelアプリ実装
- [ ] 操作ログ・監査機能
- [ ] システム設定画面
- [ ] 権限管理 車両管理
- [ ] vehiclesアプリ実装（在庫管理）
- [ ] 買取・売却フロー
- [ ] 利益計算機能

### Phase 4: 人事・勤怠
- [ ] employeesアプリ実装（従業員管理）
- [ ] attendanceアプリ実装（勤怠管理）
- [ ] 給与計算連携

### Phase 5: 顧客管理・ダッシュボード
- [ ] customersアプリ実装
- [ ] dashboardアプリ実装（KPI表示）
- [ ] レポート自動生成

### Phase 6: 管理者機能
- [ ] admin_panelアプリ実装
- [ ] 操作ログ・監査機能
- [ ] システム設定画面

---

## 開発ルール

### コーディング規約
- PEP 8準拠
- 日本語コメント推奨
- クラスベースビュー優先

### Git運用
- main: 本番環境
- develop: 開発環境
- feature/xxx: 機能開発ブランチ

### プルリクエスト
- レビュー必須
- テスト実施済みであること

---

## 関連ドキュメント

- [README.md](README.md) - セットアップ手順・運用手順

---

**更新履歴:**
- 2026-02-13: 初版作成
