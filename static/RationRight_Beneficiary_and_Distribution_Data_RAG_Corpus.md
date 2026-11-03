---
title: "RationRight: National Public Distribution System (PDS) Beneficiary & Operational Telemetry Corpus"
document_id: "NFSA-OPS-DATASET-2026-AUG-CORPUS"
version: "2026.8"
date: "2026-11-02"
authority: "National Food Security Act (NFSA), 2013"
target_use_case: "Retrieval-Augmented Generation (RAG), Vector Embeddings, LLM Evaluation"
total_beneficiaries: 24582
active_verified: 23410
daily_outflow_kg: 43450.5
strategic_reserves_kg: 7961167.9
fair_price_shops_count: 414
---

# RationRight: National PDS Beneficiary & Operational Telemetry Knowledge Corpus

## Executive Summary
This document serves as the ground-truth knowledge corpus for the RationRight Food Security Platform. It contains verified beneficiary entitlement profiles, Fair Price Shop (FPS) distribution outlet telemetry, buffer inventory levels, and AI fraud detection incident records. It is structured specifically for chunking, embedding generation, and high-precision semantic retrieval in RAG architectures.

---

## 1. NFSA Regulatory Framework & Entity Schema

### Welfare Categories:
1. **Antyodaya Anna Yojana (AAY):**
   - **Target Demographic:** Poorest of the poor families and destitute households.
   - **Statutory Quota:** Flat allocation of **35.0 kg of foodgrains per family per month**, regardless of the number of family members in the household.
   - **Standard Composition:** 20.0 kg Rice (Grade A) + 15.0 kg Wheat (Standard Milling).
   - **Subsidized Price:** Subsidized central issue price (historically ₹3/kg rice, ₹2/kg wheat; 100% free under PMGKAY).

2. **Priority Households (PHH):**
   - **Target Demographic:** Eligible low-income households identified by state government criteria.
   - **Statutory Quota:** **5.0 kg of foodgrains per individual member per month**.
   - **Calculation Formula:** `Total Monthly Grain (kg) = Family Member Count × 5.0 kg`.
   - **Example:** A family of 4 members receives `4 × 5.0 kg = 20.0 kg` (typically 12 kg Rice + 8 kg Wheat).

### Distribution Infrastructure:
- **Fair Price Shop (FPS):** Licensed local distribution retail outlets equipped with electronic Point-of-Sale (ePOS) devices.
- **Biometric Aadhaar Authentication:** Optical fingerprint scanner or dual-iris recognition required at the point of distribution.
- **Offline Fallback Mode:** Store-and-forward mode permitted for up to 72 hours in rural low-bandwidth areas, requiring subsequent automatic cloud synchronization.

---

## 2. Key Operational Benchmarks & System KPIs

| Metric Name | Current Recorded Value | Benchmark Comparison | Operational Status |
| :--- | :--- | :--- | :--- |
| **Total Registered Beneficiaries** | 24,582 Enrolled | +3.2% vs previous 30-day window | 95.2% Active Coverage |
| **Active Verified Cardholders** | 23,410 Active | 1,172 Pending/Flagged | Biometrically Verified |
| **Daily Grain Outflow (Today)** | 43,450.5 kg | +9.7% vs 7-day rolling average | 4,520 Verified Transactions |
| **Central Silo Buffer Stock** | 79,61,167.9 kg | 88.2% Allocation Pacing | 79.6% Safe Reserve Capacity |
| **Active FPS POS Outlets** | 402 / 414 Online | 12 Standby/Offline Cached | 97.1% Real-time Connectivity |
| **Autonomous AI Sentinel Models** | 4 Neural Agents Active | 1,248 Scans Monitored Daily | 0ms Pipeline Processing Lag |
| **Total System Alerts Under Review** | 447 Active Incidents | 148 Critical / High Priority | Immediate Audit Required |

---

## 3. Citizen Beneficiary Registry (Verified Records & Dossiers)

