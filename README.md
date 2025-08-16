# Azure Functions 日報フィードバックシステム

Azure Functions と GitHub Copilot API を使用した、AI による日報フィードバック生成システムです。

## 概要

このシステムは、従業員の日報を受け取り、GitHub Copilot API を使用して AI による建設的なフィードバックを生成します。過去の日報データを参照して、継続的な成長をサポートするパーソナライズされたフィードバックを提供します。

## 主な機能

- 📝 **日報の AI フィードバック生成**: GitHub Copilot API を使用した高品質なフィードバック
- 📊 **過去データとの比較**: 前回の日報と比較して成長分析を提供
- 💾 **Cosmos DB 統合**: 日報データとフィードバックの永続化
- 🔧 **REST API**: HTTP トリガーによる柔軟な統合
- ⚙️ **設定可能**: YAML ファイルによる設定管理

## アーキテクチャ

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   クライアント   │────│ Azure Functions │────│ GitHub Copilot  │
│  (日報システム)  │    │  HTTP Trigger   │    │      API        │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                               │
                               ▼
                       ┌─────────────────┐
                       │   Cosmos DB     │
                       │  (データ保存)    │
                       └─────────────────┘
```

## 技術スタック

- **Azure Functions**: Python 3.12
- **GitHub Copilot API**: GPT-4o-mini モデル
- **Azure Cosmos DB**: NoSQL データベース
- **PyYAML**: 設定ファイル管理
- **Requests**: HTTP クライアント

## セットアップ

### 前提条件

- Python 3.8 以上
- Azure Functions Core Tools v4
- Azure サブスクリプション
- GitHub Copilot アクセス

### 1. 環境のセットアップ

```bash
# リポジトリのクローン
git clone <repository-url>
cd Azure-function

# 仮想環境の作成（推奨）
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # macOS/Linux

# 依存関係のインストール
pip install -r requirements.txt
```

### 2. 設定ファイルの編集

`local.settings.json` ファイルで環境変数を設定：

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "UseDevelopmentStorage=true",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "GITHUB_TOKEN": "your_github_token_here",
    "COSMOSDB_ENDPOINT": "your_cosmosdb_endpoint",
    "COSMOSDB_KEY": "your_cosmosdb_key"
  }
}
```

### 3. Cosmos DB のセットアップ

1. Azure ポータルで Cosmos DB アカウントを作成
2. データベース名: `papa_test`
3. コンテナー名: `feedback`
4. パーティションキー: `/type`

### 4. ローカル実行

```bash
# Azure Functions の起動
func host start
```

サーバーは `http://localhost:7071` で起動します。

## API 使用方法

### エンドポイント

```
POST /api/daily_report_feedback
```

### リクエスト形式

```json
{
  "metadata": {
    "submitterEmail": "user@example.com",
    "timestamp": "2025-01-15T18:30:00Z",
    "source": "daily_report_form"
  },
  "data": {
    "submissionDate": "2025-01-15",
    "good_things": [
      "新機能のAPI設計を完了",
      "バグ修正で3件の問題を解決"
    ],
    "reflections": [
      "テスト工程で予想以上に時間がかかった",
      "ドキュメント作成が後回しになりがち"
    ]
  }
}
```

### レスポンス形式

```json
{
  "success": true,
  "document_id": "report_user@example.com_20250115_183000",
  "feedback": {
    "overall_rating": "4",
    "positive_points": [
      "API設計の完了とバグ修正の成果が素晴らしい"
    ],
    "improvement_areas": [
      "テスト工程の時間見積もり精度向上"
    ],
    "action_items": [
      "次回はテスト計画をより詳細に立てる"
    ],
    "encouragement": "着実に成果を上げており、継続的な改善意識が素晴らしいです"
  },
  "has_previous_report": true,
  "processed_at": "2025-01-15T18:30:15.123Z"
}
```

## テスト

プロジェクトには `test-api.http` ファイルが含まれており、REST Client 拡張機能を使用してテストできます：

1. VS Code で `test-api.http` を開く
2. REST Client 拡張機能をインストール
3. "Send Request" をクリックしてテスト実行

## デプロイ

### Azure への手動デプロイ

```bash
# Azure にログイン
az login

# Function App の作成（初回のみ）
az functionapp create \
  --resource-group <your-resource-group> \
  --consumption-plan-location japaneast \
  --runtime python \
  --runtime-version 3.12 \
  --functions-version 4 \
  --name <your-function-app-name> \
  --storage-account <your-storage-account>

# アプリケーション設定
az functionapp config appsettings set \
  --name <your-function-app-name> \
  --resource-group <your-resource-group> \
  --settings \
    GITHUB_TOKEN="your_github_token" \
    COSMOSDB_ENDPOINT="your_cosmosdb_endpoint" \
    COSMOSDB_KEY="your_cosmosdb_key"

# デプロイ
func azure functionapp publish <your-function-app-name>
```

## 設定

### config.yaml の設定項目

| 項目 | 説明 | デフォルト値 |
|------|------|-------------|
| `github_copilot.model` | 使用する AI モデル | `openai/gpt-4o-mini` |
| `github_copilot.max_tokens` | 最大トークン数 | `1000` |
| `github_copilot.temperature` | 応答の創造性 | `0.7` |
| `cosmosdb.database_name` | データベース名 | `papa_test` |
| `cosmosdb.container_name` | コンテナー名 | `feedback` |
| `settings.max_previous_reports` | 参照する過去日報数 | `1` |

## トラブルシューティング

### よくある問題

1. **GitHub Token エラー**
   ```
   GitHub Copilot API エラー: 401
   ```
   → `GITHUB_TOKEN` 環境変数が正しく設定されているか確認

2. **Cosmos DB 接続エラー**
   ```
   CosmosDB接続エラー
   ```
   → エンドポイントとキーが正しく設定されているか確認

3. **JSON パースエラー**
   ```
   無効なJSONデータ
   ```
   → リクエストボディの JSON 形式を確認

### ログの確認

```bash
# ローカル開発時
func host start --verbose
```

## 開発

### プロジェクト構造

```
Azure-function/
├── function_app.py          # メインアプリケーション
├── config.yaml             # 設定ファイル
├── host.json               # Functions ランタイム設定
├── local.settings.json     # ローカル環境変数
├── requirements.txt        # Python 依存関係
├── test-api.http          # API テストファイル
└── README.md              # このファイル
```

### コードの主要クラス

- `DailyReportProcessor`: 日報処理のメインロジック
- `daily_report_feedback`: HTTP トリガー関数

### 開発時の注意事項

- 本番環境では `local.settings.json` の機密情報を Azure App Settings で管理
- Cosmos DB の接続情報は環境変数から取得
- エラーハンドリングとログ出力を適切に実装

## 更新履歴

- **v1.0.0** (2025-01-15): 初回リリース
  - 基本的な日報フィードバック機能
  - GitHub Copilot API 統合
  - Cosmos DB データ保存機能
