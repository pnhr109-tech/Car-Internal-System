# DB設計書（買取業務フロー）

> 元資料：`docs/01_requirements/entity-list.md`
> フレームワーク：Django 5.0.1 / DB：MySQL 8.0
> ★ = エンティティ一覧の顧客ヒアリングで追加された項目

---

## 目次

1. [Djangoアプリ割り当て](#1-djangoアプリ割り当て)
2. [共通設計方針](#2-共通設計方針)
3. [employees — 従業員・店舗](#3-employees--従業員店舗)
4. [customers — 顧客](#4-customers--顧客)
5. [vehicles — 車両](#5-vehicles--車両)
6. [leads — 査定申込チャネル](#6-leads--査定申込チャネル)
7. [sales — 査定・契約](#7-sales--査定契約)
8. [operations — 引き取り・出品準備・陸送](#8-operations--引き取り出品準備陸送)
9. [marketplace — オークション・Web掲載](#9-marketplace--オークションweb掲載)
10. [finance — 入金・支払い](#10-finance--入金支払い)
11. [common — 共通](#11-common--共通)
12. [ER図（概要）](#12-er図概要)

---

## 1. Djangoアプリ割り当て

| Djangoアプリ | 管理エンティティ |
|---|---|
| `employees` | 従業員、店舗 |
| `customers` | 顧客、顧客口座情報 |
| `vehicles` | 車両、車両画像 |
| `leads` | 予約、チャネル別申込（ナビクル/マイカースカウト/HP/来店/カービュー/紹介/メール）、外部サービスマスタ |
| `sales` | 査定、査定チェック項目、買取契約、書類、書類種別マスタ、本人確認書類、所有権解除管理、先払い入金記録 |
| `operations` | 引き取り、付属品確認、出品準備、準備作業明細、整備記録、整備明細、付帯費用、陸送業者マスタ、陸送 |
| `marketplace` | オークション会場マスタ、出品、流れ・不備記録、WEB掲載媒体マスタ、WEB掲載 |
| `finance` | 入金記録、支払記録 |
| `common` | 取引・連絡履歴 |

---

## 2. 共通設計方針

### フィールド命名規則
- PK: `id` (BigAutoField, AUTO_INCREMENT)
- FK: `{参照モデル名}_id`（例: `customer_id`, `assessment_id`）
- タイムスタンプ: `created_at`, `updated_at`（全テーブル共通）
- 更新者: `updated_by_id` → FK to `employees_employee`

### 抽象基底モデル（`core.models.BaseModel`）
全テーブルに以下を自動付与:
```python
created_at  = DateTimeField(auto_now_add=True)
updated_at  = DateTimeField(auto_now=True)
updated_by  = ForeignKey('employees.Employee', null=True, on_delete=SET_NULL)
```

### 金額フィールド
- 税抜金額: `DecimalField(max_digits=10, decimal_places=0)`
- 消費税額: `DecimalField(max_digits=10, decimal_places=0)`
- 税込金額: 基本的にDBには持たず、必要に応じてプロパティで計算

### ステータスフィールド
- `CharField(max_length=20, choices=...)` を使用
- choices は各モデル内で定数定義

---

## 3. employees — 従業員・店舗

### Store（店舗）
**テーブル名:** `employees_store`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| name | CharField(50) | NOT NULL | 店舗名 |
| address | CharField(200) | NULL | 所在地 |
| phone | CharField(20) | NULL | 電話番号 |
| is_active | BooleanField | DEFAULT TRUE | 稼働中フラグ |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### Employee（従業員）
**テーブル名:** `employees_employee`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| user_id | OneToOneField → `auth_user` | NULL | Djangoログインユーザー |
| employee_number | CharField(20) | UNIQUE NOT NULL | 社員ID |
| name | CharField(50) | NOT NULL | 氏名 |
| store_id | ForeignKey → `employees_store` | NULL | 所属店舗 |
| department | CharField(50) | NULL | 所属部署 |
| role | CharField(20) | NOT NULL | 権限（`admin` / `manager` / `staff`） |
| is_active | BooleanField | DEFAULT TRUE | 在籍フラグ |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

**インデックス:** `employee_number`, `store_id`

---

## 4. customers — 顧客

### Customer（顧客）
**テーブル名:** `customers_customer`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| name | CharField(100) | NOT NULL | 氏名 |
| phone | CharField(20) | NULL | 電話番号 |
| email | EmailField | NULL | メールアドレス |
| address | CharField(200) | NULL | 住所 |
| age | PositiveSmallIntegerField | NULL | 年齢 |
| occupation | CharField(50) | NULL | 職業 |
| gender | CharField(10) | NULL | 性別（`male` / `female` / `other`） |
| family_structure | CharField(100) | NULL | 家族構成 |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |

**インデックス:** `phone`, `email`

---

### CustomerAccount（顧客口座情報）
**テーブル名:** `customers_customeraccount`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| bank_name | CharField(50) | NOT NULL | 銀行名 |
| branch_name | CharField(50) | NOT NULL | 支店名 |
| account_type | CharField(10) | NOT NULL | 口座種別（`ordinary` / `current`） |
| account_number | CharField(20) | NOT NULL | 口座番号 |
| account_holder | CharField(100) | NOT NULL | 口座名義 |
| is_primary | BooleanField | DEFAULT FALSE | 優先フラグ |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |

**インデックス:** `customer_id`

---

## 5. vehicles — 車両

### Vehicle（車両）
**テーブル名:** `vehicles_vehicle`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| maker | CharField(50) | NOT NULL | メーカー |
| car_model | CharField(100) | NOT NULL | 車種 |
| grade | CharField(100) | NULL | グレード |
| color | CharField(50) | NULL | カラー |
| model_year | PositiveSmallIntegerField | NULL | 年式 |
| mileage | PositiveIntegerField | NULL | 走行距離（km） |
| displacement | PositiveIntegerField | NULL | 排気量（cc） |
| transmission | CharField(10) | NULL | ミッション（`AT` / `MT` / `CVT`）★ |
| registration_number | CharField(20) | NULL | 登録番号（ナンバー）★ |
| chassis_number | CharField(50) | NULL | 車台番号★ |
| first_registration_date | DateField | NULL | 初年度登録年月★ |
| has_repair_history | BooleanField | NULL | 修復歴フラグ★ |
| inspection_expiry | DateField | NULL | 車検有効期限★ |
| notes | TextField | NULL | 備考 |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |

**インデックス:** `maker`, `car_model`, `chassis_number`

---

### VehicleImage（車両画像）
**テーブル名:** `vehicles_vehicleimage`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NOT NULL | |
| image_path | CharField(500) | NOT NULL | 画像ファイルパス（GCS等） |
| part_type | CharField(50) | NULL | パーツ種別（`exterior` / `interior` / `engine` 等） |
| taken_at | DateTimeField | NULL | 撮影日時 |
| created_at | DateTimeField | auto | |

**インデックス:** `vehicle_id`

---

## 6. leads — 査定申込チャネル

### ExternalServiceMaster（外部サービスマスタ）
**テーブル名:** `leads_externalservicemaster`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| name | CharField(50) | UNIQUE NOT NULL | サービス名（ナビクル/マイカースカウト/カービュー等） |
| notes | TextField | NULL | 備考 |

---

### Reservation（予約）
**テーブル名:** `leads_reservation`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NULL | |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | 担当者 |
| channel_type | CharField(20) | NOT NULL | チャネル種別（`navicle` / `mycar` / `hp` / `walk_in` / `carview` / `referral` / `email`） |
| scheduled_at | DateTimeField | NULL | 査定日時 |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |

**インデックス:** `customer_id`, `channel_type`, `scheduled_at`

---

### NavicleLead（ナビクル申込）
**テーブル名:** `leads_naviclelead`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| reservation_id | OneToOneField → `leads_reservation` | NULL | 予約紐付け |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NULL | |
| external_service_id | ForeignKey → `leads_externalservicemaster` | NOT NULL | |
| external_id | CharField(100) | NULL | 外部サービスID |
| applied_at | DateTimeField | NULL | 申込日時 |
| inquiry_count | PositiveIntegerField | DEFAULT 0 | 問合件数 |
| last_contacted_at | DateTimeField | NULL | 最終連絡日時 |
| contracted_at | DateTimeField | NULL | 成約日時 |
| assigned_employee_name | CharField(50) | NULL | 担当者名（外部表示名） |
| status | CharField(20) | NOT NULL | ステータス（下記参照）★ |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

**status choices:** `pending`（未対応）/ `in_progress`（対応中）/ `done`（対応済）/ `lost`（没）/ `call_banned`（架電禁止）/ `bad`（不良）/ `user_cancelled`（ユーザーキャンセル）

**インデックス:** `customer_id`, `status`, `external_id`

---

### MyCarScoutLead（マイカースカウト申込）
**テーブル名:** `leads_mycarsscoutlead`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| reservation_id | OneToOneField → `leads_reservation` | NULL | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NULL | |
| external_service_id | ForeignKey → `leads_externalservicemaster` | NOT NULL | |
| external_id | CharField(100) | NULL | 外部サービスID |
| bid_amount | DecimalField(10,0) | NULL | 入札金額 |
| bid_at | DateTimeField | NULL | 入札日時 |
| applied_at | DateTimeField | NULL | 申込日時 |
| last_contacted_at | DateTimeField | NULL | 最終連絡日時 |
| contracted_at | DateTimeField | NULL | 成約日時 |
| assigned_employee_name | CharField(50) | NULL | 担当者名 |
| status | CharField(20) | NOT NULL | ★（NavicleLead と同じ choices） |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### HPInquiryLead（HP依頼申込）
**テーブル名:** `leads_hpinquirylead`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| reservation_id | OneToOneField → `leads_reservation` | NULL | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NULL | |
| applied_at | DateTimeField | NULL | 申込日時 |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | |
| status | CharField(20) | NOT NULL | ★ |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### WalkInLead（来店申込）
**テーブル名:** `leads_walkinlead`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| reservation_id | OneToOneField → `leads_reservation` | NULL | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NULL | |
| walked_in_at | DateTimeField | NULL | 来店日時 |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | |
| status | CharField(20) | NOT NULL | ★ |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### CarviewLead（カービュー申込）★新規
**テーブル名:** `leads_carviewlead`

NavicleLead と同じ構成。外部サービスID・申込状況・問合件数あり。

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| reservation_id | OneToOneField → `leads_reservation` | NULL | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NULL | |
| external_service_id | ForeignKey → `leads_externalservicemaster` | NOT NULL | |
| external_id | CharField(100) | NULL | 外部サービスID |
| applied_at | DateTimeField | NULL | |
| inquiry_count | PositiveIntegerField | DEFAULT 0 | |
| last_contacted_at | DateTimeField | NULL | |
| contracted_at | DateTimeField | NULL | |
| assigned_employee_name | CharField(50) | NULL | |
| status | CharField(20) | NOT NULL | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### ReferralLead（紹介申込）★新規
**テーブル名:** `leads_referrallead`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| reservation_id | OneToOneField → `leads_reservation` | NULL | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NULL | |
| referrer_name | CharField(100) | NULL | 紹介者名 |
| applied_at | DateTimeField | NULL | |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | |
| status | CharField(20) | NOT NULL | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### EmailLead（メール申込）★新規
**テーブル名:** `leads_emaillead`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| reservation_id | OneToOneField → `leads_reservation` | NULL | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NULL | |
| received_at | DateTimeField | NULL | 受信日時 |
| subject | CharField(200) | NULL | 件名 |
| body_summary | TextField | NULL | 本文要旨 |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | |
| status | CharField(20) | NOT NULL | `pending` / `in_progress` / `done` / `lost` / `user_cancelled` |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

## 7. sales — 査定・契約

### Assessment（査定）
**テーブル名:** `sales_assessment`

> **中心エンティティ。** ②商談以降のほぼ全テーブルがこのIDを参照する。

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| reservation_id | ForeignKey → `leads_reservation` | NULL | 予約紐付け |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NOT NULL | |
| assigned_employee_id | ForeignKey → `employees_employee` | NOT NULL | 担当者 |
| assessed_at | DateTimeField | NULL | 査定日時 |
| assessment_price | DecimalField(10,0) | NULL | 査定額 |
| market_price | DecimalField(10,0) | NULL | 市場相場価格 |
| overall_score | PositiveSmallIntegerField | NULL | 総合評価（1〜5） |
| status | CharField(20) | NOT NULL | `negotiating`（商談中）/ `won`（成約）/ `lost`（不成約）/ `managed`（管理行） |
| cancel_reason | TextField | NULL | キャンセル理由 |
| cancelled_at | DateTimeField | NULL | キャンセル日時 |
| is_managed | BooleanField | DEFAULT FALSE | 管理有無 |
| managed_status | CharField(20) | NULL | `contracted` / `lost` / `re_approach` |
| notes | TextField | NULL | 備考 |
| approved_by_id | ForeignKey → `employees_employee` | NULL | 稟議承認者（マネージャー/次席） |
| approved_at | DateTimeField | NULL | 承認日時 |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |

**インデックス:** `customer_id`, `vehicle_id`, `status`, `assessed_at`

---

### AssessmentCheckItem（査定チェック項目）
**テーブル名:** `sales_assessmentcheckitem`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| check_type | CharField(50) | NOT NULL | 種別（`scratch` / `repair_history` / `interior` / `tire` 等） |
| description | TextField | NULL | 詳細説明 |
| created_at | DateTimeField | auto | |

---

### DocumentTypeMaster（書類種別マスタ）
**テーブル名:** `sales_documenttypemaster`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| name | CharField(100) | UNIQUE NOT NULL | 書類種別名（委任状/譲渡証明書等） |
| is_required | BooleanField | DEFAULT FALSE | 必須フラグ |
| description | TextField | NULL | 説明 |

---

### PurchaseContract（買取契約）
**テーブル名:** `sales_purchasecontract`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL UNIQUE | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NOT NULL | |
| assigned_employee_id | ForeignKey → `employees_employee` | NOT NULL | |
| contracted_at | DateField | NULL | 契約日 |
| purchase_price_ex_tax | DecimalField(10,0) | NOT NULL | 買取確定価格（税抜） |
| tax_amount | DecimalField(10,0) | NOT NULL | 消費税額 |
| payment_scheduled_date | DateField | NULL | 支払い予定日 |
| status | CharField(20) | NOT NULL | `pending`（未契約）/ `contracted`（契約済）/ `cancelled`（破棄） |
| cancel_reason | TextField | NULL | キャンセル理由 |
| cancelled_at | DateTimeField | NULL | キャンセル日時 |
| notes | TextField | NULL | 備考 |
| is_price_corrected | BooleanField | DEFAULT FALSE | 金額訂正フラグ★ |
| corrected_price | DecimalField(10,0) | NULL | 訂正後買取価格★ |
| has_repair | BooleanField | DEFAULT FALSE | 加修フラグ★ |
| repair_notes | TextField | NULL | 加修内容★ |
| has_ownership_release | BooleanField | DEFAULT FALSE | 所有権解除フラグ★ |
| auction_scheduled_date | DateField | NULL | オークション出品予定日★ |
| auction_venue_id | ForeignKey → `marketplace_auctionvenuemaster` | NULL | オークション出品予定会場★ |
| is_advance_payment | BooleanField | DEFAULT FALSE | 先払いフラグ |
| approved_by_id | ForeignKey → `employees_employee` | NULL | 承認者 |
| approved_at | DateTimeField | NULL | 承認日時 |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |

**インデックス:** `assessment_id`, `customer_id`, `status`

---

### Document（書類・後日品）
**テーブル名:** `sales_document`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| contract_id | ForeignKey → `sales_purchasecontract` | NOT NULL | |
| document_type_id | ForeignKey → `sales_documenttypemaster` | NOT NULL | |
| issued_date | DateField | NULL | 発行日 |
| received_date | DateField | NULL | 受領日 |
| status | CharField(20) | NOT NULL | `not_created`（未作成）/ `creating`（作成中）/ `created`（作成済）/ `waiting_receipt`（受領待）/ `received`（受領済）/ `confirmed`（確認済）★ |
| file_path | CharField(500) | NULL | ファイルパス |
| notes | TextField | NULL | 備考 |
| delivery_status | CharField(20) | NULL | 後日品送付ステータス（`not_sent` / `sent`）★ |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### IdentityDocument（本人確認書類）
**テーブル名:** `sales_identitydocument`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| contract_id | ForeignKey → `sales_purchasecontract` | NOT NULL | |
| document_type | CharField(50) | NOT NULL | 種別（`driving_license` / `passport` 等） |
| confirmed_at | DateTimeField | NULL | 確認日時 |
| confirmed_by_id | ForeignKey → `employees_employee` | NULL | |
| file_path | CharField(500) | NULL | ファイルパス |
| notes | TextField | NULL | 備考 |
| created_at | DateTimeField | auto | |

---

### OwnershipReleaseMgmt（所有権解除管理）★新規
**テーブル名:** `sales_ownershipreleasemgmt`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| contract_id | ForeignKey → `sales_purchasecontract` | NOT NULL UNIQUE | |
| pattern | CharField(1) | NOT NULL | パターン（`A`：ディーラー経由 / `B`：自己返済） |
| debt_inquiry_status | CharField(50) | NULL | 残債照会ステータス |
| dealer_doc_sent_date | DateField | NULL | ディーラーへの書類送付日 |
| debt_transfer_date | DateField | NULL | 残債振込日 |
| dealer_doc_returned_date | DateField | NULL | ディーラーからの書類返却日 |
| status | CharField(30) | NOT NULL | `pending`（未対応）/ `inquiring`（残債照会中）/ `doc_sent`（書類送付済）/ `debt_paid`（残債振込済）/ `doc_returned`（書類返却済） |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### AdvancePaymentRecord（先払い入金記録）★新規
**テーブル名:** `sales_advancepaymentrecord`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| contract_id | ForeignKey → `sales_purchasecontract` | NOT NULL | |
| expected_amount | DecimalField(10,0) | NOT NULL | 入金予定額 |
| payment_date | DateField | NULL | 入金日 |
| approved_by_id | ForeignKey → `employees_employee` | NULL | 承認者（社長） |
| status | CharField(20) | NOT NULL | `pending`（未入金）/ `paid`（入金済） |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

## 8. operations — 引き取り・出品準備・陸送

### VehicleRetrieval（車両引き取り）
**テーブル名:** `operations_vehicleretrieval`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL UNIQUE | |
| contract_id | ForeignKey → `sales_purchasecontract` | NOT NULL | |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | |
| scheduled_date | DateField | NULL | 引取予定日 |
| retrieved_at | DateTimeField | NULL | 引取日時 |
| location | CharField(200) | NULL | 引取場所 |
| final_mileage | PositiveIntegerField | NULL | 最終確認走行距離 |
| status | CharField(20) | NOT NULL | `pending`（未済）/ `done`（済） |
| notes | TextField | NULL | 備考 |
| actual_arrival_date | DateField | NULL | 入庫日（変更後）★ |
| destination_store_id | ForeignKey → `employees_store` | NULL | 送り先店舗★ |
| needs_confirmation_doc | BooleanField | DEFAULT FALSE | 引取確認書フラグ★ |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### AccessoryCheck（付属品確認）
**テーブル名:** `operations_accessorycheck`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| retrieval_id | ForeignKey → `operations_vehicleretrieval` | NOT NULL | |
| item_name | CharField(100) | NOT NULL | 付属品名（スペアキー/取扱説明書等） |
| notes | TextField | NULL | 備考 |

---

### ListingPreparation（出品準備）
**テーブル名:** `operations_listingpreparation`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL UNIQUE | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NOT NULL | |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | |
| scheduled_date | DateField | NULL | 出品予定日 |
| completed_date | DateField | NULL | 出品準備完了日 |
| is_complete | BooleanField | DEFAULT FALSE | 完了フラグ |
| notes | TextField | NULL | 備考 |
| has_listing_sheet | BooleanField | DEFAULT FALSE | 出品表作成フラグ★ |
| listing_sheet_url | CharField(500) | NULL | 出品表URL★ |
| needs_deregistration | BooleanField | DEFAULT FALSE | 登録抹消フラグ★ |
| deregistration_status | CharField(20) | NULL | 抹消ステータス（`not_cancelled` / `applying` / `cancelled`）★ |
| approved_by_id | ForeignKey → `employees_employee` | NULL | 承認者（サポートマネージャー） |
| approved_at | DateTimeField | NULL | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### PreparationWorkDetail（準備作業明細）
**テーブル名:** `operations_preparationworkdetail`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| preparation_id | ForeignKey → `operations_listingpreparation` | NOT NULL | |
| work_type | CharField(50) | NOT NULL | 作業種別（`wash` / `photo` / `doc_check` / `clean` 等） |
| is_done | BooleanField | DEFAULT FALSE | 完了フラグ |
| notes | TextField | NULL | 備考 |

---

### MaintenanceRecord（整備記録）
**テーブル名:** `operations_maintenancerecord`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| vehicle_id | ForeignKey → `vehicles_vehicle` | NOT NULL | |
| vendor_name | CharField(100) | NULL | 整備業者名 |
| work_date | DateField | NULL | 作業日 |
| total_cost_ex_tax | DecimalField(10,0) | NULL | 合計費用（税抜） |
| tax_amount | DecimalField(10,0) | NULL | 消費税額 |
| notes | TextField | NULL | 備考 |
| approved_by_id | ForeignKey → `employees_employee` | NULL | 承認者 |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### MaintenanceDetail（整備明細）
**テーブル名:** `operations_maintenancedetail`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| maintenance_id | ForeignKey → `operations_maintenancerecord` | NOT NULL | |
| work_description | CharField(200) | NOT NULL | 作業内容 |
| part_name | CharField(100) | NULL | 部品名 |
| cost_ex_tax | DecimalField(10,0) | NULL | 費用（税抜） |
| tax_amount | DecimalField(10,0) | NULL | 消費税額 |

---

### IncidentalCost（付帯費用）
**テーブル名:** `operations_incidentalcost`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| cost_type | CharField(50) | NOT NULL | 費用種別（`cleaning` / `photo` / `other`） |
| amount_ex_tax | DecimalField(10,0) | NOT NULL | 金額（税抜） |
| tax_amount | DecimalField(10,0) | NULL | 消費税額 |
| occurred_date | DateField | NULL | 発生日 |
| notes | TextField | NULL | 備考 |
| created_at | DateTimeField | auto | |

---

### TransportVendorMaster（陸送業者マスタ）
**テーブル名:** `operations_transportvendormaster`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| name | CharField(100) | UNIQUE NOT NULL | 業者名 |
| phone | CharField(20) | NULL | 電話番号 |
| email | EmailField | NULL | メールアドレス |
| notes | TextField | NULL | 備考 |

---

### Transport（陸送）
**テーブル名:** `operations_transport`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| retrieval_id | ForeignKey → `operations_vehicleretrieval` | NULL | |
| vendor_id | ForeignKey → `operations_transportvendormaster` | NULL | 陸送業者 |
| departure | CharField(200) | NULL | 出発地 |
| destination | CharField(200) | NULL | 到着地（オークション会場/店舗） |
| scheduled_date | DateField | NULL | 陸送予定日 |
| actual_date | DateField | NULL | 陸送実施日 |
| cost_ex_tax | DecimalField(10,0) | NULL | 費用（税抜） |
| tax_amount | DecimalField(10,0) | NULL | 消費税額 |
| status | CharField(20) | NOT NULL | `requested`（依頼済）/ `in_transit`（輸送中）/ `done`（完了） |
| notes | TextField | NULL | 備考 |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

## 9. marketplace — オークション・Web掲載

### AuctionVenueMaster（オークション会場マスタ）
**テーブル名:** `marketplace_auctionvenuemaster`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| name | CharField(100) | UNIQUE NOT NULL | 会場名 |
| location | CharField(200) | NULL | 所在地 |
| fee_type | CharField(10) | NULL | 手数料形式（`rate` / `fixed`） |
| fee_rate | DecimalField(5,4) | NULL | 手数料率（例: 0.0300 = 3%） |
| fee_fixed | DecimalField(10,0) | NULL | 手数料定額 |
| notes | TextField | NULL | 備考 |

---

### AuctionListing（出品）
**テーブル名:** `marketplace_auctionlisting`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| venue_id | ForeignKey → `marketplace_auctionvenuemaster` | NOT NULL | |
| listed_date | DateField | NULL | 出品日 |
| listing_number | CharField(50) | NULL | 出品番号 |
| desired_price | DecimalField(10,0) | NULL | 希望価格 |
| listing_count | PositiveSmallIntegerField | DEFAULT 1 | 出品回数 |
| result | CharField(20) | NULL | 結果（`sold`（落札）/ `passed`（流れ）/ `defect`（不備）） |
| sold_price | DecimalField(10,0) | NULL | 落札価格 |
| commission | DecimalField(10,0) | NULL | 成約手数料 |
| notes | TextField | NULL | 備考 |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

**インデックス:** `assessment_id`, `result`

---

### AuctionNoSaleRecord（流れ・不備記録）
**テーブル名:** `marketplace_auctionnosalerecord`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| listing_id | ForeignKey → `marketplace_auctionlisting` | NOT NULL | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | |
| occurred_date | DateField | NULL | 発生日 |
| category | CharField(20) | NOT NULL | 区分（`sold` / `passed` / `defect`） |
| overall_score | PositiveSmallIntegerField | NULL | 総合評価（1〜5） |
| reason | TextField | NULL | 理由 |
| next_action | CharField(20) | NULL | 対応方針（`re_list`（再出品）/ `web_listing`（Web掲載移行）） |
| created_at | DateTimeField | auto | |

---

### WebListingMediaMaster（WEB掲載媒体マスタ）
**テーブル名:** `marketplace_weblistingmediamaster`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| name | CharField(100) | UNIQUE NOT NULL | 媒体名 |
| url | CharField(500) | NULL | 媒体URL |
| fee_rate | DecimalField(5,4) | NULL | 手数料率 |
| fee_fixed | DecimalField(10,0) | NULL | 手数料定額 |
| notes | TextField | NULL | 備考 |

---

### WebListing（WEB掲載）
**テーブル名:** `marketplace_weblisting`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| media_id | ForeignKey → `marketplace_weblistingmediamaster` | NOT NULL | |
| assigned_employee_id | ForeignKey → `employees_employee` | NULL | |
| start_date | DateField | NULL | 掲載開始日 |
| end_date | DateField | NULL | 掲載終了日 |
| listing_price | DecimalField(10,0) | NULL | 掲載価格 |
| status | CharField(20) | NOT NULL | `listing`（掲載中）/ `sold`（成約）/ `withdrawn`（取り下げ） |
| notes | TextField | NULL | 備考 |
| approved_by_id | ForeignKey → `employees_employee` | NULL | 承認者（社長） |
| approved_at | DateTimeField | NULL | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

## 10. finance — 入金・支払い

### PaymentIncomeRecord（入金記録）
**テーブル名:** `finance_paymentincomerecord`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| contract_id | ForeignKey → `sales_purchasecontract` | NOT NULL | |
| source_type | CharField(20) | NOT NULL | 入金元種別（`auction` / `web`） |
| source_name | CharField(100) | NULL | 入金元名 |
| expected_date | DateField | NULL | 入金予定日 |
| actual_date | DateField | NULL | 実入金日 |
| expected_amount | DecimalField(10,0) | NULL | 入金予定額 |
| actual_amount | DecimalField(10,0) | NULL | 実入金額 |
| bank_account | CharField(200) | NULL | 入金口座 |
| status | CharField(20) | NOT NULL | `unconfirmed`（未確認）/ `confirmed`（確認済） |
| notes | TextField | NULL | 備考 |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

### PaymentRecord（支払記録）
**テーブル名:** `finance_paymentrecord`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NOT NULL | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| contract_id | ForeignKey → `sales_purchasecontract` | NOT NULL | |
| account_id | ForeignKey → `customers_customeraccount` | NULL | 支払先口座 |
| scheduled_date | DateField | NULL | 支払い予定日 |
| actual_date | DateField | NULL | 実支払い日 |
| amount | DecimalField(10,0) | NULL | 支払い額 |
| payment_method | CharField(50) | NULL | 支払い方法（`bank_transfer` 等） |
| is_advance | BooleanField | DEFAULT FALSE | 前倒しフラグ |
| status | CharField(20) | NOT NULL | `unpaid`（未払い）/ `paid`（支払済） |
| notes | TextField | NULL | 備考 |
| is_diff_approved | BooleanField | DEFAULT FALSE | 差異承認フラグ★ |
| diff_reason | TextField | NULL | 差異理由★ |
| approved_by_id | ForeignKey → `employees_employee` | NULL | 承認者（社長/経理） |
| approved_at | DateTimeField | NULL | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |
| created_at | DateTimeField | auto | |
| updated_at | DateTimeField | auto | |

---

## 11. common — 共通

### ContactHistory（取引・連絡履歴）
**テーブル名:** `common_contacthistory`

| フィールド名 | 型 | 制約 | 説明 |
|---|---|---|---|
| id | BigAutoField | PK | |
| assessment_id | ForeignKey → `sales_assessment` | NULL | |
| customer_id | ForeignKey → `customers_customer` | NOT NULL | |
| employee_id | ForeignKey → `employees_employee` | NOT NULL | |
| contacted_at | DateTimeField | NOT NULL | 連絡日時 |
| contact_method | CharField(20) | NOT NULL | 連絡方法（`phone` / `email` / `sms`） |
| summary | TextField | NOT NULL | 連絡内容要旨 |
| created_at | DateTimeField | auto | |
| updated_by_id | ForeignKey → `employees_employee` | NULL | |

**インデックス:** `customer_id`, `assessment_id`, `contacted_at`

---

## 12. ER図（概要）

```
[leads_reservation]
  └─ channel_type によって対応するLeadテーブルを参照
       ├─ leads_naviclelead
       ├─ leads_mycarsscoutlead
       ├─ leads_hpinquirylead
       ├─ leads_walkinlead
       ├─ leads_carviewlead ★
       ├─ leads_referrallead ★
       └─ leads_emaillead ★

[sales_assessment]  ← 中心エンティティ（案件ID）
  ├─ leads_reservation (FK)
  ├─ customers_customer (FK)
  ├─ vehicles_vehicle (FK)
  ├─ employees_employee (FK)
  │
  ├─ [sales_purchasecontract] (1:1)
  │    ├─ [sales_document] (1:N)
  │    ├─ [sales_identitydocument] (1:N)
  │    ├─ [sales_ownershipreleasemgmt] (1:1) ★
  │    └─ [sales_advancepaymentrecord] (1:N) ★
  │
  ├─ [sales_assessmentcheckitem] (1:N)
  │
  ├─ [operations_vehicleretrieval] (1:1)
  │    └─ [operations_accessorycheck] (1:N)
  │
  ├─ [operations_listingpreparation] (1:1)
  │    ├─ [operations_preparationworkdetail] (1:N)
  │    ├─ [operations_maintenancerecord] (1:N)
  │    │    └─ [operations_maintenancedetail] (1:N)
  │    └─ [operations_incidentalcost] (1:N)
  │
  ├─ [operations_transport] (1:N)
  │
  ├─ [marketplace_auctionlisting] (1:N)
  │    └─ [marketplace_auctionnosalerecord] (1:N)
  │
  ├─ [marketplace_weblisting] (1:N)
  │
  ├─ [finance_paymentincomerecord] (1:1)
  ├─ [finance_paymentrecord] (1:1)
  │
  └─ [common_contacthistory] (1:N)
```

---

## 付録：新規追加が必要なDjangoアプリ

現在の `ARCHITECTURE.md` に存在しないアプリで、本設計で新規追加が必要なもの:

| アプリ名 | 対応する業務 |
|---|---|
| `operations` | 引き取り・出品準備・陸送 |
| `marketplace` | オークション・Web掲載 |
| `finance` | 入金・支払い |
| `common` | 取引・連絡履歴 |

既存の `leads` / `sales` / `vehicles` / `customers` / `employees` アプリは本設計に合わせてモデルを大幅に追加・修正する必要がある。
