from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from apps.accounts.models import User
from .models import Client

class ClientSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    class Meta:
        model = Client
        fields = ['id','username','email','business_name','reference_prefix','phone','address','balance','commission_rate','is_active','created_at']
        read_only_fields = ['id','reference_prefix','balance','created_at']

class ClientCreateSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=6, write_only=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    business_name = serializers.CharField(max_length=100)
    phone = serializers.CharField(max_length=15, required=False, allow_blank=True)
    commission_rate = serializers.DecimalField(max_digits=5, decimal_places=2, default=10.00)
    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username hii tayari inatumika.")
        return value
    def create(self, validated_data):
        user = User.objects.create(username=validated_data['username'], email=validated_data.get('email',''), password=make_password(validated_data['password']), role=User.ROLE_CLIENT)
        return Client.objects.create(user=user, business_name=validated_data['business_name'], phone=validated_data.get('phone',''), commission_rate=validated_data.get('commission_rate',10.00))
    def to_representation(self, instance):
        return ClientSerializer(instance).data

class AddBalanceSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=1)
