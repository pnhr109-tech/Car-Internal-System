# Cloud SQL（MySQL）EXPLAIN確認手順

この手順は、本番前に「どのクエリが重いか」「インデックスが効いているか」を確認するためのチェックリストです。

---

## 1. 事前確認

- DB: Cloud SQL for MySQL 8.x
- 対象テーブル: `car_assessment_requests`
- 既存インデックス（モデル定義より）
  - `PRIMARY KEY (id)`
  - `UNIQUE KEY application_number`
  - `idx_app_datetime (application_datetime)`
  - `idx_customer_name (customer_name)`
  - `idx_phone_number (phone_number)`

---

## 2. 実行コマンド（基本）

```sql
EXPLAIN FORMAT=TRADITIONAL <SQL>;
```

可能なら実行計画＋実測も確認：

```sql
EXPLAIN ANALYZE <SQL>;
```

---

## 3. 優先確認クエリ（このシステム向け）

### A. 新着チェックAPI（`/api/check-new/`）

```sql
EXPLAIN FORMAT=TRADITIONAL
SELECT id, application_number, application_datetime, customer_name, maker, car_model
FROM car_assessment_requests
WHERE id > 100000
ORDER BY id DESC;
```

期待値:
- `key` が `PRIMARY`
- `type` が `range` 相当
- `rows` が過大でない

### B. 初期一覧（検索条件なし）

```sql
EXPLAIN FORMAT=TRADITIONAL
SELECT id, application_number, application_datetime, desired_sale_timing, maker, car_model,
       year, mileage, customer_name, phone_number, postal_code, address, email, created_at
FROM car_assessment_requests
ORDER BY application_datetime DESC
LIMIT 100;
```

期待値:
- `key` が `idx_app_datetime`
- `filesort` が出ない（または軽微）

### C. 申込番号の完全一致検索

```sql
EXPLAIN FORMAT=TRADITIONAL
SELECT id, application_number, application_datetime
FROM car_assessment_requests
WHERE application_number = '9060727';
```

期待値:
- `key` が `application_number`（unique index）
- `type` が `const` または `ref`

### D. 日付範囲検索

```sql
EXPLAIN FORMAT=TRADITIONAL
SELECT id, application_number, application_datetime
FROM car_assessment_requests
WHERE application_datetime >= '2026-02-01 00:00:00'
  AND application_datetime <= '2026-02-14 23:59:59'
ORDER BY application_datetime DESC
LIMIT 100;
```

期待値:
- `key` が `idx_app_datetime`
- `type` が `range`

### E. 住所の部分一致検索（要注意）

```sql
EXPLAIN FORMAT=TRADITIONAL
SELECT id, application_number, address, application_datetime
FROM car_assessment_requests
WHERE address LIKE '%東京都%'
ORDER BY application_datetime DESC
LIMIT 100;
```

注意点:
- `LIKE '%...%'` は通常B-Treeインデックスが効きにくい
- データ増加時に `rows` が増えやすい

---

## 4. 判定ポイント（最低限）

- `key = NULL` になっていないか
- `type = ALL`（全件走査）が常態化していないか
- `rows` がデータ件数に近すぎないか
- `Extra` に `Using filesort` / `Using temporary` が常時出ていないか

---

## 5. 改善アクションの目安

- 新着チェックが重い:
  - `id` 条件 + 並び順を維持（現状は `id` 利用で最適化済み）
- 初期一覧が重い:
  - `application_datetime` の並びを維持、不要列を増やさない
- 住所検索が重い:
  - 仕様が許せば前方一致（`LIKE '東京都%'`）へ変更
  - もしくは全文検索の導入を検討

---

## 6. 本番運用での実施タイミング

- 初回リリース前
- データ件数が 1万 / 5万 / 10万 を超えた時
- 画面表示やAPI応答が体感で遅くなった時

---

## 7. 記録テンプレート

- 実行日時:
- 対象クエリ:
- EXPLAIN結果（key/type/rows/Extra）:
- 判定（OK/要改善）:
- 対応内容:
