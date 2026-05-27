import csv
import math
from datetime import datetime, timedelta
from decimal import Decimal
import io
import json

from django.db import transaction
from django.contrib.auth.models import User
from .models import Tenant, Facility, Airport, EmissionFactor, IngestionBatch, RawRecord, ActivityRecord, AuditLog

# Hardcoded fallback airport data for instant out-of-the-box operation
FALLBACK_AIRPORTS = {
    'JFK': {'name': 'John F. Kennedy International Airport', 'lat': 40.6398, 'lon': -73.7789},
    'SFO': {'name': 'San Francisco International Airport', 'lat': 37.6190, 'lon': -122.3749},
    'LHR': {'name': 'London Heathrow Airport', 'lat': 51.4700, 'lon': -0.4543},
    'CDG': {'name': 'Paris Charles de Gaulle Airport', 'lat': 49.0097, 'lon': 2.5479},
    'DXB': {'name': 'Dubai International Airport', 'lat': 25.2532, 'lon': 55.3657},
    'SIN': {'name': 'Singapore Changi Airport', 'lat': 1.3644, 'lon': 103.9915},
    'HND': {'name': 'Tokyo Haneda Airport', 'lat': 35.5494, 'lon': 139.7798},
    'SYD': {'name': 'Sydney Airport', 'lat': -33.9461, 'lon': 151.1772},
    'ORD': {'name': 'Chicago O\'Hare International Airport', 'lat': 41.9742, 'lon': -87.9073},
    'LAX': {'name': 'Los Angeles International Airport', 'lat': 33.9416, 'lon': -118.4085},
    'FRA': {'name': 'Frankfurt Airport', 'lat': 50.0379, 'lon': 8.5622},
    'AMS': {'name': 'Amsterdam Schiphol Airport', 'lat': 52.3105, 'lon': 4.7683},
    'DEL': {'name': 'Indira Gandhi International Airport', 'lat': 28.5562, 'lon': 77.1000},
    'BOM': {'name': 'Chhatrapati Shivaji Maharaj International Airport', 'lat': 19.0896, 'lon': 72.8656},
    'BLR': {'name': 'Kempegowda International Airport', 'lat': 13.1986, 'lon': 77.7066},
}

def calculate_haversine_distance(lat1, lon1, lat2, lon2):
    """
    Computes Great Circle Distance in kilometers between two coordinates.
    """
    R = 6371.0 # Earth's radius in km
    lat1_rad = math.radians(float(lat1))
    lon1_rad = math.radians(float(lon1))
    lat2_rad = math.radians(float(lat2))
    lon2_rad = math.radians(float(lon2))
    
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad
    
    a = math.sin(dlat / 2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2)**2
    c = 2 * math.asin(math.sqrt(a))
    return R * c

def get_airport_coordinates(iata_code):
    """
    Looks up airport in DB, falls back to static dictionary.
    """
    iata_code = iata_code.strip().upper()
    try:
        airport = Airport.objects.get(iata_code=iata_code)
        return float(airport.latitude), float(airport.longitude)
    except Airport.DoesNotExist:
        if iata_code in FALLBACK_AIRPORTS:
            data = FALLBACK_AIRPORTS[iata_code]
            return data['lat'], data['lon']
    return None

