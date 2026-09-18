from apps.vouchers.models import Voucher
from django.utils import timezone

# ── Kundi 1: bado hazijatumika — futa expires_at ya default mbovu ──
unused = Voucher.objects.filter(status='active', used_at__isnull=True)
count_unused = unused.count()
unused.update(expires_at=None)
print(f"Kundi 1: vouchers {count_unused} (bado hazijatumika) -- expires_at imefutwa (None)")

# ── Kundi 2: tayari zimetumika lakini bado 'active' -- sahihisha expires_at ──
used_active = Voucher.objects.filter(
    status='active', used_at__isnull=False
).select_related('package')

fixed = 0
skipped_no_package = 0
total_used = used_active.count()
for v in used_active:
    if not v.package_id:
        skipped_no_package += 1
        continue
    correct = v.used_at + timezone.timedelta(minutes=v.package.duration_minutes)
    if v.expires_at != correct:
        old = v.expires_at
        v.expires_at = correct
        v.save(update_fields=['expires_at'])
        fixed += 1
        print(f"  {v.code}: {old} -> {correct}")

print(f"Kundi 2: vouchers {fixed} zimesahihishwa (kati ya {total_used} zilizotumika)")
if skipped_no_package:
    print(f"  (Onyo: {skipped_no_package} hazina package -- ziliruka)")

print("IMEKAMILIKA.")
