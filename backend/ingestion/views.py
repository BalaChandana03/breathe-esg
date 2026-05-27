from datetime import datetime, date
from decimal import Decimal
import io

from django.db import transaction
from django.db.models import Sum, Count, Avg
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from django.contrib.auth.models import User

from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser

from .models import Tenant, Facility, Airport, EmissionFactor, IngestionBatch, RawRecord, ActivityRecord, AuditLog
from .serializers import TenantSerializer, FacilitySerializer, IngestionBatchSerializer, ActivityRecordSerializer, AuditLogSerializer
from .parsers import ESGDataParser, FALLBACK_AIRPORTS

def ensure_seed_data(tenant):
    """
    Auto-seeds the database with default facilities, airports, and emission factors 
    if they are not already set up. This ensures a seamless out-of-the-box review experience.
    """
    # 1. Seed Facilities
    if not Facility.objects.filter(tenant=tenant).exists():
        Facility.objects.create(tenant=tenant, name="San Francisco Corporate HQ", facility_code="WERKS-1001", region="US-WEST")
        Facility.objects.create(tenant=tenant, name="Frankfurt Production Plant", facility_code="WERKS-1002", region="DE-NORTH")
        Facility.objects.create(tenant=tenant, name="ConEd Meter Account #1042", facility_code="CONED-4210", region="US-EAST")
        Facility.objects.create(tenant=tenant, name="ConEd Meter Account #1043", facility_code="MTR-9876", region="US-EAST")

    # 2. Seed Airports
    if Airport.objects.count() == 0:
        for code, info in FALLBACK_AIRPORTS.items():
            Airport.objects.create(
                iata_code=code,
                name=info['name'],
                latitude=Decimal(str(info['lat'])),
                longitude=Decimal(str(info['lon']))
            )

    # 3. Seed Emission Factors
    if EmissionFactor.objects.count() == 0:
        # SAP EFs (kg CO2e per normalized unit)
        EmissionFactor.objects.create(source_type='SAP', category='Diesel Fuel', scope=1, factor=Decimal('2.68'), unit='L')
        EmissionFactor.objects.create(source_type='SAP', category='Gasoline Fuel', scope=1, factor=Decimal('2.31'), unit='L')
        EmissionFactor.objects.create(source_type='SAP', category='Steel', scope=3, factor=Decimal('1.85'), unit='KG')
        EmissionFactor.objects.create(source_type='SAP', category='Concrete', scope=3, factor=Decimal('0.32'), unit='KG')
        EmissionFactor.objects.create(source_type='SAP', category='General Purchased Goods', scope=3, factor=Decimal('0.95'), unit='KG')

        # Utility Grid EFs (kg CO2e per kWh by region)
        EmissionFactor.objects.create(source_type='UTILITY', category='Purchased Electricity', scope=2, factor=Decimal('0.231'), unit='kWh', region='US-WEST') # Cleaner grid (CA)
        EmissionFactor.objects.create(source_type='UTILITY', category='Purchased Electricity', scope=2, factor=Decimal('0.385'), unit='kWh', region='US-EAST') # ConEd/NY standard grid
        EmissionFactor.objects.create(source_type='UTILITY', category='Purchased Electricity', scope=2, factor=Decimal('0.420'), unit='kWh', region='DE-NORTH') # German grid blend
        EmissionFactor.objects.create(source_type='UTILITY', category='Purchased Electricity', scope=2, factor=Decimal('0.370'), unit='kWh', region='US-AVERAGE')

        # Travel EFs (kg CO2e per standard unit)
        EmissionFactor.objects.create(source_type='TRAVEL', category='Short-Haul Flight', scope=3, factor=Decimal('0.254'), unit='pkm') # <500km
        EmissionFactor.objects.create(source_type='TRAVEL', category='Medium-Haul Flight', scope=3, factor=Decimal('0.191'), unit='pkm') # 500-1600km
        EmissionFactor.objects.create(source_type='TRAVEL', category='Long-Haul Flight', scope=3, factor=Decimal('0.172'), unit='pkm') # >1600km
        EmissionFactor.objects.create(source_type='TRAVEL', category='Hotel Stay', scope=3, factor=Decimal('20.40'), unit='room_night')
        EmissionFactor.objects.create(source_type='TRAVEL', category='Ground Transport', scope=3, factor=Decimal('0.210'), unit='km')
        EmissionFactor.objects.create(source_type='TRAVEL', category='Ground Transport Spend', scope=3, factor=Decimal('0.462'), unit='USD')


