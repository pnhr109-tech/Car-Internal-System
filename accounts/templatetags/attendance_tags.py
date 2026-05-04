from django import template

register = template.Library()


@register.filter
def minutes_to_hm(value):
    """分（int）を 'Xh Ym' 形式の文字列に変換"""
    try:
        value = int(value)
    except (TypeError, ValueError):
        return '-'
    if value <= 0:
        return '-'
    h = value // 60
    m = value % 60
    return f'{h}時間{m:02d}分'
