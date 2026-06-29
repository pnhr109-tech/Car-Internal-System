# Google Cloud デプロイ コスト試算

本ドキュメントは、本システムをGoogle Cloudにデプロイして運用する場合の月額コストをざっくり試算したものです。
正式な見積りではなく、構成検討のための目安として利用してください。

**作成日**: 2026年6月29日

---

## 1. 前提条件

| 項目 | 内容 |
|---|---|
| リージョン | asia-northeast1（東京） |
| 利用者数 | 日中ピーク時 約40名（社内利用、夜間は大幅減） |
| アクセスパターン | 全員が常時アクセスし続けるわけではない（同時リクエスト数は実際には数件程度と想定） |
| 案件数 | 月間 約300件（査定申込〜契約〜売却まで一連のフローが発生） |
| 案件あたりの画像・書類点数 | 約15〜20点/件（車両画像10〜15枚、必要書類スキャン3〜4点、本人確認書類1〜2点） |
| 起動方式 | 常時起動（min-instances ≥ 1、スケールトゥゼロにしない） |
| 冗長化 | なし（社内ツールのため、マルチリージョン・HA構成は想定しない） |
| 想定構成 | Cloud Run（アプリ）+ Cloud SQL for MySQL（DB）+ Cloud Storage（画像・書類）+ Compute Engine（ナビクルスクレイパー常駐ワーカー） |
| 案件取り込み方式 | ナビクルスクレイパーによるポーリング（60秒間隔）。Gmail Push通知（Pub/Sub）は過去に実装されていたが`GmailMessage`モデルは削除済みで現在は未使用 |
| 成長率 | 案件数・査定申込数は年々増加する想定（本ドキュメントでは+20%/年のシナリオも併記） |

---

## 2. 想定構成と各コンポーネントの役割

