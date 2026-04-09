# DB設計 — フェーズ1（アポイント〜契約）

## 設計方針

- **既存の `CarAssessmentRequest` は残す**（Gmail連携が動いているため壊さない）
- 新たに `Customer` / `Vehicle` を独立テーブル化し、FK で紐付ける
- 査定申込 → 査定 → 契約 を縦に繋ぐ `Assessment`（査定）テーブルを中核に置く
- 担当者は Django `auth.User` を直接参照
- 全テーブル共通で `created_at` / `updated_at` / `updated_by` を持つ

---

## ER図（テキスト）

```
auth.User
  │
  ├─── AssessmentRequest（査定申込）
  │         │channel_type（チャネル種別）
  │         │ナビクル / マイカースカウト / HP / 来店 / カービュー / 紹介 / メール / 手動
  │         │
  │         ├── Customer（顧客）
  │         │       └── CustomerBankAccount（顧客口座）
  │         │
  │         └── Vehicle（車両）
  │                 └── VehicleImage（車両画像）
  │
  └─── Assessment（査定）  ← AssessmentRequest の商談昇格で生成
            │
            ├── AssessmentCheckItem（査定チェック項目）
            │
            └── PurchaseContract（買取契約）  ← 成約で生成
                      ├── Document（書類）
                      │       └── DocumentTypeMaster（書類種別マスタ）
                      ├── IdentityDocument（本人確認書類）
                      ├── OwnershipRelease（所有権解除管理）★
                      └── AdvancePayment（先払い入金記録）★

ContactHistory（取引・連絡履歴）── AssessmentRequest に紐付く（全ステップ共通）
```

---

## テーブル定義

### 1. customers（顧客）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| name | VARCHAR(100) | NO | 氏名 |
| phone_number | VARCHAR(20) | NO | 電話番号 |
| email | VARCHAR(255) | YES | メールアドレス |
| postal_code | VARCHAR(10) | YES | 郵便番号 |
| address | VARCHAR(255) | YES | 住所 |
| age | SMALLINT | YES | 年齢 |
| occupation | VARCHAR(100) | YES | 職業 |
| gender | VARCHAR(10) | YES | 性別（男性/女性/その他） |
| family_structure | VARCHAR(100) | YES | 家族構成 |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |
| updated_by_id | BIGINT FK→User | YES | |

**インデックス:** `name`, `phone_number`

---

### 2. customer_bank_accounts（顧客口座情報）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| customer_id | BIGINT FK→customers | NO | |
| bank_name | VARCHAR(100) | NO | 銀行名 |
| branch_name | VARCHAR(100) | NO | 支店名 |
| account_type | VARCHAR(10) | NO | 口座種別（普通/当座） |
| account_number | VARCHAR(20) | NO | 口座番号 |
| account_holder | VARCHAR(100) | NO | 口座名義 |
| is_primary | BOOLEAN | NO | 優先口座フラグ（default: False） |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |
| updated_by_id | BIGINT FK→User | YES | |

---

### 3. vehicles（車両）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| maker | VARCHAR(100) | NO | メーカー |
| car_model | VARCHAR(100) | NO | 車種 |
| year | VARCHAR(10) | NO | 年式 |
| mileage | VARCHAR(20) | NO | 走行距離 |
| grade | VARCHAR(100) | YES | グレード |
| color | VARCHAR(50) | YES | カラー |
| displacement | VARCHAR(20) | YES | 排気量 |
| chassis_number | VARCHAR(50) | YES | 車台番号（②商談で追加） |
| first_registration_date | DATE | YES | 初年度登録年月（②商談で追加） |
| repair_history_flag | BOOLEAN | YES | 修復歴フラグ（②商談で追加） |
| inspection_expiry | DATE | YES | 車検有効期限（②商談で追加） |
| transmission_type | VARCHAR(10) | YES | ミッション種別（AT/MT/CVT）（②商談で追加） |
| registration_number | VARCHAR(20) | YES | 登録番号（ナンバー）（②商談で追加） |
| remarks | TEXT | YES | 備考 |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |
| updated_by_id | BIGINT FK→User | YES | |

---

### 4. vehicle_images（車両画像）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| vehicle_id | BIGINT FK→vehicles | NO | |
| image_path | VARCHAR(500) | NO | 画像ファイルパス |
| part_type | VARCHAR(50) | YES | パーツ種別（外装/内装/エンジン等） |
| taken_at | DATETIME | YES | 撮影日時 |
| created_at | DATETIME | NO | |

---

### 5. assessment_requests（査定申込）※ 既存 CarAssessmentRequest を拡張

> 既存テーブルに FK カラムを追加するマイグレーションで対応。
> `application_number` / `gmail_message` などの既存カラムはそのまま保持。

**追加カラム（ALTER TABLE）:**

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| channel_type | VARCHAR(30) | NO | チャネル種別（下記CHOICES） |
| customer_id | BIGINT FK→customers | YES | 顧客（登録後に紐付け） |
| vehicle_id | BIGINT FK→vehicles | YES | 車両（登録後に紐付け） |
| external_service_id | VARCHAR(100) | YES | 外部サービス側のID |
| referral_name | VARCHAR(100) | YES | 紹介者名（チャネル=紹介の場合） |
| reservation_datetime | DATETIME | YES | 査定予約日時 |
| cancel_reason | VARCHAR(255) | YES | キャンセル理由 |

**channel_type の選択肢:**
```
NAVIKURU       = ナビクル
MYCAR_SCOUT    = マイカースカウト
CARVIEW        = カービュー
HP             = ホームページ
WALK_IN        = 来店
REFERRAL       = 紹介
EMAIL          = メール
MANUAL         = 手動入力
```

**既存 follow_status を拡張（フェーズ1対応）:**
```
未対応 / 不通 / 再コール予定 / 商談確定 / 成約 / 見送り（既存）
→ 「商談昇格済」を追加（Assessmentレコード生成後）
```

---

### 6. assessments（査定）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| assessment_request_id | BIGINT FK→assessment_requests | NO | 元の査定申込 |
| customer_id | BIGINT FK→customers | NO | |
| vehicle_id | BIGINT FK→vehicles | NO | |
| assigned_to_id | BIGINT FK→User | NO | 担当者 |
| assessment_datetime | DATETIME | NO | 査定日時 |
| assessment_price | DECIMAL(12,0) | YES | 査定額 |
| market_price | DECIMAL(12,0) | YES | 市場相場価格 |
| overall_rating | SMALLINT | YES | 総合評価（1〜5） |
| status | VARCHAR(10) | NO | 成約/不成約/管理（default:査定中） |
| management_status | VARCHAR(20) | YES | 管理時の方針（契約/没/再アプローチ） |
| cancel_reason | VARCHAR(255) | YES | キャンセル理由 |
| cancelled_at | DATETIME | YES | キャンセル日時 |
| approved_by_id | BIGINT FK→User | YES | 承認者 |
| approved_at | DATETIME | YES | 承認日時 |
| remarks | TEXT | YES | 備考 |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |
| updated_by_id | BIGINT FK→User | YES | |

**インデックス:** `assessment_request_id`, `assigned_to_id`, `status`

---

### 7. assessment_check_items（査定チェック項目）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| assessment_id | BIGINT FK→assessments | NO | |
| check_type | VARCHAR(30) | NO | 種別（傷/修復歴/内装/タイヤ/その他） |
| description | TEXT | YES | 詳細説明 |
| created_at | DATETIME | NO | |

---

### 8. purchase_contracts（買取契約）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| assessment_id | BIGINT FK→assessments | NO | |
| customer_id | BIGINT FK→customers | NO | |
| vehicle_id | BIGINT FK→vehicles | NO | |
| assigned_to_id | BIGINT FK→User | NO | 担当者 |
| contract_date | DATE | NO | 契約日 |
| purchase_price_excl_tax | DECIMAL(12,0) | NO | 買取確定価格（税抜） |
| tax_amount | DECIMAL(12,0) | NO | 消費税額 |
| purchase_price_incl_tax | DECIMAL(12,0) | NO | 買取確定価格（税込） |
| payment_scheduled_date | DATE | YES | 支払い予定日（仮） |
| auction_scheduled_date | DATE | YES | オークション出品予定日 |
| status | VARCHAR(10) | NO | 未契約/契約済/破棄（default:未契約） |
| cancel_reason | VARCHAR(255) | YES | キャンセル理由 |
| cancelled_at | DATETIME | YES | キャンセル日時 |
| amount_correction_flag | BOOLEAN | NO | 金額訂正フラグ（default:False） |
| corrected_price | DECIMAL(12,0) | YES | 訂正後買取価格 |
| repair_flag | BOOLEAN | NO | 加修フラグ（default:False） |
| repair_notes | TEXT | YES | 加修内容 |
| ownership_release_flag | BOOLEAN | NO | 所有権解除フラグ（default:False） |
| approved_by_id | BIGINT FK→User | YES | 承認者 |
| approved_at | DATETIME | YES | 承認日時 |
| remarks | TEXT | YES | 備考 |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |
| updated_by_id | BIGINT FK→User | YES | |

