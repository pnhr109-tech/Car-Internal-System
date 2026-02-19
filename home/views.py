from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.http import JsonResponse

from leads.models import CarAssessmentRequest
from .services import (
    get_latest_assessments,
    get_upcoming_calendar_events,
    get_recent_chat_messages,
)


@login_required
@require_GET
def dashboard(request):
    current_user_display_name = request.user.get_full_name().strip() or request.user.username
    latest_assessments = get_latest_assessments(limit=100)
    return render(request, 'home/dashboard.html', {
        'latest_assessments': latest_assessments,
        'current_user_display_name': current_user_display_name,
        'follow_status_choices': [choice[0] for choice in CarAssessmentRequest.FOLLOW_STATUS_CHOICES],
    })


@login_required
@require_GET
def calendar_events_api(request):
    result = get_upcoming_calendar_events(limit=10)
    return JsonResponse(result)


@login_required
@require_GET
def chat_messages_api(request):
    result = get_recent_chat_messages(limit_spaces=3, messages_per_space=3)
    return JsonResponse(result)


@csrf_exempt
@require_http_methods(['GET', 'POST'])
def google_chat_webhook(request):
    return JsonResponse({'text': 'ok', 'status': 'ready'})
