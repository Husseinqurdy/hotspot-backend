"""Excel (openpyxl) na PDF (reportlab), kwa Kiswahili au Kiingereza. Maktaba zinaingizwa ndani ya build()."""
import io
from . import calc
from .models import Entry

TZS = '"TZS" #,##0'
L = {
    'sw': {
        'title': 'Ripoti ya Uhasibu', 'period': 'Kipindi', 'range': '{a} hadi {b}', 'start': 'mwanzo', 'now': 'leo',
        's_summary': 'Muhtasari', 's_records': 'Rekodi', 'per_site': 'Kila site', 'item': 'Kipengele',
        'pairs': ['Mapato', 'Matumizi', 'Faida / Hasara', 'Mali (assets)', 'Madeni (liabilities)', 'Mikopo isiyolipwa', 'Mtaji (equity)'],
        'head': ['Tarehe', 'Site', 'Aina', 'Kundi', 'Maelezo', 'Kiasi (TZS)', 'Hali'],
        'site_cols': ['Site', 'Mapato', 'Matumizi', 'Faida', 'Mali', 'Madeni', 'Mikopo', 'Mtaji'],
        'company': 'Kampuni nzima', 'voided': 'IMEFUTWA',
        'tot_income': 'Jumla Mapato', 'tot_expense': 'Jumla Matumizi', 'tot_profit': 'Faida / Hasara',
        'kinds': {'income': 'Mapato', 'expense': 'Matumizi', 'asset': 'Mali', 'liability': 'Deni', 'loan': 'Mkopo', 'loan_payment': 'Marejesho ya mkopo'},
    },
    'en': {
        'title': 'Accounting Report', 'period': 'Period', 'range': '{a} to {b}', 'start': 'start', 'now': 'today',
        's_summary': 'Summary', 's_records': 'Records', 'per_site': 'By site', 'item': 'Item',
        'pairs': ['Income', 'Expenses', 'Profit / Loss', 'Assets', 'Liabilities', 'Outstanding loans', 'Equity'],
        'head': ['Date', 'Site', 'Type', 'Category', 'Description', 'Amount (TZS)', 'Status'],
        'site_cols': ['Site', 'Income', 'Expenses', 'Profit', 'Assets', 'Liabilities', 'Loans', 'Equity'],
        'company': 'Whole company', 'voided': 'DELETED',
        'tot_income': 'Total Income', 'tot_expense': 'Total Expenses', 'tot_profit': 'Profit / Loss',
        'kinds': {'income': 'Income', 'expense': 'Expense', 'asset': 'Asset', 'liability': 'Liability', 'loan': 'Loan', 'loan_payment': 'Loan repayment'},
    },
}
SITE_KEYS = ('income', 'expense', 'profit', 'assets', 'liabilities', 'loans_outstanding', 'equity')
PAIR_KEYS = ('income', 'expense', 'profit', 'assets', 'liabilities', 'loans_outstanding', 'equity')


def _rows(site, df, dt, T):
    qs = Entry.objects.select_related('site').order_by('date', 'id')
    if site == 'company':
        qs = qs.filter(site__isnull=True)
    elif site:
        qs = qs.filter(site_id=site)
    if df:
        qs = qs.filter(date__gte=df)
    if dt:
        qs = qs.filter(date__lte=dt)
    return [[e.date.isoformat(), e.site.name if e.site_id else T['company'], T['kinds'][e.kind],
             e.category, e.description, float(e.amount), T['voided'] if e.voided else ''] for e in qs]


def build(kind, site, df, dt, lang='sw'):
    T = L.get(lang, L['sw'])
    s = calc.summary(site, df, dt)
    for r in s['by_site']:
        if r['site'] == 'Kampuni nzima':
            r['site'] = T['company']
    rows = _rows(site, df, dt, T)
    period = T['range'].format(a=df or T['start'], b=dt or T['now'])
    return (_xlsx if kind == 'xlsx' else _pdf)(s, rows, period, T)


def _xlsx(s, rows, period, T):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill
    bold, fill = Font(bold=True), PatternFill('solid', fgColor='DDE3F5')
    wb = Workbook()
    ws = wb.active
    ws.title = T['s_summary']
    ws.append([T['period'], period]); ws['A1'].font = bold
    ws.append([])
    for label, key in zip(T['pairs'], PAIR_KEYS):
        ws.append([label, float(s[key])])
    ws.append([])
    ws.append(T['site_cols'])
    for c in ws[ws.max_row]:
        c.font, c.fill = bold, fill
    for r in s['by_site']:
        ws.append([r['site']] + [float(r[k]) for k in SITE_KEYS])
    for row in ws.iter_rows(min_row=3):
        for c in row[1:]:
            if isinstance(c.value, float):
                c.number_format = TZS
    for col in 'BCDEFGH':
        ws.column_dimensions[col].width = 18
    ws.column_dimensions['A'].width = 26

    we = wb.create_sheet(T['s_records'])
    we.append(T['head'])
    for c in we[1]:
        c.font, c.fill = bold, fill
    for r in rows:
        we.append(r)
    for row in we.iter_rows(min_row=2, min_col=6, max_col=6):
        row[0].number_format = TZS
    n = len(rows) + 1
    we.append([])
    # fomula halisi — jumla zinajihesabu upya mhasibu akihariri Excel (kigezo ni lebo ya lugha husika)
    for label, key in ((T['tot_income'], 'income'), (T['tot_expense'], 'expense')):
        we.append([label, '', '', '', '', f'=SUMIFS(F2:F{n},C2:C{n},"{T["kinds"][key]}",G2:G{n},"")'])
    we.append([T['tot_profit'], '', '', '', '', f'=F{n+2}-F{n+3}'])
    for row in we.iter_rows(min_row=n + 2, max_row=n + 4, min_col=6, max_col=6):
        row[0].number_format = TZS
    for col, w in zip('ABCDEFG', (12, 20, 18, 18, 40, 20, 12)):
        we.column_dimensions[col].width = w
    buf = io.BytesIO(); wb.save(buf)
    return buf.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _pdf(s, rows, period, T):
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
    story = [Paragraph(T['title'], st['Title']), Paragraph(f"{T['period']}: {period}", st['Normal']), Spacer(1, 8),
             tbl([[T['item'], 'TZS']] + [[lbl, m(s[k])] for lbl, k in zip(T['pairs'], PAIR_KEYS)], [200, 110]), Spacer(1, 10)]
    if s['by_site']:
        story += [Paragraph(T['per_site'], st['Heading3']),
                  tbl([T['site_cols']] + [[r['site']] + [m(r[k]) for k in SITE_KEYS] for r in s['by_site']]), Spacer(1, 10)]
    story += [Paragraph(T['s_records'], st['Heading3']),
              tbl([T['head']] + [r[:5] + [f'{r[5]:,.0f}', r[6]] for r in rows], [60, 100, 90, 90, 280, 70, 60])]
    doc.build(story)
    return buf.getvalue(), 'application/pdf'