class ESGDataParser:
    @staticmethod
    def parse_sap_csv(batch, csv_file_wrapper):
        """
        Parses SAP MB51 export flat files.
        Headers: MANDT, BUKRS, WERKS, BUDAT, MATNR, MAKTX, MENGE, MEINS, DMBTR, WAERS, LIFNR
        Can handle German headers: Mandant, Buchungskreis, Werk, Buchungsdatum, Material, Materialkurztext, Menge, Basiseinheit, Betrag, Waehrung
        Dates in format DD.MM.YYYY
        """
        reader = csv.DictReader(csv_file_wrapper)
        
        # Mappings for German / Alternate technical headers
        header_mapping = {
            'mandant': 'MANDT', 'client': 'MANDT',
            'buchungskreis': 'BUKRS', 'company code': 'BUKRS',
            'werk': 'WERKS', 'plant': 'WERKS',
            'buchungsdatum': 'BUDAT', 'posting date': 'BUDAT',
            'material': 'MATNR', 'material number': 'MATNR',
            'materialkurztext': 'MAKTX', 'material description': 'MAKTX',
            'menge': 'MENGE', 'quantity': 'MENGE',
            'basiseinheit': 'MEINS', 'unit': 'MEINS', 'base unit': 'MEINS',
            'betrag': 'DMBTR', 'amount': 'DMBTR',
            'waehrung': 'WAERS', 'currency': 'WAERS',
            'lieferant': 'LIFNR', 'vendor': 'LIFNR'
        }

        # Normalize headers to standard SAP abbreviations
        original_headers = reader.fieldnames
        normalized_headers_map = {}
        for h in original_headers:
            h_lower = h.strip().lower()
            if h in ['MANDT', 'BUKRS', 'WERKS', 'BUDAT', 'MATNR', 'MAKTX', 'MENGE', 'MEINS', 'DMBTR', 'WAERS', 'LIFNR']:
                normalized_headers_map[h] = h
            elif h_lower in header_mapping:
                normalized_headers_map[h] = header_mapping[h_lower]
            else:
                normalized_headers_map[h] = h

        row_index = 0
        total_rows = 0
        processed_rows = 0
        failed_rows = 0
        errors = []

        for row in reader:
            row_index += 1
            total_rows += 1
            
            # Map columns to standard technical codes
            normalized_row = {normalized_headers_map.get(k, k): v for k, v in row.items()}
            
            # Create RawRecord to guarantee audit trail
            raw_record = RawRecord.objects.create(
                batch=batch,
                row_index=row_index,
                raw_payload=row,
                status='UNPROCESSED'
            )

            try:
                # Required validations
                werks = normalized_row.get('WERKS', '').strip()
                budat = normalized_row.get('BUDAT', '').strip()
                matnr = normalized_row.get('MATNR', '').strip()
                quantity_str = normalized_row.get('MENGE', '').strip().replace(',', '')
                unit = normalized_row.get('MEINS', '').strip().upper()
                amount_str = normalized_row.get('DMBTR', '').strip().replace(',', '')

                if not werks or not budat or not matnr or not quantity_str:
                    raise ValueError(f"Missing mandatory fields in row {row_index}: Plant, Date, Material, and Quantity are required.")

                # Date parsing: DD.MM.YYYY or YYYY-MM-DD
                try:
                    if '.' in budat:
                        activity_date = datetime.strptime(budat, '%d.%m.%Y').date()
                    else:
                        activity_date = datetime.strptime(budat, '%Y-%m-%d').date()
                except ValueError:
                    raise ValueError(f"Invalid Date format: '{budat}'. Expected formats: DD.MM.YYYY or YYYY-MM-DD")

                # Parse numbers
                try:
                    original_quantity = Decimal(quantity_str)
                    amount = Decimal(amount_str) if amount_str else Decimal('0.00')
                except Exception:
                    raise ValueError(f"Failed to parse numeric quantity '{quantity_str}' or Betrag '{amount_str}'.")

                # Identify ESG Facility by Plant Code
                facility = Facility.objects.filter(tenant=batch.tenant, facility_code=werks).first()
                anomaly_flags = {}
                if not facility:
                    # Flag anomaly: Unmapped SAP plant code
                    anomaly_flags['unmapped_plant'] = True

                # Determine scope & category based on SAP Material ID (MATNR)
                matnr_upper = matnr.upper()
                category = ""
                scope = 3
                factor_category = ""
                normalized_unit = unit
                normalized_quantity = original_quantity

                # Carbon Calculation logic
                if 'FUEL-DIESEL' in matnr_upper or 'DIESEL' in normalized_row.get('MAKTX', '').upper():
                    scope = 1
                    category = "Direct Emissions (Stationary Fuel Combustion)"
                    factor_category = "Diesel Fuel"
                    # Unit conversion: standard fuel unit is Liter (L)
                    if unit in ['GAL', 'GLL']:
                        normalized_unit = 'L'
                        normalized_quantity = original_quantity * Decimal('3.78541')
                    elif unit in ['L', 'LTR']:
                        normalized_unit = 'L'
                    else:
                        anomaly_flags['unsupported_unit_conversion'] = True
                elif 'FUEL-GASOLINE' in matnr_upper or 'GASOLINE' in normalized_row.get('MAKTX', '').upper():
                    scope = 1
                    category = "Direct Emissions (Stationary Fuel Combustion)"
                    factor_category = "Gasoline Fuel"
                    if unit in ['GAL', 'GLL']:
                        normalized_unit = 'L'
                        normalized_quantity = original_quantity * Decimal('3.78541')
                    elif unit in ['L', 'LTR']:
                        normalized_unit = 'L'
                elif 'PROC-STEEL' in matnr_upper or 'STEEL' in normalized_row.get('MAKTX', '').upper():
                    scope = 3
                    category = "Scope 3: Purchased Goods & Services (Steel)"
                    factor_category = "Steel"
                    if unit in ['TO', 'TON']:
                        normalized_unit = 'KG'
                        normalized_quantity = original_quantity * Decimal('1000')
                    elif unit in ['KG', 'KGS']:
                        normalized_unit = 'KG'
                elif 'PROC-CONCRETE' in matnr_upper or 'CONCRETE' in normalized_row.get('MAKTX', '').upper():
                    scope = 3
                    category = "Scope 3: Purchased Goods & Services (Concrete)"
                    factor_category = "Concrete"
                    if unit in ['TO', 'TON']:
                        normalized_unit = 'KG'
                        normalized_quantity = original_quantity * Decimal('1000')
                    elif unit in ['KG', 'KGS']:
                        normalized_unit = 'KG'
                else:
                    # Default Procurement Category
                    scope = 3
                    category = f"Scope 3: Purchased Goods & Services ({normalized_row.get('MAKTX', 'Other Material')})"
                    factor_category = "General Purchased Goods"
                    normalized_unit = 'KG' if unit in ['KG', 'TO', 'TON'] else unit

                # Retrieve emission factor
                ef = EmissionFactor.objects.filter(
                    source_type='SAP',
                    category=factor_category,
                    active=True
                ).first()

                if not ef:
                    # Fallback EF if not defined in DB
                    if scope == 1:
                        factor_value = Decimal('2.68') # Default Diesel/Gasoline standard kg CO2e/L
                    else:
                        factor_value = Decimal('1.90') # Default Scope 3 factor per kg
                    ef_used = factor_value
                else:
                    ef_used = ef.factor

                # Emissions calculation (quantity * factor) / 1000 to convert kg CO2e to Metric Tons (t CO2e)
                co2e_emissions = (normalized_quantity * ef_used) / Decimal('1000.0')

                # Create Normalized Activity Record
                activity = ActivityRecord.objects.create(
                    tenant=batch.tenant,
                    facility=facility,
                    raw_record=raw_record,
                    source_type='SAP',
                    scope=scope,
                    category=category,
                    activity_date=activity_date,
                    quantity=normalized_quantity,
                    unit=normalized_unit,
                    original_quantity=original_quantity,
                    original_unit=unit,
                    co2e_emissions=co2e_emissions,
                    emission_factor_used=ef_used,
                    status='PENDING_REVIEW',
                    anomaly_flags=anomaly_flags
                )

                # Log creation in AuditLog
                AuditLog.objects.create(
                    activity_record=activity,
                    action='CREATE',
                    changes={
                        'message': 'SAP record normalized and calculated.',
                        'original_werks': werks,
                        'original_quantity': str(original_quantity),
                        'original_unit': unit,
                        'emissions_calculated_t_co2e': str(co2e_emissions)
                    }
                )

                # Mark raw record as validated
                raw_record.status = 'VALIDATED'
                raw_record.save()
                processed_rows += 1

            except Exception as e:
                failed_rows += 1
                errors.append(f"Row {row_index} error: {str(e)}")
                raw_record.status = 'ERROR'
                raw_record.error_message = str(e)
                raw_record.save()

        # Update batch summary
        batch.total_rows = total_rows
        batch.processed_rows = processed_rows
        batch.failed_rows = failed_rows
        if errors:
            batch.status = 'FAILED'
            batch.error_summary = "\n".join(errors[:20]) # Limit summary length
        else:
            batch.status = 'SUCCESS'
        batch.save()

        return processed_rows, failed_rows

    @staticmethod
    def parse_utility_csv(batch, csv_file_wrapper):
        """
        Parses Utility Electricity Statement CSVs.
        Headers: Account Number, Meter Number, Service Start Date, Service End Date, Usage (kWh), Demand (kW), Current Charges ($)
        Accommodates non-calendar-aligned billing cycles (e.g. Dec 14 to Jan 15) using temporal proportional splitting.
        """
        reader = csv.DictReader(csv_file_wrapper)
        row_index = 0
        total_rows = 0
        processed_rows = 0
        failed_rows = 0
        errors = []

        for row in reader:
            row_index += 1
            total_rows += 1
            
            raw_record = RawRecord.objects.create(
                batch=batch,
                row_index=row_index,
                raw_payload=row,
                status='UNPROCESSED'
            )

            try:
                account_num = row.get('Account Number', '').strip()
                meter_num = row.get('Meter Number', '').strip()
                start_date_str = row.get('Service Start Date', '').strip()
                end_date_str = row.get('Service End Date', '').strip()
                usage_str = row.get('Usage (kWh)', '').strip().replace(',', '')
                charges_str = row.get('Current Charges ($)', '').strip().replace('$', '').replace(',', '')

                if not meter_num or not start_date_str or not end_date_str or not usage_str:
                    raise ValueError(f"Missing mandatory utility fields in row {row_index}: Meter, Service Dates, and Usage (kWh) are required.")

                # Date parsing
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                total_usage = Decimal(usage_str)
                total_charges = Decimal(charges_str) if charges_str else Decimal('0.00')

                if end_date <= start_date:
                    raise ValueError(f"Service End Date ({end_date_str}) must be after Service Start Date ({start_date_str}).")

                # Map Facility by Meter Number or Account Number
                facility = Facility.objects.filter(tenant=batch.tenant, facility_code=meter_num).first()
                if not facility:
                    facility = Facility.objects.filter(tenant=batch.tenant, facility_code=account_num).first()
                
                anomaly_flags = {}
                if not facility:
                    anomaly_flags['unmapped_meter'] = True

                # Check for Usage Spikes (Anomalies)
                # Query historical usage for this meter / account
                avg_usage = Decimal('0.00')
                historical_records = ActivityRecord.objects.filter(
                    tenant=batch.tenant,
                    source_type='UTILITY',
                    original_unit='kWh'
                )
                if facility:
                    historical_records = historical_records.filter(facility=facility)
                else:
                    historical_records = historical_records.filter(raw_record__batch__tenant=batch.tenant)
                
                hist_count = historical_records.count()
                if hist_count > 0:
                    hist_sum = sum([r.quantity for r in historical_records])
                    avg_usage = hist_sum / Decimal(hist_count)
                    if avg_usage > 0 and total_usage > (avg_usage * Decimal('2.0')):
                        anomaly_flags['usage_spike'] = True

                # Split non-calendar-aligned cycles into calendar months
                days_by_month = {}
                curr_date = start_date
                total_days = (end_date - start_date).days

                if total_days <= 0:
                    total_days = 1 # Avoid division by zero

                # Count overlapping days for each calendar month in the range
                while curr_date < end_date:
                    month_key = (curr_date.year, curr_date.month)
                    days_by_month[month_key] = days_by_month.get(month_key, 0) + 1
                    curr_date += timedelta(days=1)

                # Retrieve Regional Grid Emission Factor
                region_name = facility.region if (facility and facility.region) else 'US-AVERAGE'
                ef = EmissionFactor.objects.filter(
                    source_type='UTILITY',
                    category='Purchased Electricity',
                    region=region_name,
                    active=True
                ).first()
                
                if not ef:
                    # US Average Grid factor: ~0.37 kg CO2e / kWh
                    ef_used = Decimal('0.370')
                else:
                    ef_used = ef.factor

                # Generate proportional calendar month records
                sub_records = []
                for (year, month), overlap_days in days_by_month.items():
                    proportion = Decimal(overlap_days) / Decimal(total_days)
                    prop_usage = total_usage * proportion
                    prop_charges = total_charges * proportion
                    
                    # Proportional Emissions: prop_usage * ef / 1000 (t CO2e)
                    prop_emissions = (prop_usage * ef_used) / Decimal('1000.0')
                    
                    month_start_date = datetime(year, month, 1).date()
                    # Calculate end date for this sub-segment
                    sub_start = max(start_date, month_start_date)
                    if month == 12:
                        next_month_start = datetime(year + 1, 1, 1).date()
                    else:
                        next_month_start = datetime(year, month + 1, 1).date()
                    sub_end = min(end_date, next_month_start)

                    activity = ActivityRecord.objects.create(
                        tenant=batch.tenant,
                        facility=facility,
                        raw_record=raw_record,
                        source_type='UTILITY',
                        scope=2,
                        category="Scope 2: Purchased Electricity (Market/Location-based)",
                        activity_date=sub_start,
                        end_date=sub_end,
                        quantity=prop_usage,
                        unit='kWh',
                        original_quantity=total_usage * proportion,
                        original_unit='kWh',
                        co2e_emissions=prop_emissions,
                        emission_factor_used=ef_used,
                        status='PENDING_REVIEW',
                        anomaly_flags=anomaly_flags
                    )

                    AuditLog.objects.create(
                        activity_record=activity,
                        action='CREATE',
                        changes={
                            'message': f"Utility cycle split proportionally. Segment allocated: {overlap_days}/{total_days} days.",
                            'segment_days': overlap_days,
                            'segment_usage_kwh': str(prop_usage),
                            'segment_charges_usd': str(prop_charges),
                            'grid_emission_factor_used': str(ef_used)
                        }
                    )
                    sub_records.append(activity)

                raw_record.status = 'VALIDATED'
                raw_record.save()
                processed_rows += 1

            except Exception as e:
                failed_rows += 1
                errors.append(f"Row {row_index} error: {str(e)}")
                raw_record.status = 'ERROR'
                raw_record.error_message = str(e)
                raw_record.save()

        # Update batch summary
        batch.total_rows = total_rows
        batch.processed_rows = processed_rows
        batch.failed_rows = failed_rows
        if errors:
            batch.status = 'FAILED'
            batch.error_summary = "\n".join(errors[:20])
        else:
            batch.status = 'SUCCESS'
        batch.save()

        return processed_rows, failed_rows

    @staticmethod
    def parse_travel_csv(batch, csv_file_wrapper):
        """
        Parses Corporate Travel Platform exports (e.g. Concur Travel).
        Headers: Trip ID, Employee Email, Segment Type, Start Date, End Date, Origin, Destination, Cabin Class, Quantity/Distance, Unit, Amount / Spend, Currency
        Origin/Destination are IATA codes (e.g. SFO, JFK). Computes Great-Circle Distance using Haversine formula when missing.
        """
        reader = csv.DictReader(csv_file_wrapper)
        row_index = 0
        total_rows = 0
        processed_rows = 0
        failed_rows = 0
        errors = []

        for row in reader:
            row_index += 1
            total_rows += 1
            
            raw_record = RawRecord.objects.create(
                batch=batch,
                row_index=row_index,
                raw_payload=row,
                status='UNPROCESSED'
            )

            try:
                trip_id = row.get('Trip ID', '').strip()
                segment_type = row.get('Segment Type', '').strip().upper()
                start_date_str = row.get('Start Date', '').strip()
                end_date_str = row.get('End Date', '').strip()
                origin = row.get('Origin', '').strip().upper()
                destination = row.get('Destination', '').strip().upper()
                cabin_class = row.get('Cabin Class', '').strip().upper()
                distance_str = row.get('Quantity/Distance', '').strip().replace(',', '')
                unit = row.get('Unit', '').strip().upper()
                spend_str = row.get('Amount / Spend', '').strip().replace(',', '')

                if not segment_type or not start_date_str or not end_date_str:
                    raise ValueError(f"Missing mandatory travel fields in row {row_index}: Segment, Start, and End dates are required.")

                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
                spend = Decimal(spend_str) if spend_str else Decimal('0.00')

                anomaly_flags = {}
                category = f"Scope 3 Category 6: Business Travel ({segment_type.capitalize()})"
                quantity = Decimal('0.00')
                normalized_unit = ''
                original_qty = Decimal('0.00')
                ef_category = ''
                
                # Cabin class multiplier (Standard GHG Protocol multipliers)
                class_multiplier = Decimal('1.0')
                if cabin_class == 'BUSINESS':
                    class_multiplier = Decimal('2.5')
                elif cabin_class == 'FIRST':
                    class_multiplier = Decimal('4.0')
                elif cabin_class == 'PREMIUM_ECONOMY':
                    class_multiplier = Decimal('1.6')

                if segment_type == 'FLIGHT':
                    if not origin or not destination:
                        raise ValueError("Origin and Destination airport codes are required for Flights.")

                    # Calculate distance
                    distance_km = Decimal('0.00')
                    coords_origin = get_airport_coordinates(origin)
                    coords_dest = get_airport_coordinates(destination)

                    if coords_origin and coords_dest:
                        km = calculate_haversine_distance(coords_origin[0], coords_origin[1], coords_dest[0], coords_dest[1])
                        distance_km = Decimal(str(round(km, 2)))
                    else:
                        anomaly_flags['airport_coordinate_lookup_failed'] = True
                        # If coordinates are missing, check if distance was supplied in CSV
                        if distance_str:
                            orig_dist = Decimal(distance_str)
                            if unit in ['MI', 'MILES']:
                                distance_km = orig_dist * Decimal('1.60934')
                            else:
                                distance_km = orig_dist
                        else:
                            raise ValueError(f"Could not compute or locate flight distance between {origin} and {destination}.")

                    # Determine flight length category (standard DEFRA/EPA categorizations)
                    if distance_km < Decimal('500.0'):
                        ef_category = "Short-Haul Flight"
                    elif distance_km <= Decimal('1600.0'):
                        ef_category = "Medium-Haul Flight"
                    else:
                        ef_category = "Long-Haul Flight"

                    # Standard unit: Passenger-Kilometer (pkm)
                    quantity = distance_km
                    normalized_unit = 'pkm'
                    original_qty = Decimal(distance_str) if distance_str else distance_km

                elif segment_type == 'HOTEL':
                    nights = (end_date - start_date).days
                    if nights <= 0:
                        nights = 1
                    ef_category = "Hotel Stay"
                    quantity = Decimal(str(nights))
                    normalized_unit = 'room_night'
                    original_qty = quantity

                elif segment_type in ['CAR', 'GROUND', 'RAIL']:
                    ef_category = "Ground Transport"
                    normalized_unit = 'km'
                    if distance_str:
                        orig_dist = Decimal(distance_str)
                        if unit in ['MI', 'MILES']:
                            quantity = orig_dist * Decimal('1.60934')
                        else:
                            quantity = orig_dist
                        original_qty = orig_dist
                    else:
                        # Spend-based fallback if distance is missing
                        quantity = spend
                        normalized_unit = 'USD'
                        original_qty = spend
                        ef_category = "Ground Transport Spend"

                else:
                    raise ValueError(f"Unsupported travel segment type: '{segment_type}'")

                # Retrieve emission factor
                ef = EmissionFactor.objects.filter(
                    source_type='TRAVEL',
                    category=ef_category,
                    active=True
                ).first()

                if not ef:
                    # Fallbacks
                    if ef_category == "Short-Haul Flight":
                        factor_val = Decimal('0.25') # kg CO2e / pkm
                    elif ef_category == "Medium-Haul Flight":
                        factor_val = Decimal('0.19')
                    elif ef_category == "Long-Haul Flight":
                        factor_val = Decimal('0.17')
                    elif ef_category == "Hotel Stay":
                        factor_val = Decimal('20.40') # kg CO2e / room_night
                    elif ef_category == "Ground Transport":
                        factor_val = Decimal('0.21') # kg CO2e / km
                    else:
                        factor_val = Decimal('0.46') # spend fallback kg / USD
                    ef_used = factor_val
                else:
                    ef_used = ef.factor

                # Calculations (quantity * ef * cabin_multiplier) / 1000 (t CO2e)
                multiplier = class_multiplier if segment_type == 'FLIGHT' else Decimal('1.0')
                co2e_emissions = (quantity * ef_used * multiplier) / Decimal('1000.0')

                # Create Normalized Activity Record
                activity = ActivityRecord.objects.create(
                    tenant=batch.tenant,
                    facility=None, # Business travel is usually organization-wide, not bound to a physical plant
                    raw_record=raw_record,
                    source_type='TRAVEL',
                    scope=3,
                    category=category,
                    activity_date=start_date,
                    end_date=end_date,
                    quantity=quantity,
                    unit=normalized_unit,
                    original_quantity=original_qty,
                    original_unit=unit if unit else normalized_unit,
                    co2e_emissions=co2e_emissions,
                    emission_factor_used=ef_used,
                    status='PENDING_REVIEW',
                    anomaly_flags=anomaly_flags
                )

                AuditLog.objects.create(
                    activity_record=activity,
                    action='CREATE',
                    changes={
                        'message': 'Corporate travel booking normalized.',
                        'trip_id': trip_id,
                        'segment_type': segment_type,
                        'cabin_class': cabin_class,
                        'cabin_multiplier': str(multiplier),
                        'calculated_distance_km': str(quantity) if segment_type == 'FLIGHT' else 'N/A',
                        'emissions_calculated_t_co2e': str(co2e_emissions)
                    }
                )

                raw_record.status = 'VALIDATED'
                raw_record.save()
                processed_rows += 1

            except Exception as e:
                failed_rows += 1
                errors.append(f"Row {row_index} error: {str(e)}")
                raw_record.status = 'ERROR'
                raw_record.error_message = str(e)
                raw_record.save()

        # Update batch summary
        batch.total_rows = total_rows
        batch.processed_rows = processed_rows
        batch.failed_rows = failed_rows
        if errors:
            batch.status = 'FAILED'
            batch.error_summary = "\n".join(errors[:20])
        else:
            batch.status = 'SUCCESS'
        batch.save()

        return processed_rows, failed_rows