### Record: BEN-88401
- **Cardholder Name:** Aarav Sharma
- **Welfare Tier:** Priority Household (PHH)
- **State / District:** Delhi (Okhla Industrial Area)
- **Assigned Fair Price Shop:** FPS-DL-0021
- **Household Size:** 4 Family Members
- **Monthly Entitlement:** 20.0 kg (12.0 kg Rice + 8.0 kg Wheat)
- **Audit Risk Classification:** Low Risk (Clean Audit History)
- **Verification Status:** Verified (Biometric Aadhaar Match)
- **Last Distribution Date:** 2026-08-09
- **Semantic Retrieval Chunk:**
  > Beneficiary BEN-88401 (Aarav Sharma) is an active Priority Household cardholder registered at Fair Price Shop FPS-DL-0021 in Delhi. With a household size of 4 members, the authorized monthly grain entitlement is exactly 20.0 kg (12kg Rice and 8kg Wheat). The profile is in Verified status with Low Risk, and the last disbursement occurred on 2026-08-09.

---

### Record: BEN-19804
- **Cardholder Name:** Rajesh Patel
- **Welfare Tier:** Antyodaya Anna Yojana (AAY)
- **State / District:** Gwalior, Madhya Pradesh (Lashkar West)
- **Assigned Fair Price Shop:** FPS-GW-0104
- **Household Size:** 5 Family Members
- **Monthly Entitlement:** 35.0 kg (20.0 kg Rice + 15.0 kg Wheat)
- **Audit Risk Classification:** Medium Risk
- **Verification Status:** Pending (Annual Iris Re-verification required)
- **Last Distribution Date:** 2026-08-08
- **Semantic Retrieval Chunk:**
  > Beneficiary BEN-19804 (Rajesh Patel) belongs to the Antyodaya Anna Yojana (AAY) welfare category in Gwalior (FPS-GW-0104). As an AAY household of 5 members, the family receives the standard 35.0 kg monthly foodgrain allocation. Current status is Pending due to scheduled annual biometric renewal.

---

### Record: BEN-77621
- **Cardholder Name:** Sunita Devi
- **Welfare Tier:** Priority Household (PHH)
- **State / District:** East Delhi (Krishna Nagar)
- **Assigned Fair Price Shop:** BENX1
- **Household Size:** 3 Family Members
- **Monthly Entitlement:** 15.0 kg (10.0 kg Rice + 5.0 kg Wheat)
- **Audit Risk Classification:** High Risk (Under Active Investigation)
- **Verification Status:** Flagged (Off-Hours Transaction Timestamp)
- **Last Distribution Date:** 2026-08-07
- **Semantic Retrieval Chunk:**
  > Beneficiary BEN-77621 (Sunita Devi) is a PHH beneficiary entitled to 15.0 kg monthly foodgrains at center BENX1 in East Delhi. The record is flagged with High Risk because transactions were logged at 02:14 AM outside regulated operating hours, indicating potential dealer ledger falsification.

---

### Record: BEN-44912
- **Cardholder Name:** Vikram Singh
- **Welfare Tier:** Priority Household (PHH)
- **State / District:** Pune, Maharashtra (Hadapsar Logistics Zone)
- **Assigned Fair Price Shop:** FPS-PN-0045
- **Household Size:** 6 Family Members
- **Monthly Entitlement:** 30.0 kg (18.0 kg Rice + 12.0 kg Wheat)
- **Audit Risk Classification:** Low Risk
- **Verification Status:** Verified
- **Last Distribution Date:** 2026-08-09
- **Semantic Retrieval Chunk:**
  > Beneficiary BEN-44912 (Vikram Singh) represents a 6-member Priority Household in Pune (FPS-PN-0045). Entitled to 30.0 kg monthly grain quota. The record maintains a 100% verified optical biometric log.

---

### Record: BEN-65239
- **Cardholder Name:** Fatima Sheikh
- **Welfare Tier:** Antyodaya Anna Yojana (AAY)
- **State / District:** Lucknow, Uttar Pradesh (Alambagh Sector 4)
- **Assigned Fair Price Shop:** FPS-LU-0098
- **Household Size:** 4 Family Members
- **Monthly Entitlement:** 35.0 kg (25.0 kg Wheat + 10.0 kg Rice)
- **Audit Risk Classification:** Low Risk
- **Verification Status:** Verified
- **Last Distribution Date:** 2026-08-09
- **Semantic Retrieval Chunk:**
  > Beneficiary BEN-65239 (Fatima Sheikh) is an Antyodaya Anna Yojana cardholder assigned to FPS-LU-0098 in Lucknow. Entitled to 35.0 kg foodgrains monthly with zero transaction irregularities.

