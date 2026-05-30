from rest_framework import serializers
from .models import OutgoingSMS
class OutgoingSMSSerializer(serializers.ModelSerializer):
    class Meta:
        model = OutgoingSMS
        fields = ['id','phone','message','status','priority','created_at']
        read_only_fields = fields