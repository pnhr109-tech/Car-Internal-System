"""
本文パース機能のテストスクリプト
実際のメール本文形式でパース処理をテスト
"""
import re
from datetime import datetime
from zoneinfo import ZoneInfo

# テスト用メール本文
test_body = """=====================================
■お申込み内容■
お申込番号　  ：9060727
お申込日時　　：2026年02月05日 21:25
希望売却時期　：直近層
-===================================-
■お車の情報■
メーカー名　　：ダイハツ
車種名　　　　：タント
年式　　　　　：2013年（平成25年）
走行距離　　　：１５万キロ以上
=-=================================-=
■お客様ご連絡先■
お名前　　　　：田中直美　　
電話番号　　　：090-1234-5678
郵便番号　　　：319-1541
住所　　　　　：茨城県北茨城市磯原町磯原
メールアドレス：test@gmail.com
==-===============================-==
"""

def extract_value(pattern, body):
    """正規表現で値を抽出"""
    match = re.search(pattern, body)
    return match.group(1).strip() if match else ''

def parse_datetime(datetime_str):
    """日時文字列をdatetimeオブジェクトに変換"""
    if not datetime_str:
        return None
    
    try:
        # "2026年02月05日 21:25" 形式をパース
        datetime_str = datetime_str.replace('年', '-').replace('月', '-').replace('日', '')
        dt = datetime.strptime(datetime_str.strip(), '%Y-%m-%d %H:%M')
        # タイムゾーンを付与（日本時間として扱う）
        return dt.replace(tzinfo=ZoneInfo('Asia/Tokyo'))
    except Exception as e:
        print(f"日時パースエラー: {e}")
        return None

# テスト実行
print("=" * 60)
print("メール本文パーステスト")
print("=" * 60)

print("\n【元の本文】")
print(test_body)

print("\n【抽出結果】")
data = {
    'お申込番号': extract_value(r'お申込番号\s*[：:]\s*(\d+)', test_body),
    'お申込日時': extract_value(r'お申込日時\s*[：:]\s*(.+)', test_body),
    '希望売却時期': extract_value(r'希望売却時期\s*[：:]\s*(.+)', test_body),
    'メーカー名': extract_value(r'メーカー名\s*[：:]\s*(.+)', test_body),
    '車種名': extract_value(r'車種名\s*[：:]\s*(.+)', test_body),
    '年式': extract_value(r'年式\s*[：:]\s*(.+)', test_body),
    '走行距離': extract_value(r'走行距離\s*[：:]\s*(.+)', test_body),
    'お名前': extract_value(r'お名前\s*[：:]\s*(.+)', test_body),
    '電話番号': extract_value(r'電話番号\s*[：:]\s*(.+)', test_body),
    '郵便番号': extract_value(r'郵便番号\s*[：:]\s*(.+)', test_body),
    '住所': extract_value(r'住所\s*[：:]\s*(.+)', test_body),
    'メールアドレス': extract_value(r'メールアドレス\s*[：:]\s*(.+)', test_body),
}

for key, value in data.items():
    status = "✓" if value else "✗"
    print(f"{status} {key:15s}: {value}")

# 日時パース
print("\n【日時パース】")
datetime_str = data['お申込日時']
dt = parse_datetime(datetime_str)
if dt:
    print(f"✓ 元の文字列: {datetime_str}")
    print(f"✓ パース結果: {dt}")
    print(f"✓ ISO形式: {dt.isoformat()}")
else:
    print(f"✗ パース失敗: {datetime_str}")

print("\n" + "=" * 60)
print("✅ テスト完了")
print("=" * 60)