class IngestionUploadView(APIView):
    parser_classes = [MultiPartParser]

    def post(self, request, format=None):
        """
        Accepts multipart form-data upload containing:
        - file: CSV file
        - source_type: 'SAP' | 'UTILITY' | 'TRAVEL'
        - tenant_id (optional): Int ID of Tenant
        """
        uploaded_file = request.FILES.get('file')
        source_type = request.data.get('source_type')
        tenant_id = request.data.get('tenant_id')

        if not uploaded_file or not source_type:
            return Response(
                {"error": "Both 'file' and 'source_type' must be provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if source_type not in ['SAP', 'UTILITY', 'TRAVEL']:
            return Response(
                {"error": f"Invalid source_type '{source_type}'. Must be one of: 'SAP', 'UTILITY', 'TRAVEL'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Retrieve or create default Tenant (Breathe ESG Demo Tenant)
        if tenant_id:
            tenant = get_object_or_404(Tenant, id=tenant_id)
        else:
            tenant, _ = Tenant.objects.get_or_create(name="Breathe ESG Enterprise Demo")

        # Auto-seed basic settings for seamless demonstration
        ensure_seed_data(tenant)

        # Get or create admin user to associate with uploading
        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user, _ = User.objects.get_or_create(username='analyst_demo', email='analyst@demo.com')

        # Read CSV file contents
        try:
            file_data = uploaded_file.read().decode('utf-8')
            csv_file_wrapper = io.StringIO(file_data)
        except Exception as e:
            return Response(
                {"error": f"Failed to read CSV file: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Initialize IngestionBatch
        batch = IngestionBatch.objects.create(
            tenant=tenant,
            source_type=source_type,
            file_name=uploaded_file.name,
            status='PROCESSING',
            uploaded_by=user
        )

        try:
            # Parse based on source type
            with transaction.atomic():
                if source_type == 'SAP':
                    processed, failed = ESGDataParser.parse_sap_csv(batch, csv_file_wrapper)
                elif source_type == 'UTILITY':
                    processed, failed = ESGDataParser.parse_utility_csv(batch, csv_file_wrapper)
                elif source_type == 'TRAVEL':
                    processed, failed = ESGDataParser.parse_travel_csv(batch, csv_file_wrapper)

            # Refresh batch data from DB
            batch.refresh_from_db()
            
            serializer = IngestionBatchSerializer(batch)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except Exception as e:
            batch.status = 'FAILED'
            batch.error_summary = f"Fatal system parsing exception: {str(e)}"
            batch.save()
            return Response(
                {"error": f"Internal parser crashed: {str(e)}", "batch_id": batch.id},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ActivityRecordListView(APIView):
    def get(self, request):
        """
        Returns filterable list of normalized ActivityRecords.
        Query params: status, source_type, scope, has_anomalies
        """
        # Ensure seed data is initialized
        tenant, _ = Tenant.objects.get_or_create(name="Breathe ESG Enterprise Demo")
        ensure_seed_data(tenant)

        records = ActivityRecord.objects.all().order_by('-activity_date')

        # Query Filters
        status_param = request.query_params.get('status')
        source_param = request.query_params.get('source_type')
        scope_param = request.query_params.get('scope')
        anomaly_param = request.query_params.get('has_anomalies')

        if status_param:
            records = records.filter(status=status_param)
        if source_param:
            records = records.filter(source_type=source_param)
        if scope_param:
            records = records.filter(scope=int(scope_param))
        
        if anomaly_param:
            if anomaly_param.lower() == 'true':
                records = [r for r in records if bool(r.anomaly_flags)]
            elif anomaly_param.lower() == 'false':
                records = [r for r in records if not bool(r.anomaly_flags)]

        serializer = ActivityRecordSerializer(records, many=True)
        return Response(serializer.data)


class ActivityRecordActionView(APIView):
    def post(self, request, pk, action):
        """
        Accepts review actions on records: 'approve' or 'reject'.
        For rejections, requires 'rejection_reason' in POST body.
        """
        record = get_object_or_404(ActivityRecord, id=pk)
        
        # Lock check: Cannot modify locked/already approved audit records
        if record.status == 'APPROVED' and action != 'reject':
            return Response(
                {"error": "This record has already been locked for audit."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user, _ = User.objects.get_or_create(username='analyst_demo', email='analyst@demo.com')

        if action == 'approve':
            record.status = 'APPROVED'
            record.reviewed_by = user
            record.reviewed_at = datetime.now()
            record.rejection_reason = None
            record.save()

            AuditLog.objects.create(
                activity_record=record,
                user=user,
                action='APPROVE',
                changes={"status": {"old": "PENDING_REVIEW", "new": "APPROVED"}}
            )

        elif action == 'reject':
            reason = request.data.get('rejection_reason', '').strip()
            if not reason:
                return Response(
                    {"error": "A rejection reason must be provided when rejecting rows."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            old_status = record.status
            record.status = 'REJECTED'
            record.reviewed_by = user
            record.reviewed_at = datetime.now()
            record.rejection_reason = reason
            record.save()

            AuditLog.objects.create(
                activity_record=record,
                user=user,
                action='REJECT',
                changes={
                    "status": {"old": old_status, "new": "REJECTED"},
                    "rejection_reason": reason
                }
            )
        else:
            return Response(
                {"error": f"Invalid review action '{action}'. Must be 'approve' or 'reject'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = ActivityRecordSerializer(record)
        return Response(serializer.data)


class ActivityRecordEditView(APIView):
    def put(self, request, pk):
        """
        Allows analysts to override normalized quantities.
        Automatically logs changes in AuditLog and recalculates t CO2e emissions.
        """
        record = get_object_or_404(ActivityRecord, id=pk)

        if record.status == 'APPROVED':
            return Response(
                {"error": "Approved records are locked for audit and cannot be modified."},
                status=status.HTTP_400_BAD_REQUEST
            )

        new_quantity_str = request.data.get('quantity')
        facility_id = request.data.get('facility_id')

        if new_quantity_str is None:
            return Response(
                {"error": "The field 'quantity' is required for editing."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_quantity = Decimal(str(new_quantity_str))
        except Exception:
            return Response(
                {"error": f"Invalid numeric format for quantity: '{new_quantity_str}'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(is_superuser=True).first()
        if not user:
            user, _ = User.objects.get_or_create(username='analyst_demo', email='analyst@demo.com')

        changes_logged = {}
        old_quantity = record.quantity

        with transaction.atomic():
            # Update quantity & recalculate emissions
            record.quantity = new_quantity
            record.is_edited = True
            
            # Recalculate co2e_emissions: (new_quantity * ef_used) / 1000
            # Wait, if they edited the quantity, does the cabin class multiplier apply for flights?
            flight_multiplier = Decimal('1.0')
            if record.source_type == 'TRAVEL' and record.raw_record:
                cabin = record.raw_record.raw_payload.get('Cabin Class', '').upper()
                if cabin == 'BUSINESS':
                    flight_multiplier = Decimal('2.5')
                elif cabin == 'FIRST':
                    flight_multiplier = Decimal('4.0')
                elif cabin == 'PREMIUM_ECONOMY':
                    flight_multiplier = Decimal('1.6')
            
            new_emissions = (new_quantity * record.emission_factor_used * flight_multiplier) / Decimal('1000.0')
            old_emissions = record.co2e_emissions
            record.co2e_emissions = new_emissions

            changes_logged['quantity'] = {"old": str(old_quantity), "new": str(new_quantity)}
            changes_logged['co2e_emissions'] = {"old": str(old_emissions), "new": str(new_emissions)}

            # Update Facility if changed
            if facility_id is not None:
                old_fac_id = record.facility.id if record.facility else None
                if facility_id == '':
                    record.facility = None
                    changes_logged['facility'] = {"old": old_fac_id, "new": None}
                    # Clear unmapped facility flags if they mapped or cleared it
                    if 'unmapped_plant' in record.anomaly_flags:
                        del record.anomaly_flags['unmapped_plant']
                    if 'unmapped_meter' in record.anomaly_flags:
                        del record.anomaly_flags['unmapped_meter']
                else:
                    new_facility = get_object_or_404(Facility, id=facility_id)
                    record.facility = new_facility
                    changes_logged['facility'] = {"old": old_fac_id, "new": new_facility.id}
                    if 'unmapped_plant' in record.anomaly_flags:
                        del record.anomaly_flags['unmapped_plant']
                    if 'unmapped_meter' in record.anomaly_flags:
                        del record.anomaly_flags['unmapped_meter']

            record.save()

            AuditLog.objects.create(
                activity_record=record,
                user=user,
                action='UPDATE',
                changes=changes_logged
            )

        serializer = ActivityRecordSerializer(record)
        return Response(serializer.data)


class ESGAnalyticsView(APIView):
    def get(self, request):
        """
        Returns high-fidelity consolidated metrics for dashboard visualization:
        1. Consolidated emissions (Scope 1, 2, 3)
        2. Scope breakdown
        3. Monthly trends
        4. Emissions by Facility
        5. Emissions by Source Type
        """
        # Ensure seed data is initialized
        tenant, _ = Tenant.objects.get_or_create(name="Breathe ESG Enterprise Demo")
        ensure_seed_data(tenant)

        # Filters could be applied (e.g. facility, dates)
        base_qs = ActivityRecord.objects.filter(status='APPROVED')
        # If no approved rows yet, let's include PENDING_REVIEW for rich demonstration graphics!
        if base_qs.count() == 0:
            base_qs = ActivityRecord.objects.all()

        # 1. Standard aggregated metrics (t CO2e)
        total_emissions = base_qs.aggregate(Sum('co2e_emissions'))['co2e_emissions__sum'] or Decimal('0.00')
        scope_1 = base_qs.filter(scope=1).aggregate(Sum('co2e_emissions'))['co2e_emissions__sum'] or Decimal('0.00')
        scope_2 = base_qs.filter(scope=2).aggregate(Sum('co2e_emissions'))['co2e_emissions__sum'] or Decimal('0.00')
        scope_3 = base_qs.filter(scope=3).aggregate(Sum('co2e_emissions'))['co2e_emissions__sum'] or Decimal('0.00')

        # 2. Emissions by Source Type
        sources = base_qs.values('source_type').annotate(emissions=Sum('co2e_emissions'))
        source_breakdown = {s['source_type']: s['emissions'] for s in sources}

        # 3. Emissions by Facility
        facilities_qs = base_qs.values('facility__name').annotate(emissions=Sum('co2e_emissions')).order_by('-emissions')
        facility_breakdown = []
        for f in facilities_qs:
            facility_breakdown.append({
                "facility": f['facility__name'] if f['facility__name'] else "Corporate Operations / Unassigned",
                "emissions": f['emissions']
            })

        # 4. Monthly Ingestion Trends
        trends_qs = base_qs.annotate(
            month=TruncMonth('activity_date')
        ).values('month').annotate(
            emissions=Sum('co2e_emissions')
        ).order_by('month')

        monthly_trends = []
        for t in trends_qs:
            if t['month']:
                monthly_trends.append({
                    "month": t['month'].strftime("%b %Y"),
                    "emissions": t['emissions']
                })

        # 5. Ingestion stats (anomalies, counts)
        total_records_count = ActivityRecord.objects.count()
        approved_count = ActivityRecord.objects.filter(status='APPROVED').count()
        pending_count = ActivityRecord.objects.filter(status='PENDING_REVIEW').count()
        rejected_count = ActivityRecord.objects.filter(status='REJECTED').count()
        
        # Calculate how many anomalies are flagged currently
        anomalies_count = 0
        all_records = ActivityRecord.objects.all()
        for r in all_records:
            if bool(r.anomaly_flags):
                anomalies_count += 1

        response_data = {
            "total_emissions": total_emissions,
            "scope_1": scope_1,
            "scope_2": scope_2,
            "scope_3": scope_3,
            "source_breakdown": source_breakdown,
            "facility_breakdown": facility_breakdown,
            "monthly_trends": monthly_trends,
            "ingestion_stats": {
                "total_records": total_records_count,
                "approved": approved_count,
                "pending": pending_count,
                "rejected": rejected_count,
                "anomalies": anomalies_count
            }
        }

        return Response(response_data)
