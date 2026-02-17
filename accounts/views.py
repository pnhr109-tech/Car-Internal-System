from django.conf import settings
from django.contrib.auth import get_user_model, login, logout
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_POST
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token


@require_GET
def google_login_page(request):
    if request.user.is_authenticated:
        return redirect(settings.LOGIN_REDIRECT_URL)

    return render(request, 'accounts/google_login.html', {
        'google_client_id': settings.GOOGLE_CLIENT_ID,
        'allowed_domain': settings.ALLOWED_GOOGLE_DOMAIN,
    })


@require_POST
def google_login(request):
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
    return JsonResponse({'success': True, 'redirect': settings.LOGIN_REDIRECT_URL})


@require_GET
def logout_view(request):
    logout(request)
    return redirect(settings.LOGOUT_REDIRECT_URL)