| コンポーネント | 役割 | 備考 |
|---|---|---|
| Cloud Run | Djangoアプリ本体の実行環境 | 常時起動、1vCPU/1GiB想定 |
| Cloud SQL (MySQL) | データベース | 現行 docker-compose の MySQL 8.0 を置き換え |
| Cloud Storage | 車両画像・契約書類等のメディアファイル保管 | 現状コードは `MEDIA_ROOT` 未設定のため別途実装が必要（[6. リスク・注意点](#6-リスク注意点)参照） |
| Compute Engine（e2-micro） | ナビクルスクレイパーの常駐実行環境 | `scraper/main.py` が60秒間隔でナビクルをポーリングし続ける常駐プロセスのため、Cloud Run/Cloud SQLとは別に稼働環境が必要（[6. リスク・注意点](#6-リスク注意点)参照） |
| Secret Manager | 環境変数・APIキー等の機密情報管理 | OAuth・ナビクル認証情報・スクレイパー内部トークンなど |
| Artifact Registry | コンテナイメージの保管 | CI/CDでのビルド成果物保存用 |

---

## 3. 月額コスト試算（初年度）

Cloud Storageは案件数の蓄積に応じて年々増加するため、本表は運用開始〜1年目の目安です。複数年の見通しは [4. ストレージ増加予測](#4-ストレージ増加予測) を参照してください。

### コスト優先構成（共有コアDB）

| 項目 | 構成 | 目安月額 |
|---|---|---|
| Cloud Run（常時起動） | 1vCPU/1GiB、待機時はCPU割引レート課金 | 約2,300〜3,500円 |
| Cloud SQL（MySQL） | 共有コア db-g1-small + ストレージ10〜20GB + バックアップ | 約4,500〜6,500円 |
| Cloud Storage | 画像・書類（初年度末で約50〜130GB想定） | 約450〜1,400円 |
| Compute Engine（e2-micro） | ナビクルスクレイパー常駐ワーカー | 約1,000〜1,500円 |
| Secret Manager・Artifact Registry | 設定値・コンテナ保管 | 約150〜500円 |
| **合計目安** | | **約8,400〜13,400円/月** |

### 信頼性優先構成（専有コアDB、推奨）

| 項目 | 構成 | 目安月額 |
|---|---|---|
| Cloud Run（常時起動） | 1vCPU/1GiB | 約2,300〜3,500円 |
| Cloud SQL（MySQL） | 専有コア db-custom-1-3840（1vCPU/3.75GB） + ストレージ + バックアップ | 約8,500〜11,000円 |
| Cloud Storage | 画像・書類（初年度末で約50〜130GB想定） | 約450〜1,400円 |
| Compute Engine（e2-micro） | ナビクルスクレイパー常駐ワーカー | 約1,000〜1,500円 |
| Secret Manager・Artifact Registry | 設定値・コンテナ保管 | 約150〜500円 |
| **合計目安** | | **約12,400〜17,900円/月** |

運用初期はコスト優先構成（共有コアDB）で開始し、レスポンス低下や接続エラーが見られた場合に専有コアへスケールアップする進め方も可能です。

---

## 4. ストレージ増加予測

案件数 300件/月 × 約15〜20点/件の画像・書類が蓄積されるため、Cloud Storageの使用量は年々増加します。Cloud Storageは従量課金で容量上限を設定するものではないため「容量不足」にはなりませんが、コストが右肩上がりになる点は事前に共有しておくべきポイントです。

### 月間・年間の増加量

| 前提 | 月間増加量 | 年間増加量 |
|---|---|---|
| 圧縮なし（平均2.5MB/枚） | 約11GB/月 | 約132GB/年 |
| アップロード時に自動圧縮（平均1MB/枚） | 約4.5GB/月 | 約54GB/年 |

### 複数年の累積容量・コスト目安（案件数フラット想定）

| 経過年数 | 累積容量（圧縮なし） | 月額コスト目安 |
|---|---|---|
| 1年後 | 約130GB | 約450円/月 |
| 2年後 | 約260GB | 約900円/月 |
| 3年後 | 約400GB | 約1,400円/月 |

### 案件数が年20%ずつ増加する場合

| 経過年数 | 累積容量（圧縮なし） | 月額コスト目安 |
|---|---|---|
| 1年後 | 約130GB | 約450円/月 |
| 2年後 | 約290GB | 約1,000円/月 |
| 3年後 | 約480GB | 約1,650円/月 |

いずれのシナリオでも3年目時点で月1,000〜1,700円程度であり、コスト面で問題になる規模ではありません。アップロード時の画像圧縮（長辺1920px・JPEG品質80%程度への自動リサイズ）を実装すれば、増加ペースをさらに半分以下に抑えられます（現状未実装）。

なお、案件の構造化データ（申込・契約・売却・連絡履歴等）自体はCloud SQL側に保存されますが、1件あたり数十KB程度と非常に軽量です。300件/月のペースが今後数倍に増えても、Cloud SQLストレージの年間増加量は数百MB〜1GB程度に収まり、20GBの想定に対しては問題になりません（画像・書類の実ファイルはCloud Storage側に保存され、DBにはファイルパスのみ記録されるため）。

---

## 5. 試算の根拠

- **Cloud Run**: 「リクエスト処理中のみCPU割り当て」モードでは、min-instancesによる待機中インスタンスはCPUが割引レート（$0.0000025/vCPU秒、アクティブ時の約1/10）、メモリは通常レート（$0.0000025/GiB秒）で課金される。1vCPU/1GiBを24時間365日起動した場合の待機コストが約$13/月（≒2,000円弱）。日中の実処理分（40名・通常利用）はこれに数百円程度加算される想定。
- **Cloud SQL**: 共有コア（db-f1-micro/db-g1-small）はSLA対象外。`docs/04_setup/CLOUDSQL_EXPLAIN_RUNBOOK.md` で前提としているMySQL 8.xインスタンスのクエリ性能確認結果も踏まえ、40名規模の同時利用では専有コアの方が安全。
- **Cloud Storage**: 案件数300件/月 × 画像・書類15〜20点/件 × 平均2.5MB/点（未圧縮）で算出。詳細は [4. ストレージ増加予測](#4-ストレージ増加予測) を参照。
- **Compute Engine（スクレイパー）**: `scraper/main.py` は60秒間隔でナビクルをポーリングし続ける常駐プロセスであり、HTTPリクエスト単位で課金されるCloud Runには適さない。負荷が極めて軽い（requests + BeautifulSoupによるポーリングのみ）ため、最小構成の e2-micro（共有vCPU・1GBメモリ）を24時間稼働させる前提で算出。
- 為替レートは概算で 1ドル ≒ 150〜155円として算出。

---

## 6. リスク・注意点

1. **Cloud Runの無料枠は東京リージョン非対象**
   無料枠（180,000 vCPU秒/月、360,000 GiB秒/月、200万リクエスト/月）は us-central1 / us-east1 / us-west1 限定。asia-northeast1にデプロイする場合は全量が課金対象になる（ただし40名規模なら絶対額は小さい）。

2. **共有コアDBはSLA対象外・性能上限が低い**
   db-f1-micro・db-g1-small はGoogle CloudのSLA保証がなく、同時実行クエリが増えるとレスポンス劣化のリスクがある。40名が日中に集中アクセスする想定では、早期に専有コアへの移行を検討すべき。

3. **メディアファイルの永続化が未実装**
   現状の `config/settings.py` には `MEDIA_ROOT`/Cloud Storage連携の設定がない。Cloud Runはコンテナのローカルディスクが再起動で消えるため、車両画像・契約書類等を保存するには `django-storages` 等によるCloud Storage連携の実装が別途必要（本コストには実装費は含まない、運用コストのみ）。

4. **本番用デプロイ構成が未整備**
   現リポジトリには本番用Dockerfile・Cloud Build設定・Cloud Run/Compute Engine向けの設定がまだ存在しない。デプロイには別途構築作業が必要。

5. **価格変動・地域差**
   GCPの料金は改定される可能性があり、本試算は2026年6月時点の公開情報に基づく。正式な金額は [Pricing Calculator](https://cloud.google.com/products/calculator) での確認を推奨。

6. **常時起動によるコスト増**
   スケールトゥゼロ（min-instances=0）にすれば待機コストはほぼゼロになるが、利用が無い時間帯の最初のアクセスにコールドスタート（数秒の遅延）が発生する。常時起動はこのトレードオフを解消するための選択。

7. **Cloud Storageコストの経年増加**
   案件数の増加に伴いCloud Storage使用量・コストは年々増加する（[4. ストレージ増加予測](#4-ストレージ増加予測)参照）。容量不足にはならないが、コストは右肩上がりになる前提で顧客への説明・予算計画を行うべき。画像の自動圧縮を実装すれば増加ペースを抑制できる。

8. **Gmail Push通知（Pub/Sub）は現在未使用**
   CLAUDE.mdの技術スタック説明には「メール: Gmail API（Push通知: Google Cloud Pub/Sub）」と記載されているが、`leads/migrations/0019_remove_gmail_message.py` で`GmailMessage`モデルが削除されており、Pub/Subのwebhookエンドポイントもコード上に存在しない。案件の取り込みは現在ナビクルスクレイパー（ポーリング方式）のみで行われているため、本書では旧構成（Pub/Sub）を試算から除外し、実際に常時稼働しているスクレイパーのホスティングコストを計上した。

9. **スクレイパーは常駐プロセスのためCloud Runと別構成が必要**
   `scraper/main.py` はリクエスト/レスポンス型ではなく、無限ループでポーリングを続ける常駐ワーカー。Cloud Runは基本的にHTTPリクエスト処理に最適化されたサービスのため、この用途には小型のCompute Engineインスタンス（または同様の常時起動ワーカー環境）の方が適している。スクレイパー自体のコンテナ化・本番デプロイ設定も別途必要（[4. 本番用デプロイ構成が未整備](#6-リスク注意点)と同様、実装費は本コストに含まない）。

---

## 7. 補足

- 月単位の予算アラート（Budget Alert）をGCP側で設定し、想定を超えた課金が発生した場合に通知を受け取れるようにしておくと安心。
- Cloud SQLのバックアップ・ストレージ自動増加によりストレージ課金が徐々に増える点に注意（定期的な棚卸しを推奨）。
- 利用者数・案件数が今後さらに増える場合（勤怠管理・顧客管理など `docs/04_setup/ARCHITECTURE.md` 記載の未実装アプリが追加された場合）は、本試算より上振れする。
- Cloud Storageの増加ペースは画像の自動圧縮実装で大きく抑制できるため、運用コストを抑えたい場合は早期の実装を推奨。

---

## 8. Pricing Calculatorでの入力例

[GCP Pricing Calculator](https://cloud.google.com/products/calculator) で本ドキュメントと同様の試算を再現する場合の入力値の例。サービスごとに「Estimate」へ項目を追加して合計する。

### Cloud Run

| 項目 | 入力値 |
|---|---|
| Region | `asia-northeast1` (Tokyo) |
| Tier | Tier 1 |
| CPU allocation | "CPU is only allocated during request processing" |
| Number of requests | 約90,000 リクエスト/月（40名 × 平均100リクエスト/日 × 22日で概算） |
| Request duration | 200 ms（Django+MySQLの平均的な処理時間として仮置き） |
| Memory allocated | 1 GiB |
| CPU allocated | 1 vCPU |
| Minimum instances | 1（常時起動） |
| Concurrency | デフォルト（80）でOK |

※ Calculatorは「リクエスト処理中」の分しか自動算出しないことが多く、min-instancesによる待機コスト（CPU割引レート + メモリ）が反映されない場合がある。その場合は、1vCPU/1GiBを720時間（≒2,592,000秒）、CPU $0.0000025/秒・メモリ $0.0000025/GiB秒で計算した待機コスト（約$13/月）を別途加算する。

### Cloud SQL for MySQL

| 項目 | コスト優先構成 | 信頼性優先構成 |
|---|---|---|
| Database engine | MySQL | MySQL |
| Region | asia-northeast1 | asia-northeast1 |
| Edition | Enterprise | Enterprise |
| vCPU / Memory | 共有コア db-g1-small相当（1 vCPU共有 / 1.7GB） | 専有コア 1 vCPU / 3.75GB（db-custom-1-3840） |
| Storage type | SSD | SSD |
| Storage size | 20 GB | 20 GB |
| High availability | なし（Single zone） | なし（Single zone） |
| Backup storage | 自動見積りでOK（20GB分が目安） | 同左 |

### Cloud Storage

| 項目 | 入力値 |
|---|---|
| Storage class | Standard |
| Region | asia-northeast1 |
| Data stored | 50〜130 GB（初年度末、300件/月×15〜20点/件の累積想定。2年目以降は[4. ストレージ増加予測](#4-ストレージ増加予測)の値に置き換える） |
| Class A operations（書込・一覧取得） | 数千回/月 |
| Class B operations（読込） | 数万回/月 |
| Network egress | ほぼ0（社内利用・同リージョン内通信が中心） |

### Compute Engine（ナビクルスクレイパー）

| 項目 | 入力値 |
|---|---|
| Region | asia-northeast1 |
| Machine type | e2-micro（共有2vCPU / 1GB メモリ） |
| Number of instances | 1（常時稼働） |
| Usage time | 730時間/月（24時間×30日） |
| Boot disk | 標準永続ディスク 10GB |
| Committed use discount | なし（オンデマンド） |

### Secret Manager / Artifact Registry

| 項目 | 入力値 |
|---|---|
| Secret Manager - アクティブなシークレット数 | 5〜10個 |
| Secret Manager - アクセス回数 | 月1万回未満 |
| Artifact Registry - ストレージ | コンテナイメージ 1〜2 GB |

これらを合計すると、[3. 月額コスト試算（初年度）](#3-月額コスト試算初年度)の数字（コスト優先: 約8,400〜13,400円、信頼性優先: 約12,400〜17,900円）とほぼ近い結果になる。

---

## 9. 参考資料

- [Cloud Run pricing | Google Cloud](https://cloud.google.com/run/pricing)
- [Set minimum instances for services | Cloud Run | Google Cloud Documentation](https://docs.cloud.google.com/run/docs/configuring/min-instances)
- [Billing settings for services | Cloud Run | Google Cloud Documentation](https://docs.cloud.google.com/run/docs/configuring/billing-settings)
- [Cloud SQL pricing | Google Cloud](https://cloud.google.com/sql/pricing)
- [GCP Pricing Calculator](https://cloud.google.com/products/calculator)

---

**更新履歴:**
- 2026-06-29: 初版作成
- 2026-06-29: Pricing Calculatorでの入力例を追加
- 2026-06-29: 案件数（300件/月）ベースのストレージ増加予測を追加し、複数年のコスト見通しを反映
- 2026-06-29: Gmail Push通知（Pub/Sub）は現在未使用であることを確認し試算から除外。実際に稼働しているナビクルスクレイパーの常駐実行環境（Compute Engine e2-micro）をコストに追加