---

### Record: BEN-90234
- **Cardholder Name:** Manoj Kumar
- **Welfare Tier:** Antyodaya Anna Yojana (AAY)
- **State / District:** Delhi
- **Assigned Fair Price Shop:** FPS-DL-0044
- **Household Size:** 7 Family Members
- **Monthly Entitlement:** 35.0 kg (20.0 kg Rice + 15.0 kg Wheat)
- **Audit Risk Classification:** Critical Risk (Immediate Suspension)
- **Verification Status:** Flagged (Ghost Duplicate Attempt)
- **Last Distribution Date:** 2026-08-09
- **Semantic Retrieval Chunk:**
  > Beneficiary BEN-90234 (Manoj Kumar) was flagged by AI Agent 3 for a Critical fraud alert: the cardholder's credentials were presented simultaneously at terminal FPS-DL-0044 and secondary terminal FPS-DL-0012 (24 kilometers apart) within a 3-minute window, indicating automated cloned credential replay.

---

## 4. Fair Price Shop (FPS) Outlet Network Directory

| FPS Identifier | Geographical Location & District | Licensee / Authorized Dealer | Cardholders Served | Stock on Hand (kg) | POS Telemetry Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FPS-DL-0021** | Okhla Industrial Area, South Delhi | R.K. Gupta | 842 Cards | 18,200 kg | Nominal (Online 100%) |
| **FPS-GW-0104** | Lashkar West Zone, Gwalior MP | S.N. Tomar | 610 Cards | 12,400 kg | Nominal (Online 100%) |
| **BENX1** | Krishna Nagar Sector 2, East Delhi | M.K. Bansal | 1,120 Cards | 24,500 kg | **Critical Audit Active** |
| **FPS-PN-0045** | Hadapsar Logistics Complex, Pune MH | A.B. Patil | 950 Cards | 21,000 kg | Nominal (Online 100%) |
| **FPS-LU-0098** | Alambagh Sector 4, Lucknow UP | D.P. Shukla | 780 Cards | 16,800 kg | Standby (72hr Inactivity) |
| **FPS-BP-0012** | Govindpura B-Sector, Bhopal MP | V.K. Chouhan | 530 Cards | 11,500 kg | Nominal (Online 100%) |
| **FPS-AU-0077** | CIDCO Zone 3, Aurangabad MH | R.T. Jadhav | 690 Cards | 15,200 kg | Nominal (Online 100%) |

---

## 5. Strategic Commodity Buffer Stock & Silo Telemetry

| Commodity Name | Total Silo Reserve (kg) | Allocated Quota (kg) | Burn Rate (%) | Low-Stock Centers | Primary Apex Godown Origin |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Rice (Grade A Paddy)** | 42,50,000 kg | 38,00,000 kg | 89% Allocated | 12 Outlets | FCI Godown #12 (Central Reserve) |
| **Wheat (Standard Milling)** | 28,50,000 kg | 25,00,000 kg | 88% Allocated | 8 Outlets | FCI Silo North Corridor (Delhi) |
| **Sugar (Refined S-30)** | 6,20,000 kg | 5,00,000 kg | 81% Allocated | 4 Outlets | Central Buffer Complex (Bhopal) |
| **Kerosene (PDS Grade)** | 2,41,167.9 kg | 2,00,000 kg | 83% Allocated | 15 Outlets | Strategic Tank Silo #4 (Pune) |

### Inflow Consignment Challans:
- **Challan FCI-CH-3676:** +50,000 kg Rice (Grade A) transferred from FCI Godown #12 to East Delhi Buffer Silo. Authorized by Inspector P.K. Verma.
- **Challan FCI-CH-1377:** +50,000 kg Rice transferred from Central Grain Reserve into state distribution silos.
- **Challan FCI-CH-3268:** +1,00,000 kg Wheat dispatched to North Corridor Silos. Inspector: R.S. Bisht.
- **Challan FCI-CH-6819:** +50,000 kg Sugar dispatched to Bhopal Regional Silo. Inspector: K.L. Sharma.

---

## 6. AI Sentinel Anomaly Investigations & Fraud Incident Ledger

