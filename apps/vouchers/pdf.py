COLOR_THEMES = {
    'blue':   {'bg': '#1e40af', 'accent': '#3b82f6'},
    'green':  {'bg': '#065f46', 'accent': '#10b981'},
    'purple': {'bg': '#4c1d95', 'accent': '#8b5cf6'},
    'red':    {'bg': '#991b1b', 'accent': '#ef4444'},
    'orange': {'bg': '#9a3412', 'accent': '#f97316'},
    'teal':   {'bg': '#134e4a', 'accent': '#14b8a6'},
    'black':  {'bg': '#111827', 'accent': '#6b7280'},
    'gold':   {'bg': '#78350f', 'accent': '#f59e0b'},
}

PER_PAGE = 24


def _price_display(price):
    price = float(price or 0)
    if price <= 0:
        return '—'
    if price >= 10000:
        return f"{price / 1000:.0f}K"
    return f"{price:,.0f}"


def _voucher_html(v):
    price = float(v.get('price') or 0)
    price_display = _price_display(price)
    uptime = v.get('duration') or '—'
    speed = v.get('speed') or '—'
    package_name = v.get('package_name') or '—'
    price_font = 10 if len(price_display) > 6 else 12 if len(price_display) > 4 else 14

    price_box = ''
    if price > 0:
        price_box = f'''
        <div class="v-price-box">
          <div class="v-price-label">PRICE</div>
          <div class="v-price-val" style="font-size:{price_font}px;">TZS {price_display}</div>
        </div>'''

    return f'''
    <div class="voucher">
      <div class="v-inner">
        <div>
          <div class="v-header">
            <div class="v-left">
              <div class="v-bizname">{v['business_name'].upper()}</div>
              <div class="v-tagline">Stay Connected. Stay Powered.</div>
            </div>
            <div class="v-right">
              {price_box}
              <div class="v-wifi">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none">
                  <path d="M1.5 8.5C5.5 4.5 10.5 2.5 12 2.5C13.5 2.5 18.5 4.5 22.5 8.5" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
                  <path d="M4.5 11.5C7.5 8.5 10 7 12 7C14 7 16.5 8.5 19.5 11.5" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
                  <path d="M7.5 14.5C9.5 12.5 11 11.5 12 11.5C13 11.5 14.5 12.5 16.5 14.5" stroke="white" stroke-width="2.5" stroke-linecap="round"/>
                  <circle cx="12" cy="18" r="1.5" fill="white"/>
                </svg>
              </div>
            </div>
          </div>
          <div class="v-stats">
            <div class="v-stat">
              <div class="v-stat-label">UPTIME</div>
              <div class="v-stat-val">{uptime}</div>
            </div>
            <div class="v-stat">
              <div class="v-stat-label">SPEED</div>
              <div class="v-stat-val" style="font-size:{'7px' if len(speed) > 10 else '9px'};">{speed}</div>
            </div>
          </div>
          <div class="v-pkg">
            <span class="v-pkg-label">PACKAGE</span>
            <span class="v-pkg-val">{package_name}</span>
          </div>
        </div>
        <div>
          <div class="v-dash"></div>
          <div class="v-code-box">
            <div class="v-code">{v['code']}</div>
            <div class="v-code-label">VOUCHER CODE</div>
          </div>
          <div class="v-footer">
            <div class="v-ty">Thank You!</div>
          </div>
        </div>
      </div>
    </div>'''


