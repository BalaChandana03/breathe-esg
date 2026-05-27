from django.db import models
from django.contrib.auth.models import User

class Tenant(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Facility(models.Model):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='facilities')
    name = models.CharField(max_length=255)
    facility_code = models.CharField(max_length=100) # e.g. SAP Plant "WERKS-1001" or similar
    region = models.CharField(max_length=100) # e.g. PG&E Region or "US-WEST", "DE-NORTH"
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Facilities"
        unique_together = ('tenant', 'facility_code')

    def __str__(self):
        return f"{self.name} ({self.facility_code})"

class Airport(models.Model):
    iata_code = models.CharField(max_length=3, unique=True)
    name = models.CharField(max_length=255)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    def __str__(self):
        return f"{self.iata_code} - {self.name}"

class EmissionFactor(models.Model):
    SOURCE_CHOICES = [
        ('SAP', 'SAP ERP (Fuel & Procurement)'),
        ('UTILITY', 'Utility Portal (Electricity)'),
        ('TRAVEL', 'Corporate Travel (Flights, Hotels, Ground)'),
    ]
    
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    category = models.CharField(max_length=255) # e.g. "Diesel Fuel", "Purchased Electricity", "Short-Haul Flight", etc.
    scope = models.IntegerField(choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')])
    factor = models.DecimalField(max_digits=12, decimal_places=6) # kg CO2e per unit
    unit = models.CharField(max_length=50) # e.g. "L", "kWh", "pkm", "room_night"
    region = models.CharField(max_length=100, blank=True, null=True) # Optional regional specificity (e.g. ConEd vs. PG&E grid factor)
    active = models.BooleanField(default=True)

    def __str__(self):
        return f"[{self.get_source_type_display()}] {self.category} (Scope {self.scope}) - {self.factor} kg CO2e/{self.unit}"

class IngestionBatch(models.Model):
    STATUS_CHOICES = [
        ('PENDING', 'Pending Processing'),
        ('PROCESSING', 'Processing'),
        ('SUCCESS', 'Successfully Processed'),
        ('FAILED', 'Failed'),
    ]
    
    SOURCE_CHOICES = [
        ('SAP', 'SAP Fuel & Procurement'),
        ('UTILITY', 'Utility Portal Electricity'),
        ('TRAVEL', 'Corporate Travel Platform'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='batches')
    source_type = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    file_name = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    
    total_rows = models.IntegerField(default=0)
    processed_rows = models.IntegerField(default=0)
    failed_rows = models.IntegerField(default=0)
    error_summary = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name_plural = "Ingestion Batches"

    def __str__(self):
        return f"{self.source_type} Batch #{self.id} ({self.status}) - {self.file_name}"

class RawRecord(models.Model):
    STATUS_CHOICES = [
        ('UNPROCESSED', 'Unprocessed'),
        ('VALIDATED', 'Validated & Normalized'),
        ('ERROR', 'Error Parsing'),
    ]

    batch = models.ForeignKey(IngestionBatch, on_delete=models.CASCADE, related_name='raw_records')
    row_index = models.IntegerField()
    raw_payload = models.JSONField() # Preserves the verbatim original row exactly as imported
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='UNPROCESSED')
    error_message = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"RawRow #{self.row_index} in Batch #{self.batch.id} ({self.status})"

class ActivityRecord(models.Model):
    STATUS_CHOICES = [
        ('PENDING_REVIEW', 'Pending Review'),
        ('APPROVED', 'Approved & Locked'),
        ('REJECTED', 'Rejected'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='activity_records')
    facility = models.ForeignKey(Facility, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    raw_record = models.ForeignKey(RawRecord, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities')
    
    source_type = models.CharField(max_length=20, choices=IngestionBatch.SOURCE_CHOICES)
    scope = models.IntegerField(choices=[(1, 'Scope 1'), (2, 'Scope 2'), (3, 'Scope 3')])
    category = models.CharField(max_length=255) # e.g. "Purchased Electricity", "Business Travel"
    
    activity_date = models.DateField() # Start of activity or billing period month
    end_date = models.DateField(blank=True, null=True) # End of activity (especially for utility billing ranges)
    
    quantity = models.DecimalField(max_digits=15, decimal_places=4) # Converted to standard unit
    unit = models.CharField(max_length=50) # Standard normalized unit (e.g. L, kWh, pkm)
    
    original_quantity = models.DecimalField(max_digits=15, decimal_places=4)
    original_unit = models.CharField(max_length=50)
    
    co2e_emissions = models.DecimalField(max_digits=15, decimal_places=6) # Metric Tons of CO2e
    emission_factor_used = models.DecimalField(max_digits=12, decimal_places=6)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING_REVIEW')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_activities')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True, null=True)
    
    is_edited = models.BooleanField(default=False)
    anomaly_flags = models.JSONField(default=dict, blank=True) # e.g. {"spike": true, "unmapped_facility": true}

    def __str__(self):
        return f"{self.source_type} Record - {self.quantity} {self.unit} ({self.co2e_emissions} t CO2e) - {self.status}"

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Record Normalization'),
        ('UPDATE', 'Record Edited'),
        ('APPROVE', 'Record Approved'),
        ('REJECT', 'Record Rejected'),
        ('OVERRIDE', 'Calculations Overridden'),
    ]

    activity_record = models.ForeignKey(ActivityRecord, on_delete=models.CASCADE, related_name='audit_trail')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    changes = models.JSONField(default=dict) # e.g. {"quantity": {"old": 120.0, "new": 100.0}}

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Audit: {self.action} on Record #{self.activity_record.id} by {self.user} at {self.timestamp}"
