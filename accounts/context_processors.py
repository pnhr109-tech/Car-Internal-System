from django.utils import timezone

from .models import LoginActivity


def internal_nav_context(request):
    if not request.user.is_authenticated:
        return {
            'attendance_login_at_iso': '',
            'attendance_login_at_label': '-',
            'attendance_work_minutes': 0,
            'attendance_is_clocked_out': False,
        }

    today = timezone.localdate(timezone.now())
    today_session = LoginActivity.objects.filter(
        user=request.user,
        work_date=today,
    ).order_by('login_at').first()

    if not today_session:
        return {
            'attendance_login_at_iso': '',
            'attendance_login_at_label': '-',
            'attendance_work_minutes': 0,
            'attendance_is_clocked_out': False,
        }

    login_at_local = timezone.localtime(today_session.login_at)
    is_clocked_out = bool(today_session.logout_at)
    if is_clocked_out:
        worked_minutes = today_session.work_minutes
    else:
        now = timezone.now()
        worked_minutes = max(int((now - today_session.login_at).total_seconds() // 60), 0)

    return {
        'attendance_login_at_iso': login_at_local.isoformat(),
        'attendance_login_at_label': login_at_local.strftime('%Y-%m-%d %H:%M'),
        'attendance_work_minutes': worked_minutes,
        'attendance_is_clocked_out': is_clocked_out,
    }
