from rest_framework import serializers
from django.contrib.auth.models import User
from .models import Tenant, Facility, Airport, EmissionFactor, IngestionBatch, RawRecord, ActivityRecord, AuditLog

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']

class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = '__all__'

class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = '__all__'

class AirportSerializer(serializers.ModelSerializer):
    class Meta:
        model = Airport
        fields = '__all__'

class EmissionFactorSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmissionFactor
        fields = '__all__'

class RawRecordSerializer(serializers.ModelSerializer):
    class Meta:
        model = RawRecord
        fields = '__all__'

class IngestionBatchSerializer(serializers.ModelSerializer):
    uploaded_by_detail = UserSerializer(source='uploaded_by', read_only=True)
    
    class Meta:
        model = IngestionBatch
        fields = '__all__'

class AuditLogSerializer(serializers.ModelSerializer):
    user_detail = UserSerializer(source='user', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = '__all__'

class ActivityRecordSerializer(serializers.ModelSerializer):
    facility_detail = FacilitySerializer(source='facility', read_only=True)
    raw_record_detail = RawRecordSerializer(source='raw_record', read_only=True)
    audit_trail = AuditLogSerializer(many=True, read_only=True)
    reviewed_by_detail = UserSerializer(source='reviewed_by', read_only=True)

    class Meta:
        model = ActivityRecord
        fields = '__all__'
