from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginActivity',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('work_date', models.DateField(db_index=True, verbose_name='勤務日')),
                ('login_at', models.DateTimeField(db_index=True, verbose_name='出勤時刻')),
                ('logout_at', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='退勤時刻')),
                ('work_minutes', models.PositiveIntegerField(default=0, verbose_name='勤務時間（分）')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='作成日時')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新日時')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='login_activities', to=settings.AUTH_USER_MODEL, verbose_name='ユーザー')),
            ],
            options={
                'verbose_name': 'ログイン勤怠',
                'verbose_name_plural': 'ログイン勤怠',
                'db_table': 'login_activities',
                'ordering': ['-login_at'],
            },
        ),
        migrations.AddIndex(
            model_name='loginactivity',
            index=models.Index(fields=['user', 'work_date'], name='idx_login_act_user_date'),
        ),
        migrations.AddIndex(
            model_name='loginactivity',
            index=models.Index(fields=['user', 'logout_at'], name='idx_login_act_user_out'),
        ),
    ]
