from django.test import TestCase
from django.contrib.auth.models import User
from decimal import Decimal
from datetime import date
import io

from .models import Tenant, Facility, Airport, EmissionFactor, IngestionBatch, RawRecord, ActivityRecord, AuditLog
from .parsers import calculate_haversine_distance, ESGDataParser

class ESGNormalizationTestCase(TestCase):
    def setUp(self):
        # Create standard Tenant
        self.tenant = Tenant.objects.create(name="Breathe ESG Enterprise Demo")
        
        # Create facilities
        self.hq = Facility.objects.create(
            tenant=self.tenant,
            name="San Francisco HQ",
            facility_code="WERKS-1001",
            region="US-WEST"
        )
        self.plant = Facility.objects.create(
            tenant=self.tenant,
            name="Frankfurt Production Plant",
            facility_code="WERKS-1002",
            region="DE-NORTH"
        )
        self.meter_facility = Facility.objects.create(
            tenant=self.tenant,
            name="Electricity Meter #4210",
            facility_code="CONED-4210",
            region="US-EAST"
        )

        # Create airports
        self.jfk = Airport.objects.create(iata_code="JFK", name="JFK Airport", latitude=Decimal("40.6398"), longitude=Decimal("-73.7789"))
        self.sfo = Airport.objects.create(iata_code="SFO", name="SFO Airport", latitude=Decimal("37.6190"), longitude=Decimal("-122.3749"))

        # Create standard emission factors
        EmissionFactor.objects.create(source_type='SAP', category='Diesel Fuel', scope=1, factor=Decimal('2.68'), unit='L')
        EmissionFactor.objects.create(source_type='SAP', category='Steel', scope=3, factor=Decimal('1.85'), unit='KG')
        
        EmissionFactor.objects.create(source_type='UTILITY', category='Purchased Electricity', scope=2, factor=Decimal('0.385'), unit='kWh', region='US-EAST')
        
        EmissionFactor.objects.create(source_type='TRAVEL', category='Short-Haul Flight', scope=3, factor=Decimal('0.254'), unit='pkm')
        EmissionFactor.objects.create(source_type='TRAVEL', category='Long-Haul Flight', scope=3, factor=Decimal('0.172'), unit='pkm')
        EmissionFactor.objects.create(source_type='TRAVEL', category='Hotel Stay', scope=3, factor=Decimal('20.40'), unit='room_night')

        # Admin user
        self.user = User.objects.create_superuser('admin_test', 'admin@test.com', 'adminpass')

    def test_haversine_distance_calculation(self):
        """
        Verify that our Great-Circle Haversine distance calculator outputs 
        correct coordinates and flight distance estimations.
        JFK to SFO is roughly 4151 kilometers.
        """
        jfk_coords = (self.jfk.latitude, self.jfk.longitude)
        sfo_coords = (self.sfo.latitude, self.sfo.longitude)
        
        distance_km = calculate_haversine_distance(
            jfk_coords[0], jfk_coords[1],
            sfo_coords[0], sfo_coords[1]
        )
        
        # Verify it falls within 1% error margin of 4151.3 km
        self.assertAlmostEqual(distance_km, 4151.3, delta=40.0)

    def test_sap_parser_success(self):
        """
        Tests the SAP parser's ability to ingest flat CSV files with 
        German technical headers, German date formats, and plant mappings.
        """
        # Formulate a mock SAP CSV file
        csv_content = (
            "WERKS,BUDAT,MATNR,MAKTX,MENGE,MEINS,DMBTR,WAERS,LIFNR\n"
            "WERKS-1001,25.05.2026,FUEL-DIESEL,Diesel Fuel,100,GAL,350.00,USD,VEND-01\n"
            "WERKS-1002,12.04.2026,PROC-STEEL,Steel Columns,5,TO,8500.00,EUR,VEND-02\n"
        )
        
        batch = IngestionBatch.objects.create(
            tenant=self.tenant,
            source_type='SAP',
            file_name="sap_test_mb51.csv",
            uploaded_by=self.user
        )
        
        csv_file = io.StringIO(csv_content)
        processed, failed = ESGDataParser.parse_sap_csv(batch, csv_file)
        
        self.assertEqual(processed, 2)
        self.assertEqual(failed, 0)
        
        # Verify first row: Diesel Fuel (GAL to L conversion)
        # 100 GAL * 3.78541 = 378.541 Liters
        record_1 = ActivityRecord.objects.get(raw_record__row_index=1)
        self.assertEqual(record_1.facility, self.hq)
        self.assertEqual(record_1.scope, 1)
        self.assertEqual(record_1.unit, "L")
        self.assertAlmostEqual(float(record_1.quantity), 378.541, places=3)
        # Emissions: 378.541 L * 2.68 kg CO2e / 1000 = 1.014 t CO2e
        self.assertAlmostEqual(float(record_1.co2e_emissions), 1.01449, places=3)
        self.assertEqual(record_1.status, 'PENDING_REVIEW')

        # Verify second row: Steel (TO to KG conversion)
        # 5 TO = 5000 KG. EF = 1.85. Emissions: 5000 * 1.85 / 1000 = 9.25 t CO2e
        record_2 = ActivityRecord.objects.get(raw_record__row_index=2)
        self.assertEqual(record_2.facility, self.plant)
        self.assertEqual(record_2.scope, 3)
        self.assertEqual(record_2.unit, "KG")
        self.assertEqual(int(record_2.quantity), 5000)
        self.assertAlmostEqual(float(record_2.co2e_emissions), 9.25, places=2)

    def test_utility_calendar_splitting(self):
        """
        Tests the utility parsing algorithm: split billing cycles 
        spanning calendar months proportionally (temporal proportional splitting).
        A bill from Dec 15 to Jan 14 spans 30 days total (Dec 15-31: 17 days, Jan 1-14: 13 days).
        """
        # Formulate a mock ConEd utility billing row
        csv_content = (
            "Account Number,Meter Number,Service Start Date,Service End Date,Usage (kWh),Demand (kW),Current Charges ($)\n"
            "CONED-ACCT,CONED-4210,2025-12-15,2026-01-14,3000,50,450.00\n"
        )
        
        batch = IngestionBatch.objects.create(
            tenant=self.tenant,
            source_type='UTILITY',
            file_name="coned_bills.csv",
            uploaded_by=self.user
        )
        
        csv_file = io.StringIO(csv_content)
        processed, failed = ESGDataParser.parse_utility_csv(batch, csv_file)
        
        self.assertEqual(processed, 1)
        self.assertEqual(failed, 0)
        
        # Verify that two ActivityRecords were generated for the single raw row
        sub_activities = ActivityRecord.objects.filter(raw_record__row_index=1).order_by('activity_date')
        self.assertEqual(sub_activities.count(), 2)

        # December activity segment: Dec 15 to Dec 31 (inclusive: 17 days)
        dec_segment = sub_activities[0]
        self.assertEqual(dec_segment.activity_date, date(2025, 12, 15))
        self.assertEqual(dec_segment.end_date, date(2026, 1, 1))
        # December proportion: 17/30 of 3000 kWh = 1700 kWh
        self.assertAlmostEqual(float(dec_segment.quantity), 1700.0, places=1)
        # December Emissions: 1700 kWh * 0.385 EF / 1000 = 0.6545 t CO2e
        self.assertAlmostEqual(float(dec_segment.co2e_emissions), 0.6545, places=4)

        # January activity segment: Jan 1 to Jan 13 (inclusive: 13 days)
        jan_segment = sub_activities[1]
        self.assertEqual(jan_segment.activity_date, date(2026, 1, 1))
        self.assertEqual(jan_segment.end_date, date(2026, 1, 14))
        # January proportion: 13/30 of 3000 kWh = 1300 kWh
        self.assertAlmostEqual(float(jan_segment.quantity), 1300.0, places=1)
        # January Emissions: 1300 kWh * 0.385 EF / 1000 = 0.5005 t CO2e
        self.assertAlmostEqual(float(jan_segment.co2e_emissions), 0.5005, places=4)

    def test_travel_distance_and_cabin_class_multiplier(self):
        """
        Tests the travel parser: converts Origin/Destination IATA codes,
        estimates distance, applies flight length EFs and premium cabin class multipliers.
        JFK to SFO is a Long-Haul Flight (>1600km).
        """
        # Formulate a corporate travel CSV row
        csv_content = (
            "Trip ID,Employee Email,Segment Type,Start Date,End Date,Origin,Destination,Cabin Class,Quantity/Distance,Unit,Amount / Spend,Currency\n"
            "TRIP-101,employee@breathe.com,FLIGHT,2026-06-01,2026-06-01,JFK,SFO,BUSINESS,,,1200,USD\n"
            "TRIP-102,employee@breathe.com,HOTEL,2026-06-01,2026-06-04,JFK,SFO,STANDARD,,,450,USD\n"
        )
        
        batch = IngestionBatch.objects.create(
            tenant=self.tenant,
            source_type='TRAVEL',
            file_name="concur_travel.csv",
            uploaded_by=self.user
        )
        
        csv_file = io.StringIO(csv_content)
        processed, failed = ESGDataParser.parse_travel_csv(batch, csv_file)
        
        self.assertEqual(processed, 2)
        self.assertEqual(failed, 0)
        
        # Verify Flight: Long-Haul, Business Class (2.5x multiplier)
        flight_record = ActivityRecord.objects.get(raw_record__row_index=1)
        self.assertEqual(flight_record.source_type, 'TRAVEL')
        self.assertEqual(flight_record.unit, "pkm")
        
        # Flight distance JFK to SFO is ~4151.3 km
        self.assertAlmostEqual(float(flight_record.quantity), 4151.3, delta=40.0)
        
        # EF used should be Long-Haul Flight = 0.172
        # Emissions = (distance * 0.172 * 2.5 multiplier) / 1000
        expected_emissions = (flight_record.quantity * Decimal('0.172') * Decimal('2.5')) / Decimal('1000.0')
        self.assertAlmostEqual(flight_record.co2e_emissions, expected_emissions, places=5)

        # Verify Hotel: 3 nights stay
        hotel_record = ActivityRecord.objects.get(raw_record__row_index=2)
        self.assertEqual(hotel_record.unit, "room_night")
        self.assertEqual(int(hotel_record.quantity), 3) # June 1 to June 4 = 3 nights
        # EF used should be Hotel Stay = 20.40
        # Emissions = 3 * 20.40 / 1000 = 0.0612 t CO2e
        self.assertAlmostEqual(float(hotel_record.co2e_emissions), 0.0612, places=4)
