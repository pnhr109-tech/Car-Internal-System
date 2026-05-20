from django import template

register = template.Library()


@register.filter
def step_done(process, step_key):
    """SalesProcess の指定ステップが完了しているか返す。
    例: process|step_done:"document" → process.document_done
    """
    return getattr(process, f'{step_key}_done', False)
