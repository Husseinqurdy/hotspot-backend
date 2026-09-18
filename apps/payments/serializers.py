from rest_framework import serializers

from .models import Payment, WithdrawalRequest


class PaymentSerializer(serializers.ModelSerializer):

    client_name = serializers.CharField(source='client.business_name', read_only=True)
    package_name = serializers.CharField(source='package.name', read_only=True)
    network_display = serializers.CharField(source='get_network_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    device_name = serializers.CharField(source='gsm_device.name', read_only=True)

    class Meta:
        model = Payment
        fields = [
            'id',
            'client', 'client_name',
            'package', 'package_name',
            'phone_number', 'amount', 'transaction_id',
            'network', 'network_display',
            'status', 'status_display',
            'commission_amount', 'client_share',
            'gsm_device', 'device_name', 'device_id',
            'created_at', 'processed_at',
        ]
        read_only_fields = fields


class WithdrawalRequestSerializer(serializers.ModelSerializer):

    client_name = serializers.CharField(source='client.business_name', read_only=True)
    network_display = serializers.CharField(source='get_network_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    processed_by_name = serializers.CharField(source='processed_by.username', read_only=True)

    class Meta:
        model = WithdrawalRequest
        fields = [
            'id',
            'client', 'client_name',
            'network', 'network_display',
            'account_name', 'lipa_number', 'amount',
            'status', 'status_display', 'admin_note',
            'processed_by', 'processed_by_name',
            'created_at', 'processed_at',
        ]
        read_only_fields = [
            'id', 'client', 'status', 'admin_note',
            'processed_by', 'created_at', 'processed_at',
        ]

    def validate(self, attrs):
        request = self.context.get('request')
        if self.instance is None:
            if not request or not request.user.is_client():
                raise serializers.ValidationError('Ni wateja tu wanaoweza kuomba kutoa fedha.')

            client = request.user.client_profile
            amount = attrs.get('amount')

            if amount is None or amount <= 0:
                raise serializers.ValidationError({'amount': 'Kiasi lazima kiwe zaidi ya sifuri.'})

            if amount > client.balance:
                raise serializers.ValidationError(
                    {'amount': f'Balance haitoshi. Bakaa yako ya sasa ni TZS {client.balance:,.0f}.'}
                )

        return attrs
