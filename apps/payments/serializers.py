from rest_framework import serializers

from .models import Payment


class PaymentSerializer(serializers.ModelSerializer):

    client_name = serializers.CharField(
        source='client.business_name',
        read_only=True
    )

    package_name = serializers.CharField(
        source='package.name',
        read_only=True
    )

    network_display = serializers.CharField(
        source='get_network_display',
        read_only=True
    )

    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    class Meta:

        model = Payment

        fields = [
            'id',

            # CLIENT
            'client',
            'client_name',

            # PACKAGE
            'package',
            'package_name',

            # PAYMENT
            'phone_number',
            'amount',
            'transaction_id',

            # NETWORK
            'network',
            'network_display',

            # STATUS
            'status',
            'status_display',

            # MONEY
            'commission_amount',
            'client_share',

            # DEVICE
            'device_id',

            # TIMESTAMPS
            'created_at',
            'processed_at',
        ]

        read_only_fields = fields