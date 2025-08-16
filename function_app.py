import azure.functions as func
import logging
import json
import yaml
import os
import requests
from datetime import datetime, timezone
from azure.cosmos import CosmosClient
from typing import Optional, Dict, Any, List

# 設定ファイルの読み込み
def load_config() -> Dict[str, Any]:
    """config.yamlから設定を読み込む"""
    try:
        with open('config.yaml', 'r', encoding='utf-8') as file:
            config = yaml.safe_load(file)
        
        # 環境変数の置換
        config['cosmosdb']['endpoint'] = os.getenv('COSMOSDB_ENDPOINT', config['cosmosdb']['endpoint'])
        config['cosmosdb']['key'] = os.getenv('COSMOSDB_KEY', config['cosmosdb']['key'])
        
        return config
    except Exception as e:
        logging.error(f"設定ファイル読み込みエラー: {e}")
        raise

# CosmosDBクライアントの初期化
config = load_config()

# 環境変数から実際の値を取得、なければconfig.yamlのダミー値を使用
cosmos_endpoint = os.environ.get('COSMOSDB_ENDPOINT', config['cosmosdb']['endpoint'])
cosmos_key = os.environ.get('COSMOSDB_KEY', config['cosmosdb']['key'])

# 開発環境での起動を可能にするため、実際の接続情報がある場合のみ初期化
cosmos_client = None
if (cosmos_endpoint and cosmos_key and 
    not cosmos_endpoint.startswith('${') and 
    not cosmos_key.startswith('${') and
    not cosmos_key == 'dummy_key_for_development'):
    try:
        cosmos_client = CosmosClient(cosmos_endpoint, cosmos_key)
        database = cosmos_client.get_database_client(config['cosmosdb']['database_name'])
        container = database.get_container_client(config['cosmosdb']['container_name'])
    except Exception as e:
        print(f"CosmosDB接続エラー (開発時は無視可能): {e}")
        cosmos_client = None
        database = None
        container = None
else:
    print("開発モード: CosmosDB接続をスキップ")
    database = None
    container = None

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

class DailyReportProcessor:
    """日報処理クラス"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.github_token = os.getenv('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GITHUB_TOKEN環境変数が設定されていません")
    
    def get_previous_report(self, user_email: str, current_date: str) -> Optional[Dict[str, Any]]:
        """前回の日報を取得"""
        try:
            query = """
                SELECT TOP 1 * FROM c 
                WHERE c.metadata.submitterEmail = @email 
                AND c.type = 'daily_report'
                AND c.data.submissionDate < @current_date
                ORDER BY c.data.submissionDate DESC
            """
            
            parameters = [
                {"name": "@email", "value": user_email},
                {"name": "@current_date", "value": current_date}
            ]
            
            items = list(container.query_items(
                query=query,
                parameters=parameters,
                enable_cross_partition_query=True
            ))
            
            return items[0] if items else None
            
        except Exception as e:
            logging.error(f"前回日報取得エラー: {e}")
            return None
    
    def create_ai_prompt(self, current_report: Dict[str, Any], previous_report: Optional[Dict[str, Any]]) -> str:
        """AIプロンプトを作成"""
        template = self.config['prompts']['user_template']
        
        # 前回レポートセクション
        previous_section = ""
        if previous_report:
            prev_data = previous_report.get('data', {})
            previous_section = f"""
            
