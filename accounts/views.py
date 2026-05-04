import calendar as _cal
import datetime
import logging
from collections import defaultdict

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from .models import LoginActivity, Store, UserProfile


logger = logging.getLogger(__name__)

User = get_user_model()


def _require_non_general(request):
    """一般社員以外の権限チェック。一般社員の場合は HttpResponseForbidden を返す"""
    if request.user.is_superuser:
        return None
    profile = getattr(request.user, 'profile', None)
    if profile and profile.role != UserProfile.ROLE_GENERAL:
        return None
    return HttpResponseForbidden('この機能にはサブリーダー以上の権限が必要です')


@require_GET
def google_login_page(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    login_uri = request.build_absolute_uri('/login/google/')

    return render(request, 'accounts/google_login.html', {
        'google_client_id': settings.GOOGLE_CLIENT_ID,
        'allowed_domain': settings.ALLOWED_GOOGLE_DOMAIN,
        'login_uri': login_uri,
    })


@csrf_exempt
@require_POST
def google_login(request):
    g_csrf_cookie = request.COOKIES.get('g_csrf_token', '').strip()
    g_csrf_body = request.POST.get('g_csrf_token', '').strip()
    if not g_csrf_cookie or not g_csrf_body or g_csrf_cookie != g_csrf_body:
        return HttpResponse('CSRF検証に失敗しました', status=400)

    credential = request.POST.get('credential', '').strip()

    if not settings.GOOGLE_CLIENT_ID:
        return HttpResponse('GOOGLE_CLIENT_ID が未設定です', status=500)

    if not credential:
        return HttpResponse('Google認証情報がありません', status=400)

    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except Exception:
        return HttpResponse('Googleトークンの検証に失敗しました', status=401)

    email = idinfo.get('email', '').lower()
    email_verified = idinfo.get('email_verified', False)
    hosted_domain = idinfo.get('hd', '').lower()
    allowed_domain = settings.ALLOWED_GOOGLE_DOMAIN.lower()

    is_allowed_domain = email.endswith(f'@{allowed_domain}')
    if hosted_domain:
        is_allowed_domain = is_allowed_domain and hosted_domain == allowed_domain

    if not email or not email_verified or not is_allowed_domain:
        return HttpResponse('gigicompanyのアカウントのみログイン可能です', status=403)

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username=email,
        defaults={
            'email': email,
            'first_name': idinfo.get('given_name', ''),
            'last_name': idinfo.get('family_name', ''),
            'is_active': True,
        }
    )

    if not user.is_active:
        return HttpResponse('このアカウントは無効化されています', status=403)

    updated = False
    if not user.first_name and idinfo.get('given_name'):
        user.first_name = idinfo.get('given_name')
        updated = True
    if not user.last_name and idinfo.get('family_name'):
        user.last_name = idinfo.get('family_name')
        updated = True
    if not user.email:
        user.email = email
        updated = True
    if updated:
        user.save(update_fields=['first_name', 'last_name', 'email'])

    login(request, user)

    now = timezone.now()
    today = timezone.localdate(now)
    today_session = LoginActivity.objects.filter(
        user=user,
        work_date=today,
    ).order_by('login_at').first()

    if not today_session:
        LoginActivity.objects.create(
            user=user,
            work_date=today,
            login_at=now,
        )
    else:
        logger.info(f'Today login activity exists for user={user.username}, reuse existing record')

    return redirect(settings.LOGIN_REDIRECT_URL)


@require_GET
def logout_view(request):
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


@require_GET
def clock_out_view(request):
    if request.user.is_authenticated:
        today = timezone.localdate(timezone.now())
        open_session = LoginActivity.objects.filter(
            user=request.user,
            work_date=today,
            logout_at__isnull=True,
        ).order_by('login_at').first()
        if open_session:
            open_session.close_session(timezone.now())

    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)


# ---------------------------------------------------------------------------
# 社員管理
# ---------------------------------------------------------------------------

