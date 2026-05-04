"""
views/vehicle.py — 成約済み車両一覧・CSV出力
"""
import csv
import logging
import urllib.parse
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render

from ..models import Assessment

logger = logging.getLogger(__name__)


def _parse_search_params(request):
    """GET パラメータから検索条件を取り出す。日付はキーが無い場合のみデフォルトを使う。"""
    today        = date.today()
    try:
        one_year_ago = today.replace(year=today.year - 1)
    except ValueError:
        one_year_ago = today - timedelta(days=365)

    maker          = request.GET.get('maker',          '').strip()
    car_model      = request.GET.get('car_model',      '').strip()
    chassis_number = request.GET.get('chassis_number', '').strip()
    customer_name  = request.GET.get('customer_name',  '').strip()

    # 初回アクセス（date_from キー自体が無い）はデフォルト値を使う
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
    qs = (
        Assessment.objects
        .select_related('vehicle', 'customer', 'assigned_to', 'contract')
        .filter(status=Assessment.STATUS_CONTRACTED)
        .order_by('-updated_at')
    )

    profile = getattr(request.user, 'profile', None)
    if profile and not profile.has_global_access:
        if profile.role == profile.ROLE_GENERAL:
            qs = qs.filter(assigned_to=request.user)
        else:
            store_users = (
                profile.store.members.values_list('user_id', flat=True)
                if profile.store else []
            )
            qs = qs.filter(assigned_to__in=store_users)

    if maker:
        qs = qs.filter(vehicle__maker__icontains=maker)
    if car_model:
        qs = qs.filter(vehicle__car_model__icontains=car_model)
    if chassis_number:
        qs = qs.filter(vehicle__chassis_number__icontains=chassis_number)
    if customer_name:
        qs = qs.filter(customer__name__icontains=customer_name)
    if date_from:
        qs = qs.filter(contract__contract_date__gte=date_from)
    if date_to:
        qs = qs.filter(contract__contract_date__lte=date_to)

    return qs


@login_required
def vehicle_list(request):
    """成約済み車両一覧"""
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
    })


@login_required
def vehicle_list_csv(request):
    """成約済み車両一覧 CSV ダウンロード"""
    maker, car_model, chassis_number, customer_name, date_from, date_to = _parse_search_params(request)
    qs = _build_vehicle_qs(request, maker, car_model, chassis_number, customer_name, date_from, date_to)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = 'attachment; filename="vehicle_list.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'メーカー', '車種', '年式', '走行距離', 'カラー', '車体番号',
        '顧客名', '担当者', '成約日', '買取金額（税込）',
    ])

    for a in qs:
        v = a.vehicle
        try:
            contract       = a.contract
            contract_date  = str(contract.contract_date) if contract.contract_date else ''
            purchase_price = str(int(contract.purchase_price_incl_tax)) if contract.purchase_price_incl_tax else ''
        except Exception:
            contract_date  = ''
            purchase_price = ''

        writer.writerow([
            v.maker,
            v.car_model,
            v.year,
            v.mileage,
            v.color,
            v.chassis_number,
            a.customer.name,
            a.assigned_to.get_full_name() or a.assigned_to.username,
            contract_date,
            purchase_price,
        ])

    return response
