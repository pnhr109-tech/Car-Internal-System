from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0018_assessment_system_import'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='carassessmentrequest',
            name='gmail_message',
        ),
        migrations.DeleteModel(
            name='GmailMessage',
        ),
    ]
