from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
import logging

from .models import LoginActivity


logger = logging.getLogger(__name__)


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
