"""
views/vehicle.py — 車両一覧（案件連携 + 手動登録）・CSV出力
"""
import csv
import json
import logging
import urllib.parse
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import (
    CharField, DateField, DecimalField, F, IntegerField, Q, Subquery, OuterRef,
)
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import Assessment, PurchaseContract, Vehicle

logger = logging.getLogger(__name__)


def _parse_search_params(request):
    today = date.today()
    try:
        one_year_ago = today.replace(year=today.year - 1)
    except ValueError:
        one_year_ago = today - timedelta(days=365)

    maker          = request.GET.get('maker',          '').strip()
    car_model      = request.GET.get('car_model',      '').strip()
    chassis_number = request.GET.get('chassis_number', '').strip()
    customer_name  = request.GET.get('customer_name',  '').strip()

    date_from = (
        request.GET['date_from'].strip()
        if 'date_from' in request.GET
        else one_year_ago.isoformat()
    )
    date_to = (
        request.GET['date_to'].strip()
        if 'date_to' in request.GET
        else today.isoformat()
    )

    return maker, car_model, chassis_number, customer_name, date_from, date_to


def _build_vehicle_qs(request, maker, car_model, chassis_number, customer_name, date_from, date_to):
    """
    Vehicle を主軸に、成約済み案件の顧客名・契約日・買取金額をアノテーション。
    手動登録車両（案件なし）も含む。
    """
    contracted_assessment_sq = (
        Assessment.objects
        .filter(vehicle_id=OuterRef('pk'), status=Assessment.STATUS_CONTRACTED)
        .order_by('-created_at')
    )

    qs = Vehicle.objects.annotate(
        assessment_pk=Subquery(
            contracted_assessment_sq.values('pk')[:1],
            output_field=IntegerField(),
        ),
        ann_customer_name=Subquery(
            contracted_assessment_sq.values('customer__name')[:1],
            output_field=CharField(max_length=200),
        ),
        ann_assigned_last=Subquery(
            contracted_assessment_sq.values('assigned_to__last_name')[:1],
            output_field=CharField(max_length=50),
        ),
        ann_assigned_first=Subquery(
            contracted_assessment_sq.values('assigned_to__first_name')[:1],
            output_field=CharField(max_length=50),
        ),
        ann_contract_date=Subquery(
            PurchaseContract.objects
            .filter(assessment__vehicle_id=OuterRef('pk'))
            .values('contract_date')[:1],
            output_field=DateField(),
        ),
        ann_purchase_price=Subquery(
            PurchaseContract.objects
            .filter(assessment__vehicle_id=OuterRef('pk'))
            .values('purchase_price_incl_tax')[:1],
            output_field=DecimalField(max_digits=12, decimal_places=0),
        ),
    )

    # ロールによるアクセス制御（案件連携車両のみ絞り込み。手動登録は全員閲覧可）
    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_global_access:
        if profile.role == profile.ROLE_GENERAL:
            qs = qs.filter(
                Q(assessment_pk__isnull=True)  # 手動登録
                | Q(assessments__assigned_to=request.user, assessments__status=Assessment.STATUS_CONTRACTED)
            ).distinct()
        else:
            store_users = (
                profile.store.members.values_list('user_id', flat=True)
                if profile.store else []
            )
            qs = qs.filter(
                Q(assessment_pk__isnull=True)  # 手動登録
                | Q(assessments__assigned_to__in=store_users, assessments__status=Assessment.STATUS_CONTRACTED)
            ).distinct()

    if maker:
        qs = qs.filter(maker__icontains=maker)
    if car_model:
        qs = qs.filter(car_model__icontains=car_model)
    if chassis_number:
        qs = qs.filter(chassis_number__icontains=chassis_number)
    if customer_name:
        qs = qs.filter(ann_customer_name__icontains=customer_name)

    # 日付フィルタ：案件連携は契約日、手動登録は登録日で絞る
    if date_from:
        qs = qs.filter(
            Q(ann_contract_date__gte=date_from)
            | Q(ann_contract_date__isnull=True, created_at__date__gte=date_from)
        )
    if date_to:
        qs = qs.filter(
            Q(ann_contract_date__lte=date_to)
            | Q(ann_contract_date__isnull=True, created_at__date__lte=date_to)
        )

    return qs.order_by(
        F('ann_contract_date').desc(nulls_last=True),
        '-created_at',
    )


