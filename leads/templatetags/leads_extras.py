from django import template

register = template.Library()


@register.filter
def ja_name(user):
    """姓名順（日本語）でフルネームを返す。未設定時は username にフォールバック。"""
    if user is None:
        return ''
    last = getattr(user, 'last_name', '') or ''
    first = getattr(user, 'first_name', '') or ''
    full = f'{last} {first}'.strip()
    return full if full else (getattr(user, 'username', '') or '')


@register.filter
def step_done(process, step_key):
    """SalesProcess の指定ステップが完了しているか返す。
    例: process|step_done:"document" → process.document_done
    """
    return getattr(process, f'{step_key}_done', False)
