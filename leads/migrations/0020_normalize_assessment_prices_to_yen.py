"""
0020 — assessment_price / market_price を円単位に統一

従来は万円単位での入力フォームを使っていたため、多くのレコードが万単位で保存されている。
ただし一部のレコードはすでに円単位で保存されているため、
10,000 未満の値（＝明らかに万単位）のみ 10,000 倍して円単位に変換する。
10,000 以上の値はすでに円単位とみなして変更しない。
"""

from django.db import migrations


def normalize_to_yen(apps, schema_editor):
    Assessment = apps.get_model('leads', 'Assessment')
    rows = Assessment.objects.filter(assessment_price__isnull=False, assessment_price__lt=10000)
    for obj in rows:
        if obj.assessment_price is not None and obj.assessment_price < 10000:
            obj.assessment_price = obj.assessment_price * 10000
        if obj.market_price is not None and obj.market_price < 10000:
            obj.market_price = obj.market_price * 10000
        obj.save(update_fields=['assessment_price', 'market_price'])

    # market_price だけ < 10000 のケースも拾う
    rows2 = Assessment.objects.filter(
        assessment_price__isnull=True,
        market_price__isnull=False,
        market_price__lt=10000,
    )
    for obj in rows2:
        obj.market_price = obj.market_price * 10000
        obj.save(update_fields=['market_price'])


def denormalize_to_man(apps, schema_editor):
    Assessment = apps.get_model('leads', 'Assessment')
    rows = Assessment.objects.filter(assessment_price__isnull=False, assessment_price__gte=10000)
    for obj in rows:
        if obj.assessment_price is not None and obj.assessment_price >= 10000:
            obj.assessment_price = obj.assessment_price // 10000
        if obj.market_price is not None and obj.market_price >= 10000:
            obj.market_price = obj.market_price // 10000
        obj.save(update_fields=['assessment_price', 'market_price'])


class Migration(migrations.Migration):

    dependencies = [
        ('leads', '0019_remove_gmail_message'),
    ]

    operations = [
        migrations.RunPython(normalize_to_yen, reverse_code=denormalize_to_man),
    ]
