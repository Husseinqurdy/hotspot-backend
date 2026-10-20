"""Hesabu za moja kwa moja. Rekodi zilizofutwa (voided) hazihesabiwi kamwe."""
from decimal import Decimal
from django.db.models import Sum, Q
from django.db.models.functions import TruncMonth
from .models import Entry, Site

Z = Decimal('0')


def _sum(qs, kind):
    return qs.filter(kind=kind).aggregate(t=Sum('amount'))['t'] or Z


def totals(qs_flow, qs_stock):
    """qs_flow: rekodi za kipindi (mapato/matumizi). qs_stock: zote hadi tarehe ya mwisho."""
    income, expense = _sum(qs_flow, Entry.INCOME), _sum(qs_flow, Entry.EXPENSE)
    assets, liab = _sum(qs_stock, Entry.ASSET), _sum(qs_stock, Entry.LIABILITY)
    loans = _sum(qs_stock, Entry.LOAN) - _sum(qs_stock, Entry.LOAN_PAYMENT)
    return {
        'income': income, 'expense': expense, 'profit': income - expense,
        'assets': assets, 'liabilities': liab, 'loans_outstanding': loans,
        'equity': assets - liab - loans,   # assets = liabilities + mikopo + mtaji
    }


def scoped(site, date_from, date_to):
    base = Entry.objects.filter(voided=False)
    if site == 'company':
        base = base.filter(site__isnull=True)
    elif site:
        base = base.filter(site_id=site)
    flow, stock = base, base
    if date_from:
        flow = flow.filter(date__gte=date_from)
    if date_to:
        flow, stock = flow.filter(date__lte=date_to), stock.filter(date__lte=date_to)
    return flow, stock


def summary(site, date_from, date_to):
    flow, stock = scoped(site, date_from, date_to)
    out = totals(flow, stock)
    # kwa kila site (ikiwa hakuchagua site moja)
    rows = []
    if not site:
        for s in list(Site.objects.all()) + [None]:
            f, st = flow.filter(site=s), stock.filter(site=s)
            t = totals(f, st)
            if any(t.values()):
                rows.append({'site': s.name if s else 'Kampuni nzima', **t})
    months = (flow.filter(kind__in=[Entry.INCOME, Entry.EXPENSE])
              .annotate(m=TruncMonth('date')).values('m', 'kind').annotate(t=Sum('amount')).order_by('m'))
    series = {}
    for r in months:
        k = r['m'].strftime('%Y-%m')
        series.setdefault(k, {'month': k, 'income': Z, 'expense': Z})[r['kind']] = r['t']
    cats = (flow.filter(kind__in=[Entry.INCOME, Entry.EXPENSE]).values('kind', 'category')
            .annotate(t=Sum('amount')).order_by('-t'))
    by_category = [{'kind': c['kind'], 'category': c['category'] or 'Bila kundi', 'total': c['t']} for c in cats]
    return {**out, 'by_site': rows, 'by_month': list(series.values()), 'by_category': by_category}


def loan_balance(loan):
    paid = loan.payments.filter(voided=False).aggregate(t=Sum('amount'))['t'] or Z
    return loan.amount - paid