### Investigation Case #11: Off-Hours Distribution Spike at BENX1
- **Target Center:** Fair Price Shop BENX1 (East Delhi)
- **Neural Confidence Score:** 94.2%
- **Severity Classification:** Critical Priority
- **AI Model Reasoning:** Flagged due to an anomalous pattern of back-to-back distributions with timestamps occurring in less than 45 seconds across distinct cardholders, indicating possible automated script-driven manual entries.
- **Mandated Enforcement Action:** Trigger Agent 2 deterministic verify run and dispatch District Food Inspector to perform live transaction auditing.

### Investigation Case #10: Success Rate Anomaly at BENX1
- **Target Center:** Fair Price Shop BENX1 (East Delhi)
- **Neural Confidence Score:** 89.5%
- **Severity Classification:** High Priority
- **AI Model Reasoning:** Unusually high transaction success rate of 99.8% during off-hours (01:00 AM – 04:00 AM), significantly diverging from the baseline operations standard of 84.5%.
- **Mandated Enforcement Action:** Freeze terminal batch allocations and inspect physical beneficiary biometric slips.

### Investigation Case #08: Terminal Silence Timeout at FPS-LU-0098
- **Target Center:** Fair Price Shop FPS-LU-0098 (Lucknow Sector 4)
- **Neural Confidence Score:** 98.1% (Deterministic System Ping)
- **Severity Classification:** Medium Priority
- **AI Model Reasoning:** Zero transactions recorded over the last 72 hours despite physical stock consignment delivery confirmation.
- **Mandated Enforcement Action:** Dispatch field engineer to inspect ePOS cellular modem and biometric sensor calibration.

### Investigation Case #06: Low Inventory Stockout Risk at FPS-WB-0013
- **Target Center:** FPS-WB-0013 (West Bengal Distribution Outlet)
- **Neural Confidence Score:** 91.0% (Demand Forecasting Model)
- **Severity Classification:** High Priority
- **AI Model Reasoning:** Stock levels of Wheat are below 10% safety margin. Current burn rate suggests stockout will occur in approximately 1.5 days.
- **Mandated Enforcement Action:** Route emergency consignment truck with 10,000 kg Wheat from Central Buffer Silo.

---

## 7. Synthetic Grounding Q&A Index for Vector Search

**Q: What is the monthly grain allocation for an Antyodaya Anna Yojana (AAY) family?**
> **A:** Under the NFSA guidelines implemented in RationRight, an AAY beneficiary household receives a flat entitlement of 35.0 kg of subsidized foodgrains per month, typically distributed as 20.0 kg Rice and 15.0 kg Wheat, irrespective of family size.

**Q: How is the monthly ration calculated for a Priority Household (PHH) beneficiary?**
> **A:** PHH beneficiaries receive 5.0 kg of foodgrains per family member per month. For example, beneficiary Aarav Sharma (BEN-88401) with 4 family members is entitled to exactly 20.0 kg of grains (12kg Rice + 8kg Wheat) each month.

**Q: Which Fair Price Shop center has been flagged for fraudulent distribution patterns?**
> **A:** Center BENX1 in East Delhi (managed by M.K. Bansal) has been flagged for multiple critical anomalies, including back-to-back distributions in under 45 seconds and an off-hours 99.8% transaction success rate.

**Q: Who is beneficiary BEN-90234 and why is their account flagged as Critical?**
> **A:** BEN-90234 is Manoj Kumar (AAY cardholder in Delhi with 7 family members). The account is flagged as Critical because AI Agent 3 detected concurrent transaction attempts from two distinct POS terminals 24 kilometers apart within 3 minutes.

**Q: What are the current central reserve stock levels for Rice and Wheat in RationRight?**
> **A:** Central reserves currently hold 42,50,000 kg of Rice (Grade A Paddy, 89% allocated) and 28,50,000 kg of Wheat (Standard Milling, 88% allocated) across buffer godowns.

**Q: What is the total foodgrain outflow recorded across all distribution centers today?**
> **A:** Today's total system outflow is 43,450.5 kg of foodgrains, distributed across 4,520 verified citizen transactions, representing an 88.2% quota pacing against target allocations.

**Q: What action is triggered when an FPS outlet experiences terminal silence?**
> **A:** As demonstrated in Investigation Case #08 for FPS-LU-0098 in Lucknow (inactive for 72 hours), the system alerts the logistics controller and dispatches a field engineer to inspect the ePOS cellular connectivity and hardware status.