@login_required
def vehicle_list(request):
    """車両一覧（案件連携 + 手動登録）"""
    maker, car_model, chassis_number, customer_name, date_from, date_to = _parse_search_params(request)
    qs = _build_vehicle_qs(request, maker, car_model, chassis_number, customer_name, date_from, date_to)

    total_count = qs.count()
    paginator   = Paginator(qs, 50)
    page_obj    = paginator.get_page(request.GET.get('page', 1))

    search_qs = urllib.parse.urlencode({
        'maker':          maker,
        'car_model':      car_model,
        'chassis_number': chassis_number,
        'customer_name':  customer_name,
        'date_from':      date_from,
        'date_to':        date_to,
    })

    current_year  = date.today().year
    year_choices  = [f'{y}年' for y in range(current_year + 1, 1969, -1)]

    return render(request, 'leads/vehicle_list.html', {
        'page_obj':       page_obj,
        'total_count':    total_count,
        'maker':          maker,
        'car_model':      car_model,
        'chassis_number': chassis_number,
        'customer_name':  customer_name,
        'date_from':      date_from,
        'date_to':        date_to,
        'search_qs':      search_qs,
        'year_choices':   year_choices,
    })


@login_required
@require_POST
def vehicle_create(request):
    """手動登録車両 作成 API"""
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'success': False, 'message': 'リクエスト形式が不正です'}, status=400)

    maker     = payload.get('maker', '').strip()
    car_model = payload.get('car_model', '').strip()
    year      = payload.get('year', '').strip()
    mileage   = payload.get('mileage', '').strip()

    if not maker or not car_model:
        return JsonResponse({'success': False, 'message': 'メーカーと車種は必須です'}, status=400)

    inspection_expiry = None
    raw_expiry = payload.get('inspection_expiry', '').strip()
    if raw_expiry:
        from datetime import datetime
        try:
            inspection_expiry = datetime.strptime(raw_expiry, '%Y-%m-%d').date()
        except ValueError:
            pass

    vehicle = Vehicle.objects.create(
        maker=maker,
        car_model=car_model,
        year=year,
        mileage=mileage,
        grade=payload.get('grade', '').strip(),
        color=payload.get('color', '').strip(),
        displacement=payload.get('displacement', '').strip(),
        chassis_number=payload.get('chassis_number', '').strip(),
        inspection_expiry=inspection_expiry,
        registration_number=payload.get('registration_number', '').strip(),
        passenger_count=payload.get('passenger_count', '').strip(),
        body_type=payload.get('body_type', '').strip(),
        drive_type=payload.get('drive_type', '').strip(),
        remarks=payload.get('remarks', '').strip(),
        updated_by=request.user,
    )

    return JsonResponse({
        'success': True,
        'message': f'{vehicle} を登録しました',
        'vehicle_id': vehicle.pk,
    })


@login_required
def vehicle_list_csv(request):
    """車両一覧 CSV ダウンロード"""
    maker, car_model, chassis_number, customer_name, date_from, date_to = _parse_search_params(request)
    qs = _build_vehicle_qs(request, maker, car_model, chassis_number, customer_name, date_from, date_to)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="vehicle_list.csv"'

    writer = csv.writer(response)
    writer.writerow([
        '区分', 'メーカー', '車種', '年式', '走行距離', 'カラー', '車体番号',
        '顧客名', '担当者', '成約日', '買取金額（税込）',
    ])

    for v in qs:
        category     = '案件連携' if v.assessment_pk else '手動登録'
        customer     = v.ann_customer_name or ''
        assigned     = (
            f'{v.ann_assigned_last or ""}{v.ann_assigned_first or ""}'.strip()
            or ''
        )
        contract_date  = str(v.ann_contract_date) if v.ann_contract_date else ''
        purchase_price = str(int(v.ann_purchase_price)) if v.ann_purchase_price else ''

        writer.writerow([
            category,
            v.maker,
            v.car_model,
            v.year,
            v.mileage,
            v.color,
            v.chassis_number,
            customer,
            assigned,
            contract_date,
            purchase_price,
        ])

    return response
