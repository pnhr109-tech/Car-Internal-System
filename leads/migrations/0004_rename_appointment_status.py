from django.db import migrations, models


def forwards(apps, schema_editor):
    CarAssessmentRequest = apps.get_model('leads', 'CarAssessmentRequest')
    CarAssessmentRequest.objects.filter(follow_status='商談アポ獲得').update(follow_status='商談確定')


def backwards(apps, schema_editor):
    CarAssessmentRequest = apps.get_model('leads', 'CarAssessmentRequest')
    CarAssessmentRequest.objects.filter(follow_status='商談確定').update(follow_status='商談アポ獲得')


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0003_carassessmentrequest_sales_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='carassessmentrequest',
            name='follow_status',
            field=models.CharField(
                choices=[
                    ('未対応', '未対応'),
                    ('不通', '不通'),
                    ('再コール予定', '再コール予定'),
                    ('商談確定', '商談確定'),
                    ('成約', '成約'),
                    ('見送り', '見送り'),
                ],
                default='未対応',
                max_length=30,
                verbose_name='対応ステータス',
            ),
        ),
        migrations.RunPython(forwards, backwards),
    ]
