"""Excel (openpyxl) na PDF (reportlab). Zinaingizwa ndani ya build() ili app ifanye kazi bila hizo."""
import io
from . import calc
from .models import Entry

TZS = '"TZS" #,##0'
HEAD = ['Tarehe', 'Site', 'Aina', 'Kundi', 'Maelezo', 'Kiasi (TZS)', 'Hali']


def _rows(site, df, dt):
    qs = Entry.objects.select_related('site').order_by('date', 'id')
    if site == 'company':
        qs = qs.filter(site__isnull=True)
    elif site:
        qs = qs.filter(site_id=site)
    if df:
        qs = qs.filter(date__gte=df)
    if dt:
        qs = qs.filter(date__lte=dt)
    return [[e.date.isoformat(), e.site.name if e.site_id else 'Kampuni nzima', e.get_kind_display(),
             e.category, e.description, float(e.amount), 'IMEFUTWA' if e.voided else ''] for e in qs]


def _summary_pairs(s):
    return [('Mapato', s['income']), ('Matumizi', s['expense']), ('Faida / Hasara', s['profit']),
            ('Mali (assets)', s['assets']), ('Madeni (liabilities)', s['liabilities']),
            ('Mikopo isiyolipwa', s['loans_outstanding']), ('Mtaji (equity)', s['equity'])]


def build(kind, site, df, dt):
    s = calc.summary(site, df, dt)
    rows = _rows(site, df, dt)
    period = f"{df or 'mwanzo'} hadi {dt or 'leo'}"
    return _xlsx(s, rows, period) if kind == 'xlsx' else _pdf(s, rows, period)


def _xlsx(s, rows, period):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    bold, fill = Font(bold=True), PatternFill('solid', fgColor='DDE3F5')
    wb = Workbook()
    ws = wb.active
    ws.title = 'Muhtasari'
    ws.append(['Kipindi', period]); ws['A1'].font = bold
    ws.append([])
    for k, v in _summary_pairs(s):
        ws.append([k, float(v)])
    ws.append([])
    ws.append(['Site', 'Mapato', 'Matumizi', 'Faida', 'Mali', 'Madeni', 'Mikopo', 'Mtaji'])
    for c in ws[ws.max_row]:
        c.font, c.fill = bold, fill
    for r in s['by_site']:
        ws.append([r['site']] + [float(r[k]) for k in ('income', 'expense', 'profit', 'assets', 'liabilities', 'loans_outstanding', 'equity')])
    for row in ws.iter_rows(min_row=3):
        for c in row[1:]:
            if isinstance(c.value, float):
                c.number_format = TZS
    ws.column_dimensions['A'].width = 26
    for col in 'BCDEFGH':
        ws.column_dimensions[col].width = 18

    we = wb.create_sheet('Rekodi')
    we.append(HEAD)
    for c in we[1]:
        c.font, c.fill = bold, fill
    for r in rows:
        we.append(r)
    n = len(rows) + 1
    we.append([])
    # fomula halisi — jumla zinajihesabu upya mhasibu akihariri Excel
    for label, kind in (('Jumla Mapato', 'Mapato'), ('Jumla Matumizi', 'Matumizi')):
        we.append([label, '', '', '', '', f'=SUMIFS(F2:F{n},C2:C{n},"{kind}",G2:G{n},"")'])
    we.append(['Faida / Hasara', '', '', '', '', f'=F{n+2}-F{n+3}'])
    for row in we.iter_rows(min_row=2, min_col=6, max_col=6):
        row[0].number_format = TZS
    for col, w in zip('ABCDEFG', (12, 20, 18, 18, 40, 20, 12)):
        we.column_dimensions[col].width = w
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _pdf(s, rows, period):
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer
    st = getSampleStyleSheet()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=landscape(A4), leftMargin=24, rightMargin=24, topMargin=24, bottomMargin=24)

    def tbl(data, widths=None):
        t = Table(data, colWidths=widths, repeatRows=1)
        t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dde3f5')),
                               ('FONTSIZE', (0, 0), (-1, -1), 8), ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
                               ('ALIGN', (-1, 1), (-1, -1), 'RIGHT')]))
        return t

    m = lambda v: f'{float(v):,.0f}'
    story = [Paragraph('Ripoti ya Uhasibu', st['Title']), Paragraph(f'Kipindi: {period}', st['Normal']), Spacer(1, 8),
             tbl([['Kipengele', 'TZS']] + [[k, m(v)] for k, v in _summary_pairs(s)], [200, 110]), Spacer(1, 10)]
    if s['by_site']:
        story += [Paragraph('Kila site', st['Heading3']),
                  tbl([['Site', 'Mapato', 'Matumizi', 'Faida', 'Mali', 'Madeni', 'Mikopo', 'Mtaji']] +
                      [[r['site']] + [m(r[k]) for k in ('income', 'expense', 'profit', 'assets', 'liabilities', 'loans_outstanding', 'equity')]
                       for r in s['by_site']]), Spacer(1, 10)]
    story += [Paragraph('Rekodi', st['Heading3']),
              tbl([HEAD] + [r[:5] + [f'{r[5]:,.0f}', r[6]] for r in rows], [60, 100, 90, 90, 280, 70, 60])]
    doc.build(story)
    return buf.getvalue(), 'application/pdf'