---

### 9. document_type_masters（書類種別マスタ）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| name | VARCHAR(100) | NO | 書類種別名（委任状/譲渡証明書等） |
| required_flag | BOOLEAN | NO | 必須フラグ |
| description | TEXT | YES | 説明 |

---

### 10. documents（書類・後日品）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| assessment_id | BIGINT FK→assessments | YES | |
| contract_id | BIGINT FK→purchase_contracts | YES | |
| document_type_id | BIGINT FK→document_type_masters | NO | |
| issue_date | DATE | YES | 発行日 |
| received_date | DATE | YES | 受領日 |
| status | VARCHAR(20) | NO | 未作成/作成中/作成済/受領待/受領済/確認済 |
| file_path | VARCHAR(500) | YES | ファイルパス |
| later_send_status | VARCHAR(20) | NO | 後日品送付状態（未送付/送付済） |
| remarks | TEXT | YES | 備考 |
| updated_by_id | BIGINT FK→User | YES | |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |

---

### 11. identity_documents（本人確認書類）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| customer_id | BIGINT FK→customers | NO | |
| contract_id | BIGINT FK→purchase_contracts | NO | |
| document_type | VARCHAR(50) | NO | 書類種別（運転免許証/パスポート等） |
| verified_at | DATETIME | YES | 確認日時 |
| verified_by_id | BIGINT FK→User | YES | 確認者 |
| file_path | VARCHAR(500) | YES | ファイルパス |
| remarks | TEXT | YES | 備考 |
| created_at | DATETIME | NO | |

---

### 12. ownership_releases（所有権解除管理）★

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| contract_id | BIGINT FK→purchase_contracts | NO | |
| pattern | VARCHAR(1) | NO | パターン（A:ディーラー経由 / B:自己返済） |
| inquiry_status | VARCHAR(50) | YES | 残債照会ステータス |
| dealer_doc_sent_date | DATE | YES | ディーラーへの書類送付日 |
| debt_transfer_date | DATE | YES | 残債振込日 |
| dealer_doc_returned_date | DATE | YES | ディーラーからの書類返却日 |
| status | VARCHAR(30) | NO | 未対応/残債照会中/書類送付済/残債振込済/書類返却済 |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |

---

### 13. advance_payments（先払い入金記録）★

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| contract_id | BIGINT FK→purchase_contracts | NO | |
| expected_amount | DECIMAL(12,0) | NO | 入金予定額 |
| payment_date | DATE | YES | 入金日 |
| approved_by_id | BIGINT FK→User | YES | 承認者（社長稟議） |
| status | VARCHAR(10) | NO | 未入金/入金済 |
| created_at | DATETIME | NO | |
| updated_at | DATETIME | NO | |

---

### 14. contact_histories（取引・連絡履歴）

| カラム名 | 型 | NULL | 説明 |
|---------|-----|------|------|
| id | BIGINT PK | NO | |
| assessment_request_id | BIGINT FK→assessment_requests | NO | |
| customer_id | BIGINT FK→customers | YES | |
| assigned_to_id | BIGINT FK→User | NO | 記録者 |
| contacted_at | DATETIME | NO | 連絡日時 |
| contact_method | VARCHAR(20) | NO | 連絡方法（電話/メール/SMS/対面） |
| content | TEXT | NO | 内容 |
| created_at | DATETIME | NO | |

---

## Djangoアプリ構成（案）

```
leads/          ← 既存。AssessmentRequest, GmailMessage + 新規モデルを追加
  models.py     ← Customer, Vehicle, VehicleImage, Assessment,
                   AssessmentCheckItem, PurchaseContract,
                   Document, IdentityDocument, OwnershipRelease,
                   AdvancePayment, ContactHistory, DocumentTypeMaster,
                   CustomerBankAccount を追加
```

> 将来的にモデルが増えたら `customers/` `vehicles/` アプリに切り出す。
> フェーズ1は `leads/` に集約して開発コストを抑える。

---

## マイグレーション方針

1. `customers` テーブル作成（新規）
2. `vehicles` テーブル作成（新規）
3. `car_assessment_requests` にカラム追加（`channel_type`, `customer_id`, `vehicle_id` 等）
4. 残テーブルを順次作成
5. 既存データの `customer_id` / `vehicle_id` は NULL 許容で対応し、後から手動紐付けまたはマイグレーションスクリプトで埋める
