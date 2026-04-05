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

        recent_sale_updates = [
            {
                'customer_name': '小川 俊介',
                'status_updated_at': now - timedelta(hours=2, minutes=11),
                'sales_owner_name': '山田 太郎',
                'application_number': 'N-202603-2201',
            },
            {
                'customer_name': '村上 里奈',
                'status_updated_at': now - timedelta(hours=4, minutes=2),
                'sales_owner_name': '鈴木 次郎',
                'application_number': 'S-202603-2202',
            },
            {
                'customer_name': '田中 翼',
                'status_updated_at': now - timedelta(hours=6, minutes=18),
                'sales_owner_name': '佐々木 明',
                'application_number': 'H-202603-2203',
            },
        ]

        closed_rankings = [
            {'sales_owner_name': '山田 太郎', 'closed_count': 12},
            {'sales_owner_name': '鈴木 次郎', 'closed_count': 10},
            {'sales_owner_name': '佐々木 明', 'closed_count': 8},
        ]

        mq_rankings = [
            {'sales_owner_name': '山田 太郎', 'mq_count': 18},
            {'sales_owner_name': '鈴木 次郎', 'mq_count': 15},
            {'sales_owner_name': '佐々木 明', 'mq_count': 11},
        ]

        store_performance_summary = [
            {
                'store': 'つくば',
                'mq': 22,
                'appointments': 18,
                'contracts': 8,
                'close_rate': 44.4,
                'cc_appointments': 5,
                'self_cc_ratio': '75%：25%',
                'managed_count': 18,
                'lost_count': 3,
                'pre_assessment_cancel_count': 1,
            },
            {
                'store': '水戸',
                'mq': 16,
                'appointments': 13,
                'contracts': 5,
                'close_rate': 38.5,
                'cc_appointments': 3,
                'self_cc_ratio': '75%：25%',
                'managed_count': 13,
                'lost_count': 2,
                'pre_assessment_cancel_count': 1,
            },
            {
                'store': '小山',
                'mq': 14,
                'appointments': 11,
                'contracts': 4,
                'close_rate': 36.4,
                'cc_appointments': 3,
                'self_cc_ratio': '75%：25%',
                'managed_count': 11,
                'lost_count': 2,
                'pre_assessment_cancel_count': 0,
            },
        ]

        assessment_seed = [
            {
                'sales_owner_name': '山田 太郎',
                'follow_status': '商談確定',
                'customer_name': '佐藤 一郎',
                'phone_number': '090-1111-2222',
                'call_count': 3,
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
                'call_count': 1,
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
                'call_count': 4,
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
                'call_count': 2,
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
                'call_count': 0,
                'desired_sale_timing': '2ヶ月以内',
                'maker': 'スバル',
                'car_model': 'レヴォーグ',
                'year': '2021',
                'mileage': '15,000km',
                'address': '大阪府吹田市',
            },
        ]

        latest_assessments = []
        channels = ['N', 'S', 'H', 'M', 'C']
        for index in range(180):
            base = assessment_seed[index % len(assessment_seed)].copy()
            channel = channels[index % len(channels)]
            base['application_number'] = f"{channel}-202603-{1001 + index:04d}"
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
                'period_label': now.strftime('%Y年%m月'),
                'appointments': 21,
                'contracts': 8,
                'close_rate': 38.1,
                'self_cc_ratio': '75%：25%',
                'cc_appointments': 5,
                'mq': 25,
                'managed_count': 25,
                'lost_count': 4,
                'pre_assessment_cancel_count': 2,
            },
            'period_kpis': {
                'year': {
                    'period_label': now.strftime('%Y年'),
                    'appointments': 168,
                    'contracts': 62,
                    'close_rate': 36.9,
                    'self_cc_ratio': '75%：25%',
                    'mq': 210,
                    'managed_count': 210,
                    'lost_count': 31,
                    'pre_assessment_cancel_count': 17,
                },
                'month': {
                    'period_label': now.strftime('%Y年%m月'),
                    'appointments': 21,
                    'contracts': 8,
                    'close_rate': 38.1,
                    'self_cc_ratio': '75%：25%',
                    'mq': 25,
                    'managed_count': 25,
                    'lost_count': 4,
                    'pre_assessment_cancel_count': 2,
                },
                'week': {
                    'period_label': f"{now.month}月第{((now.day - 1) // 7) + 1}週",
                    'appointments': 7,
                    'contracts': 3,
                    'close_rate': 42.9,
                    'self_cc_ratio': '75%：25%',
                    'mq': 9,
                    'managed_count': 9,
                    'lost_count': 1,
                    'pre_assessment_cancel_count': 1,
                },
            },
            'recent_appointment_updates': recent_appointment_updates,
            'recent_closed_updates': recent_closed_updates,
            'recent_sale_updates': recent_sale_updates,
            'closed_rankings': closed_rankings,
            'mq_rankings': mq_rankings,
            'store_performance_summary': store_performance_summary,
            'latest_assessments': latest_assessments,
            'calendar_events': calendar_events,
        }
