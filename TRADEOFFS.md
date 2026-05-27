# Breathe ESG - Trade-offs (TRADEOFFS.md)

To deliver a highly stable, production-grade carbon accounting prototype within the 4-day timeline, we prioritized data-model precision, temporal-splitting accuracy, and comprehensive audit lineage over feature creep. 

Here are the three architectural features we **deliberately did not build** and the justifications for these trade-offs.

---

## 1. Direct SAP OData / Concur API Connectors
*   **What we did not build**: Direct background API synchronization connectors (e.g. polling SAP OData services or setting up Navan/Concur webhook listeners).
*   **The Rationale**: 
    Large enterprise IT environments have highly restricted databases. Installing a direct SAP OData API connector requires ABAP developer resources, custom gateway configurations, and weeks of corporate security, compliance, and firewall sign-offs. 
    Furthermore, every enterprise SAP deployment has customized transaction tables; there is no such thing as a "standard" SAP BAPI or OData API endpoint that works across different corporations out-of-the-box.
    Building a brittle, mock API connector for a prototype is an anti-pattern. Instead, we built a highly robust **CSV Ingestion Pipeline** supporting standard SAP `MB51` and Concur portal reports. This allows immediate onboarding of a new client in under 5 minutes without firewalls or IT ticketing delays.

---

## 2. PDF Scrapers and OCR Engines for Utility Bills
*   **What we did not build**: An optical character recognition (OCR) or document-parsing engine to scrape raw PDF utility statements.
*   **The Rationale**: 
    There are over 3,000 municipal and investor-owned electric utilities in the United States alone, each with highly distinct, frequently changing invoice PDF designs. Scrape-based OCR engines are notoriously brittle and prone to catastrophic failure upon minor layout shifts.
    More importantly, OCR introduces severe compliance risks for carbon accounting. If a scraper misinterprets a digit (e.g., parsing a faded `3` as an `8` or missing a decimal point on a meter reading), the entire emissions report becomes invalid, which can cause severe legal and financial penalties during third-party audits.
    A Portal CSV Export (such as PG&E/ConEd portal downloads) represents the cleanest, mathematically verified service statement. We chose to focus our engineering effort on a robust **temporal proportional calendar-splitting algorithm** to correctly split overlapping billing cycles, which is a mathematically rigorous, auditable solution.

---

## 3. Environmentally Extended Input-Output (EEIO) Spend-Based Carbon Estimation
*   **What we did not build**: A financial spend-based carbon calculator (e.g. converting a procurement spend of $50,000 in SAP to estimated CO₂e based solely on transaction dollars).
*   **The Rationale**: 
    Spend-based carbon accounting (converting currency spend to carbon) is highly inaccurate and volatile. It is heavily distorted by inflation, regional market pricing, currency exchange rate fluctuations, and vendor discounts. 
    Because spend-based data does not represent physical activity, third-party auditors treat spend-based estimations with extreme skepticism, often rejecting them or applying high margins of safety that artificially inflate a company's footprint.
    To ensure the prototype provides actual **audit-locked utility**, we focused entirely on **Activity-Based Carbon Accounting** (Liters of fuel, kilowatt-hours of electricity, and passenger-kilometers of flight distance). If a spend fallback is required (such as ground transport without mileage), we explicitly flag it as an anomaly (`Ground Transport Spend` fallback) so analysts are fully aware of the data-quality gap.
