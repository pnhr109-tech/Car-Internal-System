from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0004_rename_appointment_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='carassessmentrequest',
            name='call_count',
            field=models.PositiveIntegerField(default=0, verbose_name='通話数'),
        ),
    ]
