# CLAUDE.md — Car Internal System

> **コーディング前に必ず `docs/` フォルダを参照してください。**

---

## プロジェクト概要

中古車の買取・販売業務を管理する社内向けWebシステム。
営業担当者が顧客・車両・商談情報を一元管理できるよう設計している。

---

## 技術スタック

| 項目 | 内容 |
|------|------|
| バックエンド | Django 5.0.1 (Python) |
| フロントエンド | Bootstrap 5 + カスタムトークン/オーバーライド |
| データベース | MySQL 8.0 (mysqlclient 2.2.1) |
| インフラ | Docker / Docker Compose |
| 認証 | Google OAuth 2.0 (google-auth-oauthlib) |
| メール | Gmail API (Push通知: Google Cloud Pub/Sub) |

---

## docsフォルダ構成

```
docs/
├── 01_requirements/     # 要件定義・業務フロー・画面仕様書
├── 02_design/           # システム設計・DB設計・ER図など
├── 03_coding-rules/     # コーディング規約・AI開発ルール
│   └── ai-dev-rules.md  # Django + Bootstrap UIのコーディングルール
└── 04_setup/            # 環境構築・インフラ手順書
    ├── ARCHITECTURE.md           # システムアーキテクチャ説明
    ├── CLOUDSQL_EXPLAIN_RUNBOOK.md  # Cloud SQL 運用手順
    ├── GMAIL_API_SETUP.md        # Gmail API 初期設定手順
    ├── GMAIL_PUSH_SETUP.md       # Gmail Push通知設定手順
    └── OAUTH_SETUP.md            # Google OAuth 設定手順
```

### 各フォルダの役割

- **01_requirements/** — 業務要件・画面仕様・エンティティ定義など要件フェーズの成果物
- **02_design/** — アーキテクチャ設計・DB設計・API設計などの設計ドキュメント
- **03_coding-rules/** — コーディング規約、UIスタイルルール、AI開発時の遵守事項
- **04_setup/** — 開発環境・本番環境のセットアップ手順・運用Runbook

---

## コーディング時の注意事項

1. UIの実装前に [docs/03_coding-rules/ai-dev-rules.md](docs/03_coding-rules/ai-dev-rules.md) を必ず確認する
2. Bootstrap のレイアウト・コンポーネントを優先的に使用する
3. 色・サイズなどのデザイントークンは `static/ui/tokens.css` と `static/ui/bootstrap-overrides.css` に従う
4. 新しい色やサイズを勝手に追加しない
