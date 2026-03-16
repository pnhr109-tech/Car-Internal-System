from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.utils import timezone


class Command(BaseCommand):
    help = '顧客共有用のダッシュボードモックHTMLを単体ファイルで出力します。'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='mock_exports/dashboard_mock.html',
            help='出力先HTMLパス（未指定時: mock_exports/dashboard_mock.html）',
        )

    def handle(self, *args, **options):
        output = options['output']
        output_path = Path(output)
        if not output_path.is_absolute():
            output_path = Path(settings.BASE_DIR) / output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)

        context = self._build_mock_context()
        context.update({
            'generated_at': timezone.localtime().strftime('%Y-%m-%d %H:%M'),
        })

        inline_ui_css = '\n\n'.join([
            self._read_static_css('ui/tokens.css'),
            self._read_static_css('ui/bootstrap-overrides.css'),
            self._read_static_css('ui/components.css'),
        ])

        html = render_to_string('home/dashboard_mock_standalone.html', context)
        html = html.replace('/*__INLINE_UI_CSS__*/', inline_ui_css)
        output_path.write_text(html, encoding='utf-8')

        self.stdout.write(self.style.SUCCESS(f'モックHTMLを出力しました: {output_path}'))

    @staticmethod
    def _read_static_css(relative_path):
        css_path = Path(settings.BASE_DIR) / 'static' / relative_path
        if not css_path.exists():
            return ''
        return css_path.read_text(encoding='utf-8')

    @staticmethod
    def _build_mock_context():
        now = timezone.localtime()

        recent_appointment_updates = [
            {
                'customer_name': '佐藤 一郎',
                'status_updated_at': now - timedelta(hours=1, minutes=12),
                'sales_owner_name': '山田 太郎',
                'application_number': 'A202603-1001',
            },
            {
                'customer_name': '高橋 美咲',
                'status_updated_at': now - timedelta(hours=2, minutes=4),
                'sales_owner_name': '鈴木 次郎',
                'application_number': 'A202603-1002',
            },
            {
                'customer_name': '伊藤 健',
                'status_updated_at': now - timedelta(hours=3, minutes=20),
                'sales_owner_name': '山田 太郎',
                'application_number': 'A202603-1003',
            },
        ]

        recent_closed_updates = [
            {
                'customer_name': '中村 花子',
                'status_updated_at': now - timedelta(hours=1, minutes=45),
                'sales_owner_name': '山田 太郎',
                'application_number': 'A202603-0988',
            },
            {
                'customer_name': '小林 大輔',
                'status_updated_at': now - timedelta(hours=5, minutes=7),
                'sales_owner_name': '佐々木 明',
                'application_number': 'A202603-0979',
            },
            {
                'customer_name': '加藤 由美',
                'status_updated_at': now - timedelta(hours=6, minutes=13),
                'sales_owner_name': '鈴木 次郎',
                'application_number': 'A202603-0972',
            },
        ]

        closed_rankings = [
            {'sales_owner_name': '山田 太郎', 'closed_count': 12},
            {'sales_owner_name': '鈴木 次郎', 'closed_count': 10},
            {'sales_owner_name': '佐々木 明', 'closed_count': 8},
        ]

        store_performance_summary = [
            {'store': '札幌店', 'mq': 15, 'appointments': 12, 'contracts': 5, 'close_rate': 41.7},
            {'store': '仙台店', 'mq': 12, 'appointments': 10, 'contracts': 4, 'close_rate': 40.0},
            {'store': '東京店', 'mq': 22, 'appointments': 19, 'contracts': 9, 'close_rate': 47.4},
            {'store': '名古屋店', 'mq': 14, 'appointments': 11, 'contracts': 5, 'close_rate': 45.5},
            {'store': '大阪店', 'mq': 18, 'appointments': 15, 'contracts': 6, 'close_rate': 40.0},
            {'store': '福岡店', 'mq': 11, 'appointments': 9, 'contracts': 3, 'close_rate': 33.3},
        ]

        assessment_seed = [
            {
                'sales_owner_name': '山田 太郎',
                'follow_status': '商談確定',
                'customer_name': '佐藤 一郎',
                'phone_number': '090-1111-2222',
                'desired_sale_timing': '1ヶ月以内',
                'maker': 'トヨタ',
                'car_model': 'プリウス',
                'year': '2019',
                'mileage': '34,000km',
                'address': '東京都港区',
            },
            {
                'sales_owner_name': '鈴木 次郎',
                'follow_status': '再コール予定',
                'customer_name': '高橋 美咲',
                'phone_number': '080-3333-4444',
                'desired_sale_timing': '3ヶ月以内',
                'maker': '日産',
                'car_model': 'セレナ',
                'year': '2018',
                'mileage': '51,000km',
                'address': '神奈川県横浜市',
            },
            {
                'sales_owner_name': '山田 太郎',
                'follow_status': '成約',
                'customer_name': '伊藤 健',
                'phone_number': '070-5555-6666',
                'desired_sale_timing': '即日',
                'maker': 'ホンダ',
                'car_model': 'フィット',
                'year': '2020',
                'mileage': '28,000km',
                'address': '埼玉県さいたま市',
            },
            {
                'sales_owner_name': '佐々木 明',
                'follow_status': '見送り',
                'customer_name': '松本 翼',
                'phone_number': '090-7777-8888',
                'desired_sale_timing': '未定',
                'maker': 'マツダ',
                'car_model': 'CX-5',
                'year': '2017',
                'mileage': '67,000km',
                'address': '千葉県船橋市',
            },
            {
                'sales_owner_name': '小林 航',
                'follow_status': '未対応',
                'customer_name': '井上 玲奈',
                'phone_number': '080-9999-0000',
                'desired_sale_timing': '2ヶ月以内',
                'maker': 'スバル',
                'car_model': 'レヴォーグ',
                'year': '2021',
                'mileage': '15,000km',
                'address': '大阪府吹田市',
            },
        ]

        latest_assessments = []
        for index in range(180):
            base = assessment_seed[index % len(assessment_seed)].copy()
            base['application_number'] = f"A202603-{1001 + index:04d}"
            base['application_datetime'] = now - timedelta(minutes=9 * index)

            if index % 6 == 0:
                base['follow_status'] = '未対応'
                base['sales_owner_name'] = ''
            elif index % 6 == 1:
                base['follow_status'] = '再コール予定'
                base['sales_owner_name'] = '山田 太郎'
            elif index % 6 == 2:
                base['follow_status'] = '商談確定'
                base['sales_owner_name'] = '山田 太郎'
            elif index % 6 == 3:
                base['follow_status'] = '成約'
                base['sales_owner_name'] = '鈴木 次郎'
            elif index % 6 == 4:
                base['follow_status'] = '見送り'
                base['sales_owner_name'] = '佐々木 明'
            else:
                base['follow_status'] = '未対応'
                base['sales_owner_name'] = ''

            latest_assessments.append(base)

        calendar_events = [
            {'summary': '東京店 朝会', 'start': now.strftime('%m/%d 09:30'), 'location': 'Google Meet'},
            {'summary': '商談レビュー会', 'start': now.strftime('%m/%d 13:00'), 'location': '本社会議室A'},
            {'summary': '週次KPI確認', 'start': now.strftime('%m/%d 17:00'), 'location': 'Google Meet'},
        ]

        return {
            'current_user_display_name': '山田 太郎',
            'monthly_kpis': {
                'month_label': now.strftime('%Y年%m月'),
                'appointments': 21,
                'contracts': 8,
                'close_rate': 38.1,
                'mq': 25,
            },
            'recent_appointment_updates': recent_appointment_updates,
            'recent_closed_updates': recent_closed_updates,
            'closed_rankings': closed_rankings,
            'store_performance_summary': store_performance_summary,
            'latest_assessments': latest_assessments,
            'calendar_events': calendar_events,
        }
