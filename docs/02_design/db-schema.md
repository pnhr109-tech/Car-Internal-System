# DB設計書

> 生成基準：`leads/models.py` / `accounts/models.py` の現行実装  
> フレームワーク：Django 5.0.1 / DB：MySQL 8.0  
> 最終更新：2026-04-24

---

## 目次

1. [テーブル一覧](#1-テーブル一覧)
2. [accounts アプリ](#2-accounts-アプリ)
   - [stores](#21-stores--店舗マスタ)
   - [user_profiles](#22-user_profiles--ユーザープロファイル)
   - [login_activities](#23-login_activities--ログイン勤怠)
3. [leads アプリ](#3-leads-アプリ)
   - [gmail_messages](#31-gmail_messages--gmailメッセージ)
   - [customers](#32-customers--顧客)
   - [customer_bank_accounts](#33-customer_bank_accounts--顧客口座情報)
   - [vehicles](#34-vehicles--車両)
   - [vehicle_images](#35-vehicle_images--車両画像)
   - [number_sequences](#36-number_sequences--連番管理)
   - [car_assessment_requests](#37-car_assessment_requests--査定申込)
   - [assessments](#38-assessments--査定商談)
   - [assessment_check_items](#39-assessment_check_items--査定チェック項目)
   - [document_type_masters](#310-document_type_masters--書類種別マスタ)
   - [purchase_contracts](#311-purchase_contracts--買取契約)
   - [documents](#312-documents--書類後日品)
   - [identity_documents](#313-identity_documents--本人確認書類)
   - [ownership_releases](#314-ownership_releases--所有権解除管理)
   - [advance_payments](#315-advance_payments--先払い入金)
   - [contact_histories](#316-contact_histories--取引連絡履歴)
4. [ER図（概要）](#4-er図概要)
5. [業務フロー別テーブル対応](#5-業務フロー別テーブル対応)

---

## 1. テーブル一覧

| # | テーブル名 | モデル | アプリ | 概要 |
|---|---|---|---|---|
| 1 | `stores` | Store | accounts | 店舗マスタ |
| 2 | `user_profiles` | UserProfile | accounts | ユーザー権限・所属店舗 |
| 3 | `login_activities` | LoginActivity | accounts | ログイン勤怠管理 |
| 4 | `gmail_messages` | GmailMessage | leads | Gmail取り込みメッセージ |
| 5 | `customers` | Customer | leads | 顧客マスタ |
| 6 | `customer_bank_accounts` | CustomerBankAccount | leads | 顧客口座情報 |
| 7 | `vehicles` | Vehicle | leads | 車両マスタ |
| 8 | `vehicle_images` | VehicleImage | leads | 車両画像 |
| 9 | `number_sequences` | NumberSequence | leads | 申込番号等の連番管理 |
| 10 | `car_assessment_requests` | CarAssessmentRequest | leads | 査定申込（全チャネル統合） |
| 11 | `assessments` | Assessment | leads | 査定・商談 |
| 12 | `assessment_check_items` | AssessmentCheckItem | leads | 査定チェック項目 |
| 13 | `document_type_masters` | DocumentTypeMaster | leads | 書類種別マスタ（将来実装） |
| 14 | `purchase_contracts` | PurchaseContract | leads | 買取契約 |
| 15 | `documents` | Document | leads | 書類・後日品（将来実装） |
| 16 | `identity_documents` | IdentityDocument | leads | 本人確認書類（将来実装） |
| 17 | `ownership_releases` | OwnershipRelease | leads | 所有権解除管理 |
| 18 | `advance_payments` | AdvancePayment | leads | 先払い入金記録 |
| 19 | `contact_histories` | ContactHistory | leads | 取引・連絡履歴 |

> Django標準テーブル（`auth_user`, `auth_group`, `django_session` 等）は省略。

---

## 2. accounts アプリ

### 2.1 `stores` — 店舗マスタ

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| code | VARCHAR(20) UNIQUE | NO | | 店舗コード（TSUKUBA / MITO / OYAMA / UTSUNOMIYA / CC / SUPPORT / HQ） |
| name | VARCHAR(50) | NO | | 店舗名 |
| is_active | TINYINT(1) | NO | 1 | 有効フラグ |

---

### 2.2 `user_profiles` — ユーザープロファイル

Django標準の `auth_user` と 1:1 で紐づく。権限・所属店舗を管理する。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| user_id | INT FK→auth_user | NO | | ユーザー（1:1） |
| store_id | INT FK→stores | YES | NULL | 所属店舗（全権限ロールはNULL） |
| role | VARCHAR(20) | NO | `general` | ロール（general / sub_leader / manager / superuser） |
| employee_number | VARCHAR(20) | YES | `''` | 社員番号 |
| is_active_employee | TINYINT(1) | NO | 1 | 在籍中フラグ |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |

**ロール権限早見表**

| ロール | can_approve | can_edit_numbers | has_global_access |
|---|---|---|---|
| general（一般） | ✗ | ✗ | ✗ |
| sub_leader（次席） | ✓ | ✓ | ✗ |
| manager（マネージャー） | ✓ | ✓ | ✗ |
| superuser（全権限） | ✓ | ✓ | ✓ |
| HQ所属（本社業務） | ✗ | ✗ | ✓ |

---

### 2.3 `login_activities` — ログイン勤怠

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| user_id | INT FK→auth_user | NO | | ユーザー |
| work_date | DATE | NO | | 勤務日 |
| login_at | DATETIME | NO | | 出勤時刻 |
| logout_at | DATETIME | YES | NULL | 退勤時刻 |
| work_minutes | INT | NO | 0 | 勤務時間（分） |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |

**インデックス**

| 名前 | カラム |
|---|---|
| idx_login_act_user_date | (user_id, work_date) |
| idx_login_act_user_out | (user_id, logout_at) |

---

## 3. leads アプリ

### 3.1 `gmail_messages` — Gmailメッセージ

Gmail API Push通知で受信したメッセージを保存。査定申込取り込みの元データ。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| message_id | VARCHAR(255) UNIQUE | NO | | GmailメッセージID |
| thread_id | VARCHAR(255) | NO | | スレッドID |
| from_address | VARCHAR(255) | NO | | 送信元メールアドレス |
| to_address | VARCHAR(255) | NO | | 宛先メールアドレス |
| subject | VARCHAR(500) | NO | | 件名 |
| received_at | DATETIME | NO | | 受信日時 |
| created_at | DATETIME | NO | | 取り込み日時 |
| snippet | TEXT | YES | NULL | スニペット |
| body_text | TEXT | YES | NULL | 本文（テキスト） |
| body_html | TEXT | YES | NULL | 本文（HTML） |
| raw_json | JSON | YES | NULL | Gmail APIレスポンス全体 |

**インデックス**

| 名前 | カラム |
|---|---|
| idx_received_at | (-received_at) |

---

### 3.2 `customers` — 顧客

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| name | VARCHAR(100) | NO | | 氏名 |
| furigana | VARCHAR(100) | YES | `''` | フリガナ |
| phone_number | VARCHAR(20) | NO | | 電話番号 |
| email | VARCHAR(255) | YES | `''` | メールアドレス |
| postal_code | VARCHAR(10) | YES | `''` | 郵便番号 |
| address | VARCHAR(255) | YES | `''` | 住所 |
| age | SMALLINT | YES | NULL | 年齢 |
| birth_date | DATE | YES | NULL | 生年月日 |
| occupation | VARCHAR(100) | YES | `''` | 職業 |
| gender | VARCHAR(10) | YES | `''` | 性別 |
| family_structure | VARCHAR(100) | YES | `''` | 家族構成 |
| license_number | VARCHAR(20) | YES | `''` | 免許証番号 |
| is_taxable_business | TINYINT(1) | YES | NULL | 課税事業者フラグ |
| invoice_registration_number | VARCHAR(50) | YES | `''` | インボイス登録番号 |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |
| updated_by_id | INT FK→auth_user | YES | NULL | 更新者 |

**インデックス**

| 名前 | カラム |
|---|---|
| idx_cust_name | (name) |
| idx_cust_phone | (phone_number) |

---

### 3.3 `customer_bank_accounts` — 顧客口座情報

顧客に対して複数口座を登録可能。`is_primary=True` の口座が振込先として使用される。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| customer_id | INT FK→customers | NO | | 顧客 |
| bank_institution_type | VARCHAR(20) | NO | `bank` | 金融機関種別（bank / shinkin / nokyo / yucho） |
| bank_name | VARCHAR(100) | NO | | 銀行名 |
| branch_name | VARCHAR(100) | NO | | 支店名 |
| account_type | VARCHAR(10) | NO | | 口座種別（普通 / 当座） |
| account_number | VARCHAR(20) | NO | | 口座番号 |
| account_holder | VARCHAR(100) | NO | | 口座名義（カナ） |
| is_primary | TINYINT(1) | NO | 0 | 優先口座フラグ |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |
| updated_by_id | INT FK→auth_user | YES | NULL | 更新者 |

---

### 3.4 `vehicles` — 車両

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| maker | VARCHAR(100) | NO | | メーカー |
| car_model | VARCHAR(100) | NO | | 車種 |
| year | VARCHAR(10) | NO | | 年式 |
| mileage | VARCHAR(20) | NO | | 走行距離 |
| grade | VARCHAR(100) | YES | `''` | グレード |
| color | VARCHAR(50) | YES | `''` | カラー |
| displacement | VARCHAR(20) | YES | `''` | 排気量 |
| remarks | TEXT | YES | `''` | 備考 |
| model_type | VARCHAR(50) | YES | `''` | 型式 |
| fuel_type | VARCHAR(20) | YES | `''` | 燃料種別（gasoline / diesel / hybrid / phev / ev / lpg / other） |
| chassis_number | VARCHAR(50) | YES | `''` | 車台番号 |
| first_registration_date | DATE | YES | NULL | 初年度登録年月 |
| repair_history_flag | TINYINT(1) | YES | NULL | 修復歴（NULL=未回答） |
| inspection_expiry | DATE | YES | NULL | 車検有効期限 |
| transmission_type | VARCHAR(10) | YES | `''` | ミッション種別（AT / MT / CVT / その他） |
| registration_number | VARCHAR(20) | YES | `''` | 登録番号（ナンバー） |
| passenger_count | VARCHAR(5) | YES | `''` | 乗車定員 |
| body_type | VARCHAR(50) | YES | `''` | ボディタイプ |
| drive_type | VARCHAR(10) | YES | `''` | 駆動方式 |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |
| updated_by_id | INT FK→auth_user | YES | NULL | 更新者 |

---

### 3.5 `vehicle_images` — 車両画像

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| vehicle_id | INT FK→vehicles | NO | | 車両 |
| image | VARCHAR(255) | NO | | 画像ファイルパス（upload_to: vehicle_images/） |
| part_type | VARCHAR(20) | YES | `''` | パーツ種別（外装 / 内装 / エンジン / タイヤ / その他） |
| taken_at | DATETIME | YES | NULL | 撮影日時 |
| created_at | DATETIME | NO | | 登録日時 |

---

### 3.6 `number_sequences` — 連番管理

申込番号・契約番号など各種連番の最終値を管理する汎用テーブル。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| sequence_type | VARCHAR(50) | NO | | 連番種別（例: `application_number`） |
| key | VARCHAR(100) | NO | | 区切りキー（例: `NAVIKURU-20260410`） |
| last_seq | INT | NO | 0 | 最終発行連番 |

**制約**

- UNIQUE (sequence_type, key)

---

### 3.7 `car_assessment_requests` — 査定申込

全チャネル（ナビクル・メール・来店等）の申込を統合管理する中心テーブル。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| application_number | VARCHAR(50) UNIQUE | NO | | 申込番号（例: N-20260410-0001） |
| application_datetime | DATETIME | NO | | 申込日時 |
| channel_type | VARCHAR(20) | NO | `NAVIKURU` | チャネル（NAVIKURU / MYCAR_SCOUT / CARVIEW / HP / WALK_IN / REFERRAL / EMAIL / MANUAL） |
| customer_name | VARCHAR(100) | NO | | 申込者氏名 |
| phone_number | VARCHAR(20) | NO | | 電話番号 |
| email | VARCHAR(255) | YES | `''` | メールアドレス |
| postal_code | VARCHAR(10) | YES | `''` | 郵便番号 |
| address | VARCHAR(255) | YES | `''` | 住所 |
| maker | VARCHAR(100) | YES | `''` | メーカー名（申込時入力値） |
| car_model | VARCHAR(100) | YES | `''` | 車種名（申込時入力値） |
| year | VARCHAR(100) | YES | `''` | 年式（申込時入力値） |
| mileage | VARCHAR(100) | YES | `''` | 走行距離（申込時入力値） |
| desired_sale_timing | VARCHAR(100) | YES | `''` | 希望売却時期 |
| follow_status | VARCHAR(30) | NO | `未対応` | 対応ステータス（未対応 / 不通 / 即ぷ / 再コール予定 / 商談予定 / 商談昇格済 / 成約 / 見送り） |
| sales_owner_name | VARCHAR(150) | YES | `''` | 担当営業名 |
| sales_assigned_at | DATETIME | YES | NULL | 担当確定日時 |
| call_count | INT | NO | 0 | 通話数 |
| sales_note | TEXT | YES | `''` | 対応コメント |
| status_updated_at | DATETIME | YES | NULL | ステータス更新日時 |
| status_updated_by | VARCHAR(150) | YES | `''` | ステータス更新者名 |
| external_service_id | VARCHAR(100) | YES | `''` | 外部サービスID（ナビクル等の申込番号） |
| external_status | VARCHAR(50) | YES | `''` | 外部ステータス |
| scraped_at | DATETIME | YES | NULL | 最終スクレイピング日時 |
| referral_name | VARCHAR(100) | YES | `''` | 紹介者名 |
| reservation_datetime | DATETIME | YES | NULL | 査定予約日時 |
| cancel_reason | VARCHAR(255) | YES | `''` | キャンセル理由 |
| customer_id | INT FK→customers | YES | NULL | 紐づき顧客（商談昇格後に設定） |
| vehicle_id | INT FK→vehicles | YES | NULL | 紐づき車両（商談昇格後に設定） |
| assigned_to_id | INT FK→auth_user | YES | NULL | 担当者 |
| gmail_message_id | INT FK→gmail_messages | YES | NULL | 元メッセージ |
| created_at | DATETIME | NO | | 取り込み日時 |
| updated_at | DATETIME | NO | | 更新日時 |

**インデックス**

| 名前 | カラム |
|---|---|
| idx_app_datetime | (-application_datetime) |
| idx_customer_name | (customer_name) |
| idx_phone_number | (phone_number) |
| idx_channel_external_id | (channel_type, external_service_id) |

---

### 3.8 `assessments` — 査定・商談

`car_assessment_requests` から昇格して生成される。商談〜承認フェーズを管理。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| assessment_request_id | INT FK→car_assessment_requests (1:1) | NO | | 元査定申込 |
| customer_id | INT FK→customers | NO | | 顧客 |
| vehicle_id | INT FK→vehicles | NO | | 車両 |
| assigned_to_id | INT FK→auth_user | NO | | 担当者 |
| status | VARCHAR(20) | NO | `in_progress` | ステータス（in_progress / contracted / lost / pre_cancel / managed） |
| management_status | VARCHAR(20) | YES | `''` | 管理方針（contract / lost / re_approach） |
| assessment_datetime | DATETIME | YES | NULL | 査定日時 |
| assessment_price | DECIMAL(12,0) | YES | NULL | 査定額 |
| market_price | DECIMAL(12,0) | YES | NULL | 市場相場価格 |
| overall_rating | DECIMAL(3,1) | YES | NULL | 総合評価（1〜5、0.5刻み） |
| cancel_reason | VARCHAR(255) | YES | `''` | キャンセル理由 |
| cancelled_at | DATETIME | YES | NULL | キャンセル日時 |
| approved_by_id | INT FK→auth_user | YES | NULL | 承認者 |
| approved_at | DATETIME | YES | NULL | 承認日時 |
| remarks | TEXT | YES | `''` | 備考 |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |
| updated_by_id | INT FK→auth_user | YES | NULL | 更新者 |

**インデックス**

| 名前 | カラム |
|---|---|
| idx_assessment_status | (status) |
| idx_assessment_user_status | (assigned_to_id, status) |

---

### 3.9 `assessment_check_items` — 査定チェック項目

査定時に確認した傷・修復歴・タイヤ状態などのチェック記録。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| assessment_id | INT FK→assessments | NO | | 査定 |
| check_type | VARCHAR(20) | NO | | チェック種別（scratch / repair / interior / tire / other） |
| description | TEXT | YES | `''` | 詳細説明 |
| created_at | DATETIME | NO | | 作成日時 |

---

### 3.10 `document_type_masters` — 書類種別マスタ

> ⚠️ 将来実装予定。現在DBレコードなし。

書類管理機能（[3.12](#312-documents--書類後日品)）で使用する書類種別のマスタ。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| name | VARCHAR(100) | NO | | 書類種別名 |
| required_flag | TINYINT(1) | NO | 0 | 必須フラグ |
| description | TEXT | YES | `''` | 説明 |

---

### 3.11 `purchase_contracts` — 買取契約

`assessments` と 1:1 で紐づく契約情報。契約書PDF出力の元データでもある。

#### 基本情報・金額

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| assessment_id | INT FK→assessments (1:1) | NO | | 査定 |
| customer_id | INT FK→customers | NO | | 顧客 |
| vehicle_id | INT FK→vehicles | NO | | 車両 |
| assigned_to_id | INT FK→auth_user | NO | | 担当者 |
| status | VARCHAR(20) | NO | `pending` | ステータス（pending / contracted / cancelled） |
| contract_date | DATE | NO | | 契約日 |
| purchase_price_excl_tax | DECIMAL(12,0) | NO | | 買取確定価格（税抜） |
| tax_amount | DECIMAL(12,0) | NO | | 消費税額 |
| purchase_price_incl_tax | DECIMAL(12,0) | NO | | 買取確定価格（税込） |
| recycle_amount | DECIMAL(10,0) | YES | NULL | リサイクル券金額 |
| payment_scheduled_date | DATE | YES | NULL | 支払い予定日 |
| auction_scheduled_date | DATE | YES | NULL | オークション出品予定日 |
| vehicle_handover_date | DATE | YES | NULL | 車両引渡日 |
| document_handover_date | DATE | YES | NULL | 書類引渡日 |

#### 契約オプション

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| repair_flag | TINYINT(1) | NO | 0 | 加修フラグ |
| repair_notes | TEXT | YES | `''` | 加修内容 |
| ownership_release_flag | TINYINT(1) | NO | 0 | 所有権解除フラグ |
| amount_correction_flag | TINYINT(1) | NO | 0 | 金額訂正フラグ |
| corrected_price | DECIMAL(12,0) | YES | NULL | 訂正後買取価格 |
| correction_approved_by_id | INT FK→auth_user | YES | NULL | 金額訂正承認者（社長） |
| correction_approved_at | DATETIME | YES | NULL | 金額訂正承認日時 |
| cancel_reason | VARCHAR(255) | YES | `''` | キャンセル理由 |
| cancelled_at | DATETIME | YES | NULL | 破棄日時 |

#### 車両状況・事業者登録申告（契約書記載）

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| meter_tampering | TINYINT(1) | YES | NULL | メーター戻し・改ざん等（NULL=未回答） |
| flood_hail_damage | TINYINT(1) | YES | NULL | 冠水車・雹害 |
| malfunction | TINYINT(1) | YES | NULL | 故障箇所 |
| parking_violation | TINYINT(1) | YES | NULL | 駐車違反放置反則金未納 |
| automobile_tax_unpaid | TINYINT(1) | YES | NULL | 自動車税未納 |
| qualified_invoice_registered | TINYINT(1) | YES | NULL | 適格請求書発行事業者登録 |
| invoice_registration_number | VARCHAR(50) | YES | `''` | 適格請求書登録番号 |

#### 必要書類（通数・受取確認）

車両引渡に必要な書類の通数を契約時に設定し、受取済フラグで進捗を管理する。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| required_inkan_count | SMALLINT | NO | 0 | 印鑑証明（必要通数） |
| required_juminhyo_count | SMALLINT | NO | 0 | 住民票（必要通数） |
| required_jotohyo_count | SMALLINT | NO | 0 | 除票（必要通数） |
| required_ininjyo_count | SMALLINT | NO | 0 | 委任状（必要通数） |
| required_jotosho_count | SMALLINT | NO | 0 | 譲渡書（必要通数） |
| required_kanpu_count | SMALLINT | NO | 0 | 還付（必要通数） |
| inkan_received | TINYINT(1) | NO | 0 | 印鑑証明 受取済 |
| juminhyo_received | TINYINT(1) | NO | 0 | 住民票 受取済 |
| jotohyo_received | TINYINT(1) | NO | 0 | 除票 受取済 |
| ininjyo_received | TINYINT(1) | NO | 0 | 委任状 受取済 |
| jotosho_received | TINYINT(1) | NO | 0 | 譲渡書 受取済 |
| kanpu_received | TINYINT(1) | NO | 0 | 還付 受取済 |

#### 担当者・承認

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| manager1_id | INT FK→auth_user | YES | NULL | 責任者1 |
| manager2_id | INT FK→auth_user | YES | NULL | 責任者2 |
| approved_by_id | INT FK→auth_user | YES | NULL | 承認者 |
| approved_at | DATETIME | YES | NULL | 承認日時 |
| remarks | TEXT | YES | `''` | 備考 |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |
| updated_by_id | INT FK→auth_user | YES | NULL | 更新者 |

---

### 3.12 `documents` — 書類・後日品

> ⚠️ 将来実装予定。書類のファイル保存・ステータス管理が必要になった際に使用する。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| assessment_id | INT FK→assessments | YES | NULL | 査定 |
| contract_id | INT FK→purchase_contracts | YES | NULL | 買取契約 |
| document_type_id | INT FK→document_type_masters | NO | | 書類種別 |
| status | VARCHAR(20) | NO | `not_created` | ステータス（not_created / in_progress / created / waiting / received / confirmed） |
| issue_date | DATE | YES | NULL | 発行日 |
| received_date | DATE | YES | NULL | 受領日 |
| file | VARCHAR(255) | YES | `''` | ファイルパス（upload_to: documents/） |
| later_send_status | VARCHAR(10) | NO | `not_sent` | 後日品送付状態（not_sent / sent） |
| remarks | TEXT | YES | `''` | 備考 |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |
| updated_by_id | INT FK→auth_user | YES | NULL | 更新者 |

---

### 3.13 `identity_documents` — 本人確認書類

> ⚠️ 将来実装予定。本人確認書類（免許証・マイナンバーカード等）の画像保存用。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| customer_id | INT FK→customers | NO | | 顧客 |
| contract_id | INT FK→purchase_contracts | NO | | 買取契約 |
| doc_type | VARCHAR(30) | NO | | 書類種別（driving_license / passport / my_number / other） |
| file | VARCHAR(255) | YES | `''` | ファイルパス（upload_to: identity_documents/） |
| verified_at | DATETIME | YES | NULL | 確認日時 |
| verified_by_id | INT FK→auth_user | YES | NULL | 確認者 |
| remarks | TEXT | YES | `''` | 備考 |
| created_at | DATETIME | NO | | 作成日時 |

---

### 3.14 `ownership_releases` — 所有権解除管理

`ownership_release_flag=True` の契約に対して 1:1 で紐づく。ローン残債のある車両の所有権解除プロセスを管理する。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| contract_id | INT FK→purchase_contracts (1:1) | NO | | 買取契約 |
| pattern | VARCHAR(1) | NO | | パターン（A: ディーラー経由 / B: 自己返済） |
| status | VARCHAR(30) | NO | `pending` | ステータス（pending / inquiry_in_progress / docs_sent / debt_transferred / docs_returned） |
| inquiry_status | VARCHAR(100) | YES | `''` | 残債照会ステータス（フリーテキスト） |
| dealer_doc_sent_date | DATE | YES | NULL | ディーラーへの書類送付日 |
| debt_transfer_date | DATE | YES | NULL | 残債振込日 |
| dealer_doc_returned_date | DATE | YES | NULL | ディーラーからの書類返却日 |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |

**ステータス遷移**

```
pending → inquiry_in_progress → docs_sent → debt_transferred → docs_returned
```

---

### 3.15 `advance_payments` — 先払い入金

1契約に対して複数の先払い入金を記録できる。社長稟議による承認が必要。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| contract_id | INT FK→purchase_contracts | NO | | 買取契約 |
| expected_amount | DECIMAL(12,0) | NO | | 入金予定額 |
| payment_date | DATE | YES | NULL | 入金日 |
| status | VARCHAR(10) | NO | `unpaid` | ステータス（unpaid / paid） |
| approved_by_id | INT FK→auth_user | YES | NULL | 承認者（社長）。NULL=未承認 |
| created_at | DATETIME | NO | | 作成日時 |
| updated_at | DATETIME | NO | | 更新日時 |

---

### 3.16 `contact_histories` — 取引・連絡履歴

査定申込に紐づく電話・メール・訪問等のすべての接触履歴を記録する。

| カラム | 型 | NULL | デフォルト | 説明 |
|---|---|---|---|---|
| id | INT PK | NO | AUTO | |
| assessment_request_id | INT FK→car_assessment_requests | NO | | 査定申込 |
| customer_id | INT FK→customers | YES | NULL | 顧客 |
| recorded_by_id | INT FK→auth_user | NO | | 記録者 |
| contact_method | VARCHAR(10) | NO | | 連絡方法（phone / email / sms / visit / other） |
| contacted_at | DATETIME | NO | | 連絡日時 |
| content | TEXT | NO | | 内容 |
| created_at | DATETIME | NO | | 作成日時 |

---

## 4. ER図（概要）

```
auth_user ──────────────────────────────────────────────────────────────────┐
    │                                                                         │
    ├── user_profiles (1:1) → stores                                          │
    └── login_activities (N)                                                  │
                                                                              │
gmail_messages                                                                │
    └── car_assessment_requests (N)                                           │
            │   assigned_to_id ────────────────────────────────────────────> │
            │                                                                 │
            ├── contact_histories (N)                                         │
            │                                                                 │
            └── assessments (1:1)                                             │
                    │   customer_id ──> customers                             │
                    │   vehicle_id  ──> vehicles → vehicle_images (N)        │
                    │   assigned_to_id / approved_by_id ──────────────────-> │
                    │                                                         │
                    ├── assessment_check_items (N)                            │
                    │                                                         │
                    └── purchase_contracts (1:1)                              │
                            │   manager1/2/approved_by ───────────────────-> │
                            │   correction_approved_by ───────────────────-> │
                            │                                                 │
                            ├── ownership_releases (1:1)                      │
                            ├── advance_payments (N)  approved_by ─────────> │
                            ├── documents (N) → document_type_masters         │
                            └── identity_documents (N)  verified_by ───────> │

customers                                                                     │
    ├── customer_bank_accounts (N)  updated_by ──────────────────────────-> │
    ├── identity_documents (N)                                                │
    └── contact_histories (N)                                                 │
                                                                              │
number_sequences  ← 独立テーブル（連番管理）                                      │
```

---

## 5. 業務フロー別テーブル対応

| フェーズ | 主テーブル | 補助テーブル |
|---|---|---|
| ① 申込受付 | `car_assessment_requests` | `gmail_messages`, `number_sequences` |
| ② フォロー・アポ | `car_assessment_requests` | `contact_histories` |
| ③ 商談・査定 | `assessments` | `assessment_check_items`, `vehicles`, `vehicle_images` |
| ④ 成約・稟議 | `assessments` | `customers`, `customer_bank_accounts` |
| ⑤ 契約作成 | `purchase_contracts` | — |
| ⑥ 所有権解除 | `ownership_releases` | `purchase_contracts` |
| ⑦ 先払い入金 | `advance_payments` | `purchase_contracts` |
| ⑧ 必要書類受取確認 | `purchase_contracts`（required_*/\*_received フィールド） | — |
| ⑨ 書類ファイル管理（将来） | `documents` | `document_type_masters` |
| ⑩ 本人確認（将来） | `identity_documents` | `customers` |
| ⑪ 勤怠管理 | `login_activities` | `auth_user` |
