from django.db import migrations


def forwards(apps, schema_editor):
    CarAssessmentRequest = apps.get_model('leads', 'CarAssessmentRequest')
    CarAssessmentRequest.objects.filter(follow_status='商談確定').update(follow_status='商談予定')


def backwards(apps, schema_editor):
    CarAssessmentRequest = apps.get_model('leads', 'CarAssessmentRequest')
    CarAssessmentRequest.objects.filter(follow_status='商談予定').update(follow_status='商談確定')


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0015_fix_external_id_index_remove_constraint'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
        migrations.AlterField(
            model_name='carassessmentrequest',
            name='follow_status',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                choices=[
                    ('未対応', '未対応'),
                    ('不通', '不通'),
                    ('即ぷ', '即ぷ'),
                    ('再コール予定', '再コール予定'),
                    ('商談予定', '商談予定'),
                    ('商談昇格済', '商談昇格済'),
                    ('成約', '成約'),
                    ('見送り', '見送り'),
                ],
                default='未対応',
                max_length=30,
                verbose_name='対応ステータス',
            ),
        ),
    ]
