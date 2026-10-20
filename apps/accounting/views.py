from datetime import date
from django.http import HttpResponse
from django.utils import timezone
from django.utils.dateparse import parse_date
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from . import calc
from .models import Site, Entry, AuditLog
from .serializers import SiteSerializer, EntrySerializer

TRACKED = ['site_id', 'kind', 'date', 'category', 'description', 'amount', 'interest_rate', 'loan_ref_id']


class IsSuperAdmin(BasePermission):
    message = 'Superadmin pekee.'

    def has_permission(self, request, view):
        u = request.user
        return bool(u and u.is_authenticated and u.is_superadmin())


def _plain(v):
    return None if v is None else (v if isinstance(v, (int, bool)) else str(v))


def snap(obj, fields):
    return {f: _plain(getattr(obj, f)) for f in fields}


def log(request, action, target='', site_name='', **detail):
    AuditLog.objects.create(user=request.user, username=request.user.username,
                            action=action, target=target, site_name=site_name, detail=detail)


def diff(before, after):
    return {k: {'kabla': before[k], 'baada': after[k]} for k in after if before.get(k) != after[k]}


def params(request):
    """site (id | 'company' | None), date_from, date_to — zinathibitishwa."""
    site = request.query_params.get('site') or None
    if site and site != 'company' and not site.isdigit():
        raise ValidationError({'site': 'Site si sahihi.'})
    out = []
    for k in ('date_from', 'date_to'):
        v = request.query_params.get(k)
        d = parse_date(v) if v else None
        if v and d is None:
            raise ValidationError({k: 'Tarehe si sahihi (YYYY-MM-DD).'})
        out.append(d)
    if out[0] and out[1] and out[0] > out[1]:
        raise ValidationError({'date_from': 'Tarehe ya kuanza iko baada ya ya mwisho.'})
    return site, out[0], out[1]


class SiteViewSet(viewsets.ModelViewSet):
    serializer_class = SiteSerializer
    permission_classes = [IsSuperAdmin]
    pagination_class = None
    queryset = Site.objects.all()
    http_method_names = ['get', 'post', 'patch', 'head', 'options']   # hakuna kufuta; zima kwa is_active

    def perform_create(self, s):
        o = s.save()
        log(self.request, 'site_create', f'site:{o.id}', o.name, after=snap(o, ['name', 'note', 'is_active']))

    def perform_update(self, s):
        before = snap(s.instance, ['name', 'note', 'is_active'])
        o = s.save()
        log(self.request, 'site_update', f'site:{o.id}', o.name, changes=diff(before, snap(o, ['name', 'note', 'is_active'])))


class EntryViewSet(viewsets.ModelViewSet):
    serializer_class = EntrySerializer
    permission_classes = [IsSuperAdmin]
    pagination_class = None
    http_method_names = ['get', 'post', 'patch', 'head', 'options']   # hakuna DELETE — tumia /void/

    def get_queryset(self):
        qs = Entry.objects.select_related('site', 'created_by', 'voided_by')
        site, df, dt = params(self.request)
        if site == 'company':
            qs = qs.filter(site__isnull=True)
        elif site:
            qs = qs.filter(site_id=site)
        q = self.request.query_params
        if q.get('kind'):
            qs = qs.filter(kind=q['kind'])
        if df:
            qs = qs.filter(date__gte=df)
        if dt:
            qs = qs.filter(date__lte=dt)
        if q.get('include_void') == '0':
            qs = qs.filter(voided=False)
        return qs

    def perform_create(self, s):
        o = s.save(created_by=self.request.user)
        log(self.request, 'create', f'entry:{o.id}', o.site.name if o.site_id else 'Kampuni nzima',
            kind=o.kind, after=snap(o, TRACKED))

    def perform_update(self, s):
        before = snap(s.instance, TRACKED)
        o = s.save()
        log(self.request, 'update', f'entry:{o.id}', o.site.name if o.site_id else 'Kampuni nzima',
            kind=o.kind, changes=diff(before, snap(o, TRACKED)))

    @action(detail=True, methods=['post'])
    def void(self, request, pk=None):
        o = self.get_object()
        reason = (request.data.get('reason') or '').strip()
        if not reason:
            raise ValidationError({'reason': 'Sababu inahitajika.'})
        if o.voided:
            raise ValidationError('Rekodi tayari imefutwa.')
        if o.kind == Entry.LOAN and o.payments.filter(voided=False).exists():
            raise ValidationError('Mkopo una marejesho. Futa marejesho kwanza.')
        o.voided, o.void_reason, o.voided_by, o.voided_at = True, reason, request.user, timezone.now()
        o.save()
        log(request, 'void', f'entry:{o.id}', o.site.name if o.site_id else 'Kampuni nzima',
            kind=o.kind, reason=reason, snapshot=snap(o, TRACKED))
        return Response(self.get_serializer(o).data)


class SummaryView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        site, df, dt = params(request)
        return Response(calc.summary(site, df, dt))


class LogView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        q = request.query_params
        qs = AuditLog.objects.all()
        if q.get('user'):
            qs = qs.filter(username=q['user'])
        if q.get('action'):
            qs = qs.filter(action=q['action'])
        if q.get('site'):
            qs = qs.filter(site_name=q['site'])
        _, df, dt = params(request)
        if df:
            qs = qs.filter(created_at__date__gte=df)
        if dt:
            qs = qs.filter(created_at__date__lte=dt)
        try:
            limit = min(int(q.get('limit', 300)), 2000)
        except ValueError:
            limit = 300
        rows = [{'id': l.id, 'username': l.username, 'action': l.action, 'target': l.target,
                 'site_name': l.site_name, 'detail': l.detail, 'created_at': l.created_at}
                for l in qs[:limit]]
        users = list(AuditLog.objects.order_by().values_list('username', flat=True).distinct())
        return Response({'results': rows, 'users': users})


class AccessView(APIView):
    """Frontend inaita mara moja inapofungua sehemu hii — inarekodi 'ameingia'."""
    permission_classes = [IsSuperAdmin]

    def post(self, request):
        log(request, 'open')
        return Response({'ok': True})


class ExportView(APIView):
    permission_classes = [IsSuperAdmin]

    def get(self, request):
        # 'type' (si 'format' — DRF inatumia ?format= kuchagua renderer)
        kind = request.query_params.get('type', 'xlsx')
        if kind not in ('xlsx', 'pdf'):
            raise ValidationError({'type': "Lazima iwe 'xlsx' au 'pdf'."})
        site, df, dt = params(request)
        from . import export
        try:
            data, mime = export.build(kind, site, df, dt)
        except ImportError as e:
            return Response({'error': f'Maktaba haipo: {e.name}. Isakinishe (pip install).'}, status=501)
        log(request, 'export', site_name=_site_name(site), type=kind, site=site,
            date_from=_plain(df), date_to=_plain(dt))
        resp = HttpResponse(data, content_type=mime)
        resp['Content-Disposition'] = f'attachment; filename="uhasibu-{date.today():%Y%m%d}.{kind}"'
        return resp


def _site_name(site):
    if not site:
        return ''
    if site == 'company':
        return 'Kampuni nzima'
    s = Site.objects.filter(pk=site).first()
    return s.name if s else ''