【前回の日報（{prev_data.get('submissionDate', 'N/A')}）】
            良かったこと: {prev_data.get('goodThings', 'N/A')}
            反省点: {prev_data.get('reflections', 'N/A')}
            """
        
        # テンプレートに値を挿入
        data = current_report.get('data', {})
        prompt = template.format(
            current_date=data.get('submissionDate', ''),
            name=data.get('name', ''),
            good_things=data.get('goodThings', ''),
            reflections=data.get('reflections', ''),
            additional_info=json.dumps(data, ensure_ascii=False, indent=2),
            previous_report_section=previous_section
        )
        
        return prompt
    
    def call_github_copilot_api(self, prompt: str) -> Dict[str, Any]:
        """GitHub Copilot APIを呼び出し"""
        try:
            headers = {
                'Authorization': f'Bearer {self.github_token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'model': self.config['github_copilot']['model'],
                'messages': [
                    {
                        'role': 'system',
                        'content': self.config['prompts']['feedback_system']
                    },
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': self.config['github_copilot']['max_tokens'],
                'temperature': self.config['github_copilot']['temperature']
            }
            
            response = requests.post(
                self.config['github_copilot']['api_url'],
                headers=headers,
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                content = result['choices'][0]['message']['content']
                
                # JSONレスポンスのパース
                try:
                    feedback = json.loads(content)
                    return feedback
                except json.JSONDecodeError:
                    # JSONパースに失敗した場合は文字列として返す
                    return {"feedback_text": content}
            else:
                logging.error(f"GitHub Copilot API エラー: {response.status_code} - {response.text}")
                return {"error": f"API呼び出しエラー: {response.status_code}"}
                
        except Exception as e:
            logging.error(f"GitHub Copilot API 呼び出しエラー: {e}")
            return {"error": str(e)}
    
    def save_to_cosmosdb(self, report_data: Dict[str, Any], feedback: Dict[str, Any]) -> str:
        """CosmosDBにデータを保存"""
        try:
            # 一意のIDを生成
            report_id = f"report_{report_data.get('metadata', {}).get('submitterEmail', 'unknown')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # CosmosDB用のドキュメント作成
            document = {
                "id": report_id,
                "type": "daily_report_with_feedback",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ai_feedback": feedback,
            }
            
            # CosmosDBに保存
            container.create_item(body=document)
            logging.info(f"データ保存成功: {report_id}")
            
            return report_id
            
        except Exception as e:
            logging.error(f"CosmosDB保存エラー: {e}")
            raise

@app.route(route="daily_report_feedback")
def daily_report_feedback(req: func.HttpRequest) -> func.HttpResponse:
    """日報フィードバック生成のメイン関数"""
    logging.info('日報フィードバック処理開始')
    
    try:
        # リクエストボディからJSONデータを取得
        try:
            req_body = req.get_json()
            if not req_body:
                return func.HttpResponse(
                    json.dumps({"error": "JSONデータが必要です"}, ensure_ascii=False),
                    status_code=400,
                    mimetype="application/json"
                )
        except ValueError as e:
            return func.HttpResponse(
                json.dumps({"error": f"無効なJSONデータ: {str(e)}"}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json"
            )
        
        # 必要なフィールドの検証
        required_fields = ['data', 'metadata']
        for field in required_fields:
            if field not in req_body:
                return func.HttpResponse(
                    json.dumps({"error": f"必須フィールドが不足: {field}"}, ensure_ascii=False),
                    status_code=400,
                    mimetype="application/json"
                )
        
        # 日報処理器を初期化
        processor = DailyReportProcessor(config)
        
        # 送信者のメールアドレスと日付を取得
        submitter_email = req_body.get('metadata', {}).get('submitterEmail')
        submission_date = req_body.get('data', {}).get('submissionDate')
        
        if not submitter_email or not submission_date:
            return func.HttpResponse(
                json.dumps({"error": "送信者メールアドレスまたは送信日付が不足しています"}, ensure_ascii=False),
                status_code=400,
                mimetype="application/json"
            )
        
        # 前回の日報を取得
        previous_report = processor.get_previous_report(submitter_email, submission_date)
        
        # AIプロンプトを作成
        prompt = processor.create_ai_prompt(req_body, previous_report)
        
        # GitHub Copilot APIを呼び出し
        feedback = processor.call_github_copilot_api(prompt)
        
        # CosmosDBに保存
        document_id = processor.save_to_cosmosdb(req_body, feedback)
        
        # レスポンスの作成
        response_data = {
            "success": True,
            "document_id": document_id,
            "feedback": feedback,
            "has_previous_report": previous_report is not None,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        return func.HttpResponse(
            json.dumps(response_data, ensure_ascii=False, indent=2),
            status_code=200,
            mimetype="application/json"
        )
        
    except Exception as e:
        logging.error(f"日報フィードバック処理エラー: {str(e)}")
        return func.HttpResponse(
            json.dumps({"error": f"処理中にエラーが発生しました: {str(e)}"}, ensure_ascii=False),
            status_code=500,
            mimetype="application/json"
        )