@login_required
@require_GET
def employee_list(request):
    denied = _require_non_general(request)
    if denied:
        return denied

    q_name            = request.GET.get('q_name', '').strip()
    q_email           = request.GET.get('q_email', '').strip()
    q_employee_number = request.GET.get('q_employee_number', '').strip()
    f_store           = request.GET.get('f_store', '').strip()
    f_role            = request.GET.get('f_role', '').strip()
    f_active          = request.GET.get('f_active', '').strip()

    qs = (
        UserProfile.objects
        .select_related('user', 'store')
        .order_by('store__id', 'employee_number', 'user__last_name')
    )
    if q_name:
        qs = qs.filter(
            Q(user__first_name__icontains=q_name) | Q(user__last_name__icontains=q_name)
        )
    if q_email:
        qs = qs.filter(user__email__icontains=q_email)
    if q_employee_number:
        qs = qs.filter(employee_number__icontains=q_employee_number)
    if f_store:
        qs = qs.filter(store_id=f_store)
    if f_role:
        qs = qs.filter(role=f_role)
    if f_active == '1':
        qs = qs.filter(is_active_employee=True)
    elif f_active == '0':
        qs = qs.filter(is_active_employee=False)

    stores = Store.objects.filter(is_active=True).order_by('id')
    total_count = qs.count()
    paginator = Paginator(qs, 30)
    page_obj = paginator.get_page(request.GET.get('page', 1))
    return render(request, 'accounts/employee_list.html', {
        'page_obj': page_obj,
        'total_count': total_count,
        'stores': stores,
        'role_choices': UserProfile.ROLE_CHOICES,
        'q_name': q_name,
        'q_email': q_email,
        'q_employee_number': q_employee_number,
        'f_store': f_store,
        'f_role': f_role,
        'f_active': f_active,
    })


