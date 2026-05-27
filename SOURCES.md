# Breathe ESG - Ingestion Source Research & Realities (SOURCES.md)

This document details the real-world formats researched, technical column representations, and specific edge cases handled for each of the three ingestion sources.

---

## 1. SAP ERP: Fuel & Procurement Data (Scope 1 & Scope 3)

### Real-World Research & Format
In Large-Enterprise ERP setups, material documents are tracked in standard transaction logs. We researched the standard **`MB51` Material Documents List** export format. When an enterprise purchases diesel fuel, steel, or concrete, it triggers material movement transactions (e.g. Movement Type 101 for goods receipt, 201 for consumption).

### Research Findings & Realities
*   **Messy Column Headers**: SAP layouts utilize technical German names or custom field labels depending on installation localization. 
*   **Unit Inconsistencies**: Fuels are measured in gallons (`GAL`) or liters (`L`), while structural metals are tracked in metric tons (`TO` / `TON`) or kilograms (`KG`).
*   **German Date formats**: Dates are typically exported in standard German dot notation (`DD.MM.YYYY`, e.g., `25.05.2026`).
*   **Lookup Dependencies**: Plant codes (`WERKS`) have no meaning without an organization map. They must be resolved against an operational facility registry.

### Sample Data Shape (`sap_fuel_procurement.csv`)
Our sample data utilizes a standardized header mapping that accommodates standard technical names:
```csv
WERKS,BUDAT,MATNR,MAKTX,MENGE,MEINS,DMBTR,WAERS,LIFNR
WERKS-1001,15.04.2026,FUEL-DIESEL,Diesel Fuel (Stationary),1500,GAL,5400.00,USD,LIFNR-9001
WERKS-1002,18.04.2026,PROC-STEEL,Reinforcement Steel Columns,12,TO,21600.00,EUR,LIFNR-9002
WERKS-9999,25.04.2026,FUEL-GASOLINE,Premium Unleaded Fuel,450,L,780.00,USD,LIFNR-9003
```

### Handled Edge Cases & Recalculations
1.  **Header Normalization**: The parser maps German and English lowercase labels (e.g., `werk`, `basiseinheit`, `menge`) to standard technical abbreviations.
2.  **Date Parsing**: Handles standard dot notation (`%d.%m.%Y`) and ISO-8601 (`%Y-%m-%d`).
3.  **Liters & Kilograms Standardization**: Convert `GAL` to standard `L` (factor 3.78541) and `TO` to `KG` (factor 1000).
4.  **Facility lookup validation**: Matches `WERKS` against database registries. If unmapped (like `WERKS-9999`), it flags `unmapped_plant` inside `anomaly_flags`.

### What would break in a real deployment?
SAP installations utilize customized transaction fields (e.g. custom field `ZZ_EMISSION_CAT`). If a client modifies their standard export, header mappings can fail. A production deployment requires a flexible schema-mapping interface to let clients map custom headers dynamically on upload.

---

## 2. Utility Portal Statement: Electricity (Scope 2)

### Real-World Research & Format
Facilities teams download electricity data directly from customer portals of regional utilities (such as Consolidated Edison - ConEd or PG&E). We modeled our export format after the ConEd Commercial portal billing statement export.

### Research Findings & Realities
*   **Non-Aligned Billing Cycles**: A utility bill rarely aligns with a calendar month (e.g., billing spanning Dec 14 to Jan 15). ESG disclosures require strict calendar monthly accounting.
*   **Tariff Complexity**: Billing records contain peak demand power charges ($kW$), energy usage ($kWh$), reactive power, and tax riders.
*   **Reading Shifts**: Occasional estimated readings (instead of actual meter sweeps) can skew data.

### Sample Data Shape (`coned_electricity.csv`)
```csv
Account Number,Meter Number,Service Start Date,Service End Date,Usage (kWh),Demand (kW),Current Charges ($)
CONED-ACCT-01,CONED-4210,2025-12-15,2026-01-14,3500,45,$495.00
CONED-ACCT-02,MTR-9876,2026-02-10,2026-03-11,9800,85,$1450.00
```

### Handled Edge Cases & Recalculations
1.  **Temporal Proportional Splitting**:
    Our parser automatically distributes energy consumption and carbon emissions to calendar months:
    $$\text{Month proportion} = \frac{\text{Days of billing cycle in target month}}{\text{Total days in billing cycle}}$$
    This ensures audit-compliant calendar reporting.
2.  **Consumption Spike Detection**:
    Calculates historical averages. If a meter's usage spikes $> 2\times$ average (such as row 4 in the sample), it logs a `usage_spike` flag to highlight potential data errors or facility malfunctions.
3.  **Regional Grid Emission Factors**:
    Automatically matches the facility's region to grid coefficients. If unassigned, defaults to the US national average.

### What would break in a real deployment?
If billing cycles overlap with previously uploaded files, double-counting will occur. A production setup requires a meter-level temporal overlap-check to block duplicate billing uploads.

---

## 3. Corporate Travel Platform (Scope 3 Category 6)

### Real-World Research & Format
Corporate travel platforms (such as Concur, Navan, or Egencia) generate reservation feeds. We researched the Navan / Concur Travel Booking Segment reports.

### Research Findings & Realities
*   **Missing Mileage**: Segment rows provide Origin/Destination IATA codes (e.g. `SFO`, `JFK`, `LHR`), but frequently omit actual travel distance.
*   **Cabin Class Multipliers**: Economy and Business class travelers occupy different amounts of cabin floor space. Under the GHG Protocol, Business class flights carry a much higher emissions factor (e.g., 2.5x) to account for spatial displacement.
*   **Spend-based fallbacks**: Ground transport (taxis, car rentals) often lack mileage inputs, providing only transaction currency spend.

### Sample Data Shape (`corporate_travel.csv`)
```csv
Trip ID,Employee Email,Segment Type,Start Date,End Date,Origin,Destination,Cabin Class,Quantity/Distance,Unit,Amount / Spend,Currency
TRIP-7001,exec@breathe.com,FLIGHT,2026-04-10,2026-04-10,JFK,SFO,BUSINESS,,,1800.00,USD
TRIP-7001,exec@breathe.com,HOTEL,2026-04-10,2026-04-13,SFO,SFO,STANDARD,,,900.00,USD
TRIP-7004,staff@breathe.com,FLIGHT,2026-04-20,2026-04-20,XYZ,JFK,ECONOMY,,,650.00,USD
```

### Handled Edge Cases & Recalculations
1.  **IATA Distance Calculation**:
    If distance is omitted, we run coordinates lookup from our database and calculate great-circle distances via the **Haversine formula**.
2.  **Cabin Class Scaling**:
    Applies standard DEFRA multipliers: `PREMIUM_ECONOMY` (1.6x), `BUSINESS` (2.5x), and `FIRST` (4.0x).
3.  **Distance Categorization**:
    Sorts flights into Short-Haul (<500km), Medium-Haul (500-1600km), or Long-Haul (>1600km) to map energy intensities accurately.
4.  **Spend Fallback**:
    If car rental distance is missing, it applies spend-based Category 6 emissions factors ($kg\text{ CO}_2\text{e}/\text{USD}$).
5.  **Lookup failures**:
    If an invalid airport code is supplied (like `XYZ` in row 5), it flags `airport_coordinate_lookup_failed`.

### What would break in a real deployment?
Multi-destination flights (e.g., `JFK` -> `ORD` -> `SFO` booked as a single line) will yield incorrect great-circle distances if only start/end destinations are parsed. A production environment must split bookings into individual flight segments.
