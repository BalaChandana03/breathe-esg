# Breathe ESG - Architectural Decisions (DECISIONS.md)

This document chronicles every architectural trade-off, unresolved ambiguity, and specific source subset chosen for the **Breathe ESG** data ingestion and review platform prototype.

---

## 1. Ambiguities Resolved & Selected Subsets

### SAP Fuel & Procurement
*   **The Ambiguity**: SAP exports can be complex IDocs, BAPIs, BDC sessions, OData services, or G/L Flat Files. Real-world SAP setups have deeply customized, highly complex technical structures.
*   **The Choice**: We chose a flat-file CSV export modeled after a standard SAP **`MB51` Material Documents List** (Material Transactions Ledger).
*   **Why**: Directly connecting to Large-Enterprise SAP setups using OData or BAPIs requires weeks of corporate firewall clearance, complex RFC destination authorizations, and high SAP Gateway licensing fees. In practice, initial rapid client onboarding relies on G/L or material movement flat-file exports (`MB51` or `FBL3N`). Surfacing a CSV file ingestion portal matches the operational reality of corporate ESG onboarding.
*   **Subset Handled**: We handle the technical and German SAP columns (`MANDT`, `BUKRS`, `WERKS`, `BUDAT`, `MATNR`, `MAKTX`, `MENGE`, `MEINS`, `DMBTR`, `WAERS`, `LIFNR`), dates in German format (`DD.MM.YYYY`), and base unit conversions for fuels (Gallons to Liters) and solid metals (Tons to Kilograms).
*   **Ignored**: We ignore financial currency conversions (assuming the local company code amount is already converted to the local currency, or treating USD/EUR using static coefficients) and ignore raw material batches/revaluation transactions.

### Utility Electricity Statements
*   **The Ambiguity**: Facilities teams get utility data in highly fragmented formats—some download portal CSV exports (like PG&E Green Button), others scrape PDFs, and few have direct utility API access. Additionally, billing cycles don't align with calendar months.
*   **The Choice**: We chose a **Portal CSV Export** modeled after Consolidated Edison (ConEd) statement exports.
*   **Why**: Scraped PDFs are highly fragile and prone to breaking on layout changes. Direct utility APIs (e.g., Green Button Connect) are rare and vary drastically across global utility regions. A structured portal CSV export represents the most stable, standard format accessible to a facility lead.
*   **Subset Handled**: We process non-calendar billing ranges (e.g., Dec 15 to Jan 14). We implement a **temporal proportional splitting algorithm**: calculating the exact day count overlapping with each calendar month, and distributing usage (kWh), costs ($), and emissions proportionally.
*   **Ignored**: We ignore complex commercial multi-tier demand tariffs (e.g., peak/off-peak billing intervals, reactive power charges), since the calculated carbon is solely determined by net cumulative usage (kWh) multiplied by regional grid emissions factors.

### Corporate Travel Platform (Concur / Navan)
*   **The Ambiguity**: Corporate travel feeds represent booking segment records. Travel distance (km/miles) is frequently missing, providing only origin and destination airport codes.
*   **The Choice**: We chose a **Concur-styled Travel Booking CSV export**.
*   **Why**: It is standard for Concur or Navan travel lists to include Flight/Hotel/Car reservation logs. When distances are missing, carbon accounting mandates great-circle distance calculations.
*   **Subset Handled**: We built an internal **IATA Airport Database** of coordinates and implemented the **Haversine formula** to calculate precise flight distances. We classify flights into Short-Haul (<500km), Medium-Haul (500-1600km), and Long-Haul (>1600km) categories and apply GHG Protocol cabin class multipliers (e.g., 2.5x for Business Class, 4.0x for First Class) to account for larger passenger seat space.
*   **Ignored**: We ignore flight layovers (assuming direct flights between origin and destination segments) and flight altitude radiative forcing adjustments.

---

## 2. Inquiries for the Product Manager (PM)

If we were to align with the PM on the roadmap, we would immediately ask:

1.  **Scope 2 Market-based vs. Location-based Accounting**:
    > [!IMPORTANT]
    > Currently, our utility module uses regional location-based grid factors (e.g., CA grid vs. NY grid blend). Does the client intend to report **market-based emissions**? If so, we need to allow analysts to map specific renewable Power Purchase Agreements (PPAs) or Green Tariffs to facilities, offsetting grid consumption to zero.
2.  **Plant-to-Facility Mapping Interface**:
    > [!NOTE]
    > In our prototype, unmapped plant codes (`WERKS`) or utility meters trigger an inline anomaly flag (`unmapped_plant`, `unmapped_meter`). Analysts can resolve this by overriding the row and choosing a Facility. Should we build a dedicated **Facility Mapper Dashboard** where administrators can set up structural map tables (e.g. mapping `WERKS-9999` to "Chicago HQ") globally, re-triggering normalization automatically?
3.  **Historical Emission Factor Versioning**:
    > [!WARNING]
    > Carbon coefficients change annually as regional power grids decarbonize. Does the platform need to store and version emission factors by **Calendar Year**? If so, our lookup query must match not only the source type, but also the year of the activity date.