@login_required
def employee_create(request):
    denied = _require_non_general(request)
    if denied:
        return denied

    stores = Store.objects.filter(is_active=True).order_by('id')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        employee_number = request.POST.get('employee_number', '').strip()
        store_id = request.POST.get('store_id') or None
        role = request.POST.get('role', UserProfile.ROLE_GENERAL)

        errors = []
        if not last_name:
            errors.append('姓は必須です')
        if not first_name:
            errors.append('名は必須です')
        if not email:
            errors.append('メールアドレスは必須です')
        elif User.objects.filter(username=email).exists():
            errors.append('このメールアドレスはすでに登録されています')
        if role not in dict(UserProfile.ROLE_CHOICES):
            errors.append('ロールが不正です')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/employee_form.html', {
                'stores': stores,
                'role_choices': UserProfile.ROLE_CHOICES,
                'form_data': request.POST,
                'is_edit': False,
            })

        user = User.objects.create(
            username=email,
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        UserProfile.objects.create(
            user=user,
            store_id=store_id,
            role=role,
            employee_number=employee_number,
        )
        messages.success(request, f'{last_name} {first_name} さんを登録しました')
        return redirect('accounts:employee_list')

    return render(request, 'accounts/employee_form.html', {
        'stores': stores,
        'role_choices': UserProfile.ROLE_CHOICES,
        'form_data': {},
        'is_edit': False,
    })


@login_required
def employee_edit(request, pk):
    denied = _require_non_general(request)
    if denied:
        return denied

    profile = get_object_or_404(UserProfile.objects.select_related('user', 'store'), pk=pk)
    stores = Store.objects.filter(is_active=True).order_by('id')

    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip().lower()
        employee_number = request.POST.get('employee_number', '').strip()
        store_id = request.POST.get('store_id') or None
        role = request.POST.get('role', UserProfile.ROLE_GENERAL)
        is_active_employee = request.POST.get('is_active_employee') == 'on'

        errors = []
        if not last_name:
            errors.append('姓は必須です')
        if not first_name:
            errors.append('名は必須です')
        if not email:
            errors.append('メールアドレスは必須です')
        elif User.objects.filter(username=email).exclude(pk=profile.user_id).exists():
            errors.append('このメールアドレスはすでに登録されています')
        if role not in dict(UserProfile.ROLE_CHOICES):
            errors.append('ロールが不正です')

        if errors:
            for e in errors:
                messages.error(request, e)
            return render(request, 'accounts/employee_form.html', {
                'stores': stores,
                'role_choices': UserProfile.ROLE_CHOICES,
                'profile': profile,
                'form_data': request.POST,
                'is_edit': True,
            })

        user = profile.user
        user.first_name = first_name
        user.last_name = last_name
        user.email = email
        user.username = email
        user.save(update_fields=['first_name', 'last_name', 'email', 'username'])

        profile.store_id = store_id
        profile.role = role
        profile.employee_number = employee_number
        profile.is_active_employee = is_active_employee
        profile.save(update_fields=['store_id', 'role', 'employee_number', 'is_active_employee', 'updated_at'])

        messages.success(request, f'{last_name} {first_name} さんの情報を更新しました')
        return redirect('accounts:employee_list')

    return render(request, 'accounts/employee_form.html', {
        'stores': stores,
        'role_choices': UserProfile.ROLE_CHOICES,
        'profile': profile,
        'form_data': {},
        'is_edit': True,
    })


@login_required
@require_POST
def employee_delete(request, pk):
    denied = _require_non_general(request)
    if denied:
        return denied

    profile = get_object_or_404(UserProfile.objects.select_related('user'), pk=pk)
    name = profile.user.get_full_name() or profile.user.username
    profile.user.delete()
    messages.success(request, f'{name} を削除しました')
    return redirect('accounts:employee_list')


# ---------------------------------------------------------------------------
# 勤怠管理
# ---------------------------------------------------------------------------

_WEEKDAY_JA = ['月', '火', '水', '木', '金', '土', '日']
_OVERTIME_CUTOFF_MINUTES = 18 * 60  # 18:00
_LUNCH_MINUTES = 60


def _parse_year_month(request):
    """GETパラメータから year/month を取得。不正値は当月にフォールバック"""
    today = timezone.localdate(timezone.now())
    try:
        year = int(request.GET.get('year', today.year))
        month = int(request.GET.get('month', today.month))
        if not (1 <= month <= 12 and 2000 <= year <= 2100):
            raise ValueError
    except (ValueError, TypeError):
        year, month = today.year, today.month
    return year, month


def _prev_next_month(year, month):
    """前月・翌月の (year, month) を返す"""
    first = datetime.date(year, month, 1)
    prev = first - datetime.timedelta(days=1)
    nxt = (first.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return (prev.year, prev.month), (nxt.year, nxt.month)


def _calc_day_attendance(act):
    """LoginActivity 1件から (work_minutes, overtime_minutes) を計算する"""
    if not act or not act.logout_at:
        return 0, 0
    work_min = max(0, act.work_minutes - _LUNCH_MINUTES)
    logout_local = timezone.localtime(act.logout_at)
    lo_total = logout_local.hour * 60 + logout_local.minute
    overtime_min = max(0, lo_total - _OVERTIME_CUTOFF_MINUTES)
    return work_min, overtime_min


@login_required
@require_GET
def attendance_list(request):
    denied = _require_non_general(request)
    if denied:
        return denied

    year, month = _parse_year_month(request)
    (prev_year, prev_month), (next_year, next_month) = _prev_next_month(year, month)

    q_name            = request.GET.get('q_name', '').strip()
    q_employee_number = request.GET.get('q_employee_number', '').strip()
    f_store           = request.GET.get('f_store', '').strip()

    qs = (
        UserProfile.objects
        .select_related('user', 'store')
        .order_by('store__id', 'employee_number', 'user__last_name')
    )
    if q_name:
        qs = qs.filter(
            Q(user__first_name__icontains=q_name) | Q(user__last_name__icontains=q_name)
        )
    if q_employee_number:
        qs = qs.filter(employee_number__icontains=q_employee_number)
    if f_store:
        qs = qs.filter(store_id=f_store)

    profiles = list(qs)
    user_ids = [p.user_id for p in profiles]

    activities = LoginActivity.objects.filter(
        user_id__in=user_ids,
        work_date__year=year,
        work_date__month=month,
    )
    acts_by_user = defaultdict(list)
    for act in activities:
        acts_by_user[act.user_id].append(act)

    rows = []
    for profile in profiles:
        days = 0
        work_min = 0
        overtime_min = 0
        for act in acts_by_user[profile.user_id]:
            if act.logout_at:
                days += 1
                wm, ot = _calc_day_attendance(act)
                work_min += wm
                overtime_min += ot
        rows.append({
            'profile': profile,
            'days': days,
            'work_minutes': work_min,
            'overtime_minutes': overtime_min,
        })

    stores = Store.objects.filter(is_active=True).order_by('id')
    return render(request, 'accounts/attendance_list.html', {
        'rows': rows,
        'year': year,
        'month': month,
        'month_label': f'{year}年{month}月',
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'stores': stores,
        'q_name': q_name,
        'q_employee_number': q_employee_number,
        'f_store': f_store,
    })


@login_required
@require_GET
def attendance_detail(request, pk):
    denied = _require_non_general(request)
    if denied:
        return denied

    profile = get_object_or_404(UserProfile.objects.select_related('user', 'store'), pk=pk)
    year, month = _parse_year_month(request)
    (prev_year, prev_month), (next_year, next_month) = _prev_next_month(year, month)

    activities = LoginActivity.objects.filter(
        user=profile.user,
        work_date__year=year,
        work_date__month=month,
    ).order_by('work_date')
    act_map = {a.work_date: a for a in activities}

    num_days = _cal.monthrange(year, month)[1]
    days = []
    total_work_min = 0
    total_overtime_min = 0
    total_days = 0

    for d in range(1, num_days + 1):
        date = datetime.date(year, month, d)
        act = act_map.get(date)
        work_min, overtime_min = _calc_day_attendance(act)

        if act and act.logout_at:
            total_days += 1
            total_work_min += work_min
            total_overtime_min += overtime_min

        weekday = date.weekday()
        days.append({
            'date': date,
            'weekday_ja': _WEEKDAY_JA[weekday],
            'is_weekend': weekday >= 5,
            'login_at': timezone.localtime(act.login_at) if act else None,
            'logout_at': timezone.localtime(act.logout_at) if act and act.logout_at else None,
            'work_minutes': work_min,
            'overtime_minutes': overtime_min,
        })

    return render(request, 'accounts/attendance_detail.html', {
        'profile': profile,
        'year': year,
        'month': month,
        'month_label': f'{year}年{month}月',
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
        'days': days,
        'total_days': total_days,
        'total_work_minutes': total_work_min,
        'total_overtime_minutes': total_overtime_min,
    })


@login_required
@require_POST
def attendance_update_day(request, pk):
    import json

    denied = _require_non_general(request)
    if denied:
        return JsonResponse({'success': False, 'message': '権限がありません'}, status=403)

    profile = get_object_or_404(UserProfile.objects.select_related('user'), pk=pk)

    try:
        payload = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'message': 'リクエストが不正です'}, status=400)

    date_str       = payload.get('work_date', '')
    login_time_str = payload.get('login_time', '').strip()
    logout_time_str = payload.get('logout_time', '').strip()

    try:
        work_date = datetime.date.fromisoformat(date_str)
    except (ValueError, TypeError):
        return JsonResponse({'success': False, 'message': '日付が不正です'}, status=400)

    if not login_time_str:
        return JsonResponse({'success': False, 'message': '出勤時刻は必須です'}, status=400)

    try:
        lh, lm = map(int, login_time_str.split(':'))
        login_naive = datetime.datetime(work_date.year, work_date.month, work_date.day, lh, lm)
        login_dt = timezone.make_aware(login_naive)
    except (ValueError, AttributeError):
        return JsonResponse({'success': False, 'message': '出勤時刻の形式が不正です'}, status=400)

    logout_dt = None
    logout_naive = None
    raw_work_min = 0

    if logout_time_str:
        try:
            oh, om = map(int, logout_time_str.split(':'))
            logout_naive = datetime.datetime(work_date.year, work_date.month, work_date.day, oh, om)
            logout_dt = timezone.make_aware(logout_naive)
            if logout_dt <= login_dt:
                return JsonResponse({'success': False, 'message': '退勤時刻は出勤時刻より後にしてください'}, status=400)
            raw_work_min = int((logout_dt - login_dt).total_seconds() // 60)
        except (ValueError, AttributeError):
            return JsonResponse({'success': False, 'message': '退勤時刻の形式が不正です'}, status=400)

    act = LoginActivity.objects.filter(user=profile.user, work_date=work_date).first()
    if act:
        act.login_at = login_dt
        act.logout_at = logout_dt
        act.work_minutes = raw_work_min
        act.save(update_fields=['login_at', 'logout_at', 'work_minutes', 'updated_at'])
    else:
        act = LoginActivity.objects.create(
            user=profile.user,
            work_date=work_date,
            login_at=login_dt,
            logout_at=logout_dt,
            work_minutes=raw_work_min,
        )

    display_work_min, display_overtime_min = _calc_day_attendance(act)

    return JsonResponse({
        'success': True,
        'message': '更新しました',
        'work_minutes': display_work_min,
        'overtime_minutes': display_overtime_min,
        'login_time': login_naive.strftime('%H:%M'),
        'logout_time': logout_naive.strftime('%H:%M') if logout_naive else '',
    })
