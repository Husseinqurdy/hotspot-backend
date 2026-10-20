from decimal import Decimal
from rest_framework import serializers
from .models import Site, Entry
from .calc import loan_balance


class SiteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Site
        fields = ['id', 'name', 'note', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']


class EntrySerializer(serializers.ModelSerializer):
    site_name = serializers.SerializerMethodField()
    kind_display = serializers.CharField(source='get_kind_display', read_only=True)
    created_by_name = serializers.CharField(source='created_by.username', read_only=True, default='')
    voided_by_name = serializers.CharField(source='voided_by.username', read_only=True, default='')
    loan_balance = serializers.SerializerMethodField()

    class Meta:
        model = Entry
        fields = ['id', 'site', 'site_name', 'kind', 'kind_display', 'date', 'category', 'description',
                  'amount', 'interest_rate', 'loan_ref', 'loan_balance',
                  'voided', 'void_reason', 'voided_by_name', 'voided_at',
                  'created_by_name', 'created_at']
        read_only_fields = ['id', 'voided', 'void_reason', 'voided_at', 'created_at']

    def get_site_name(self, o):
        return o.site.name if o.site_id else 'Kampuni nzima'

    def get_loan_balance(self, o):
        return str(loan_balance(o)) if o.kind == Entry.LOAN else None

    def validate(self, a):
        inst = self.instance
        if inst is not None:
            if inst.voided:
                raise serializers.ValidationError('Rekodi iliyofutwa haiwezi kubadilishwa.')
            if a.get('kind', inst.kind) != inst.kind or a.get('loan_ref', inst.loan_ref) != inst.loan_ref:
                raise serializers.ValidationError('Aina na mkopo wa rekodi haviwezi kubadilishwa. Futa rekodi kisha iunde upya.')
        kind = a.get('kind', inst.kind if inst else None)
        amount = a.get('amount', inst.amount if inst else None)
        if amount is None or amount <= 0:
            raise serializers.ValidationError({'amount': 'Kiasi lazima kiwe zaidi ya sifuri.'})
        site = a.get('site', inst.site if inst else None)
        if site is not None and not site.is_active and inst is None:
            raise serializers.ValidationError({'site': 'Site hii imezimwa.'})

        loan = a.get('loan_ref', inst.loan_ref if inst else None)
        if kind == Entry.LOAN_PAYMENT:
            if loan is None or loan.kind != Entry.LOAN or loan.voided:
                raise serializers.ValidationError({'loan_ref': 'Chagua mkopo halali.'})
            allowed = loan_balance(loan) + (inst.amount if inst else Decimal('0'))
            if amount > allowed:
                raise serializers.ValidationError({'amount': f'Marejesho yanazidi bakaa ya mkopo ({allowed:,.0f}).'})
            a['site'] = loan.site
        else:
            if loan is not None:
                raise serializers.ValidationError({'loan_ref': 'Inatumika kwa marejesho ya mkopo tu.'})
            if a.get('interest_rate') is not None and kind != Entry.LOAN:
                raise serializers.ValidationError({'interest_rate': 'Riba ni kwa mkopo tu.'})
        if inst is not None and kind == Entry.LOAN:
            paid = inst.amount - loan_balance(inst)
            if amount < paid:
                raise serializers.ValidationError({'amount': f'Mkopo umeshalipwa {paid:,.0f}; kiasi hakiwezi kuwa chini ya hicho.'})
        return a