def build_voucher_pdf(business_name: str, theme_id: str, vouchers: list) -> bytes:
    """
    vouchers: list ya dict {code, package_name, price, duration, speed}
    Inarudisha PDF bytes — muundo unaofanana na handlePrint() ya
    VoucherManagementPage.tsx (grid ya column 4, A4 portrait, kadi 32/page).
    """
    from weasyprint import HTML

    theme = COLOR_THEMES.get(theme_id, COLOR_THEMES['blue'])
    for v in vouchers:
        v['business_name'] = business_name

    chunks = [vouchers[i:i + PER_PAGE] for i in range(0, len(vouchers), PER_PAGE)] or [[]]

    pages_html = ''
    for idx, chunk in enumerate(chunks):
        is_last = idx == len(chunks) - 1
        vhtml = ''.join(_voucher_html(v) for v in chunk)
        pages_html += f'<div class="page{" last-page" if is_last else ""}">{vhtml}</div>'

    html = f'''<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ background: white; font-family: 'Liberation Sans', Arial, 'DejaVu Sans', sans-serif; }}
  .page {{
    width: 202mm; padding: 3mm;
    display: grid; grid-template-columns: repeat(4, 1fr);
    grid-auto-rows: 42mm; gap: 2mm;
    page-break-after: always;
  }}
  .last-page {{ page-break-after: avoid; }}
  .voucher {{
    background: #f0f4ff; border-radius: 7px; border: 1px solid #d0d8ff;
    display: flex; flex-direction: column; page-break-inside: avoid;
    height: 42mm; overflow: hidden;
  }}
  .v-inner {{ padding: 6px 7px; flex: 1; display: flex; flex-direction: column; justify-content: space-between; }}
  .v-header {{ display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }}
  .v-left {{ flex: 1; min-width: 0; }}
  .v-bizname {{ font-size: 11px; font-weight: 900; letter-spacing: 0.3px; line-height: 1.1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 100%; }}
  .v-tagline {{ font-size: 5.5px; color: #888; font-style: italic; margin-top: 1px; }}
  .v-right {{ display: flex; flex-direction: column; align-items: flex-end; gap: 2px; flex-shrink: 0; margin-left: 4px; }}
  .v-price-box {{ border-radius: 5px; padding: 2px 5px; border: 1.5px solid #c9a227; text-align: center; background: linear-gradient(135deg, {theme['bg']} 0%, #0d1a5c 100%); }}
  .v-price-label {{ font-size: 5px; color: #c9a227; font-weight: 700; letter-spacing: 1px; }}
  .v-price-val {{ font-weight: 900; color: #fff; white-space: nowrap; }}
  .v-wifi {{ border-radius: 5px; padding: 3px 4px; border: 1.5px solid #c9a227; display: flex; align-items: center; justify-content: center; background: {theme['bg']}; }}
  .v-stats {{ display: flex; gap: 3px; margin-bottom: 3px; }}
  .v-stat {{ flex: 1; background: #fff; border-radius: 4px; padding: 3px 4px; border: 1px solid #e5eaf5; }}
  .v-stat-label {{ font-size: 5.5px; font-weight: 700; color: #333; margin-bottom: 1px; }}
  .v-stat-val {{ font-size: 9px; font-weight: 900; color: {theme['bg']}; }}
  .v-pkg {{ display: flex; align-items: center; justify-content: space-between; padding: 2px 4px; background: #fff; border-radius: 4px; border: 1px solid #e5eaf5; }}
  .v-pkg-label {{ font-size: 5.5px; font-weight: 700; color: #555; }}
  .v-pkg-val {{ font-size: 7px; font-weight: 700; color: {theme['bg']}; max-width: 60%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
  .v-dash {{ border-top: 1px dashed #c9a227; margin: 3px 0; }}
  .v-code-box {{ background: #fff; border: 1.5px solid #c9a227; border-radius: 5px; padding: 3px 4px; text-align: center; margin-bottom: 2px; }}
  .v-code {{ font-size: 13px; font-weight: 900; letter-spacing: 1.5px; font-family: 'Courier New', monospace; color: {theme['bg']}; word-break: break-all; }}
  .v-code-label {{ font-size: 5px; font-weight: 700; color: #888; letter-spacing: 1.5px; margin-top: 1px; }}
  .v-footer {{ text-align: center; }}
  .v-ty {{ font-size: 7px; font-weight: 900; font-style: italic; font-family: Georgia, serif; color: {theme['bg']}; }}
  @page {{ size: A4 portrait; margin: 4mm; }}
</style>
</head>
<body>{pages_html}</body>
</html>'''

    return HTML(string=html).write_pdf()

