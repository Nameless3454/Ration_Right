#!/usr/bin/env python3
"""
Generate a professional, fully-structured PDF corpus for RAG (Retrieval-Augmented Generation) models.
This document contains comprehensive beneficiary registries, FPS outlet inventories,
buffer reserve telemetry, and AI fraud audit investigations from the RationRight platform.
"""

import os
import sys

class RAGPdfGenerator:
    def __init__(self, filename):
        self.filename = filename
        self.pages_data = []
        self.current_stream = []
        self.width = 595.28   # A4 width in pt
        self.height = 841.89  # A4 height in pt
        self.margin_x = 45.0
        self.margin_top = 50.0
        self.margin_bottom = 45.0
        self.y = self.height - self.margin_top
        self.page_number = 1
        
    def _escape(self, text):
        return text.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
        
    def add_rect(self, x, y, w, h, r, g, b, fill=True, stroke=False):
        mode = 'b' if (fill and stroke) else ('f' if fill else 's')
        op = f"{r:.3f} {g:.3f} {b:.3f} rg {r*0.8:.3f} {g*0.8:.3f} {b*0.8:.3f} RG {x:.2f} {y:.2f} {w:.2f} {h:.2f} re {mode}\n".encode('ascii')
        self.current_stream.append(op)
        
    def add_line(self, x1, y1, x2, y2, r=0.8, g=0.8, b=0.8, width=0.8):
        op = f"{r:.3f} {g:.3f} {b:.3f} RG {width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S\n".encode('ascii')
        self.current_stream.append(op)

    def add_text(self, text, x, y, font='F1', size=9.5, r=0.1, g=0.15, b=0.15):
        escaped = self._escape(text)
        op = f"BT /{font} {size:.2f} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y:.2f} Td ({escaped}) Tj ET\n".encode('latin-1', 'replace')
        self.current_stream.append(op)

    def draw_header_footer(self):
        # Header banner line
        self.add_line(self.margin_x, self.height - 38, self.width - self.margin_x, self.height - 38, 0.1, 0.4, 0.25, 1.2)
        self.add_text("RATIONRIGHT | NATIONAL FOOD SECURITY OPERATIONS PLATFORM", self.margin_x, self.height - 32, font='F2', size=8, r=0.08, g=0.35, b=0.22)
        self.add_text("DOCUMENT CORPUS: NFSA-BENEFICIARY-TELEMETRY-RAG-2026", self.width - self.margin_x - 240, self.height - 32, font='F1', size=7.5, r=0.45, g=0.55, b=0.5)

        # Footer
        self.add_line(self.margin_x, self.margin_bottom + 12, self.width - self.margin_x, self.margin_bottom + 12, 0.85, 0.88, 0.85, 0.8)
        self.add_text("OFFICIAL KNOWLEDGE CORPUS FOR RAG INGESTION & VECTOR RETRIEVAL", self.margin_x, self.margin_bottom, font='F1', size=7.5, r=0.5, g=0.55, b=0.52)
        self.add_text(f"Page {self.page_number}", self.width - self.margin_x - 40, self.margin_bottom, font='F2', size=8, r=0.2, g=0.25, b=0.22)

    def new_page(self):
        self.draw_header_footer()
        if self.current_stream:
            self.pages_data.append(b''.join(self.current_stream))
        self.current_stream = []
        self.page_number += 1
        self.y = self.height - self.margin_top - 15

    def check_space(self, needed):
        if self.y - needed < self.margin_bottom + 25:
            self.new_page()

    def add_section_header(self, title, subtitle=None):
        self.check_space(50)
        self.add_rect(self.margin_x, self.y - 20, self.width - (2 * self.margin_x), 24, 0.04, 0.22, 0.15, fill=True)
        self.add_text(title.upper(), self.margin_x + 10, self.y - 13, font='F2', size=11, r=1.0, g=1.0, b=1.0)
        self.y -= 30
        if subtitle:
            self.add_text(subtitle, self.margin_x + 2, self.y, font='F1', size=8.5, r=0.4, g=0.45, b=0.42)
            self.y -= 14

    def add_card(self, title, lines, alert_type="normal"):
        needed = 22 + (len(lines) * 14) + 10
        self.check_space(needed)
        
        bg_r, bg_g, bg_b = (0.96, 0.98, 0.97)
        border_r, border_g, border_b = (0.75, 0.85, 0.8)
        title_r, title_g, title_b = (0.05, 0.35, 0.22)
        
        if alert_type == "critical":
            bg_r, bg_g, bg_b = (0.99, 0.94, 0.94)
            border_r, border_g, border_b = (0.95, 0.7, 0.7)
            title_r, title_g, title_b = (0.8, 0.1, 0.1)
        elif alert_type == "highlight":
            bg_r, bg_g, bg_b = (0.93, 0.96, 1.0)
            border_r, border_g, border_b = (0.7, 0.8, 0.95)
            title_r, title_g, title_b = (0.1, 0.3, 0.7)

        w = self.width - (2 * self.margin_x)
        self.add_rect(self.margin_x, self.y - needed + 8, w, needed, bg_r, bg_g, bg_b, fill=True, stroke=True)
        
        # Title
        self.add_text(title, self.margin_x + 10, self.y - 10, font='F2', size=9.5, r=title_r, g=title_g, b=title_b)
        self.y -= 22
        
        for line in lines:
            if isinstance(line, tuple):
                label, val = line
                self.add_text(label, self.margin_x + 12, self.y, font='F2', size=8.5, r=0.2, g=0.25, b=0.22)
                self.add_text(val, self.margin_x + 160, self.y, font='F1', size=8.5, r=0.1, g=0.15, b=0.12)
            else:
                self.add_text(str(line), self.margin_x + 12, self.y, font='F1', size=8.5, r=0.2, g=0.25, b=0.22)
            self.y -= 13
        self.y -= 8

    def add_paragraph(self, text, font='F1', size=8.5, r=0.15, g=0.2, b=0.18, line_spacing=12):
        words = text.split(' ')
        max_width_chars = 95
        current_line = []
        current_len = 0
        
        for word in words:
            if current_len + len(word) + 1 > max_width_chars:
                line_str = " ".join(current_line)
                self.check_space(line_spacing + 5)
                self.add_text(line_str, self.margin_x, self.y, font=font, size=size, r=r, g=g, b=b)
                self.y -= line_spacing
                current_line = [word]
                current_len = len(word)
            else:
                current_line.append(word)
                current_len += len(word) + 1
                
        if current_line:
            line_str = " ".join(current_line)
            self.check_space(line_spacing + 5)
            self.add_text(line_str, self.margin_x, self.y, font=font, size=size, r=r, g=g, b=b)
            self.y -= line_spacing
        self.y -= 4

    def save(self):
        self.draw_header_footer()
        if self.current_stream:
            self.pages_data.append(b''.join(self.current_stream))
            
        objects = []
        objects.append(b'<< /Type /Catalog /Pages 2 0 R >>')
        kids = ' '.join(f'{3 + i*3} 0 R' for i in range(len(self.pages_data)))
        objects.append(f'<< /Type /Pages /Kids [{kids}] /Count {len(self.pages_data)} >>'.encode('ascii'))
        
        font_base = 3 + len(self.pages_data)*3
        for i, page_bytes in enumerate(self.pages_data):
            page_id = 3 + i*3
            content_id = page_id + 1
            objects.append(
                f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {self.width:.2f} {self.height:.2f}] /Contents {content_id} 0 R /Resources << /Font << /F1 {font_base} 0 R /F2 {font_base+1} 0 R /F3 {font_base+2} 0 R >> >> >>'.encode('ascii')
            )
            objects.append(f'<< /Length {len(page_bytes)} >>\nstream\n'.encode('ascii') + page_bytes + b'\nendstream')
            
        objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>')
        objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>')
        objects.append(b'<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>')
        
        out = [b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n']
        offsets = []
        for idx, obj in enumerate(objects, 1):
            offsets.append(sum(len(x) for x in out))
            out.append(f'{idx} 0 obj\n'.encode('ascii') + obj + b'\nendobj\n')
            
        startxref = sum(len(x) for x in out)
        out.append(f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode('ascii'))
        for off in offsets:
            out.append(f'{off:010d} 00000 n \n'.encode('ascii'))
            
        out.append(f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n'.encode('ascii'))
        
        with open(self.filename, 'wb') as f:
            f.write(b''.join(out))
        print(f"Generated PDF: {self.filename} ({len(self.pages_data)} pages, {os.path.getsize(self.filename)} bytes)")

def build_pdf(filepath):
    doc = RAGPdfGenerator(filepath)
    
    # -------------------------------------------------------------
    # PAGE 1: TITLE & EXECUTIVE METADATA
    # -------------------------------------------------------------
    doc.y = doc.height - doc.margin_top - 20
    doc.add_rect(doc.margin_x, doc.y - 45, doc.width - (2 * doc.margin_x), 55, 0.04, 0.22, 0.15, fill=True)
    doc.add_text("RATIONRIGHT FOOD SECURITY PLATFORM", doc.margin_x + 14, doc.y - 18, font='F2', size=14, r=1, g=1, b=1)
    doc.add_text("National Beneficiary Registry & Operational Telemetry Corpus (RAG Dataset)", doc.margin_x + 14, doc.y - 34, font='F1', size=10, r=0.8, g=0.95, b=0.88)
    doc.y -= 65

    doc.add_card("DOCUMENT METADATA FOR VECTOR EMBEDDINGS & RAG MODELS", [
        ("Corpus Identifier:", "NFSA-OPS-DATASET-2026-AUG-CORPUS"),
        ("Source Platform:", "RationRight Public Distribution System (PDS)"),
        ("Target Ingestion:", "Retrieval-Augmented Generation (RAG), Vector DBs, LLM Agents"),
        ("Legal Authority:", "National Food Security Act (NFSA), 2013, Ministry of Consumer Affairs"),
        ("Active Beneficiaries:", "24,582 Enrolled (23,410 Verified Active, 1,172 Pending/Flagged)"),
        ("Daily Outflow Tracked:", "43,450.5 kg dispatched across 4,520 verified transactions"),
        ("Strategic Reserves:", "79,61,167.9 kg foodgrains & buffer commodities across godowns"),
        ("Fair Price Shops (FPS):", "414 Active licensed distribution outlets with POS biometric terminals"),
    ], alert_type="highlight")

    doc.add_section_header("1. NFSA SCHEME DEFINITIONS & CONTEXT TAXONOMY", "Semantic background for entity resolution and question answering")
    doc.add_paragraph(
        "The National Food Security Act (NFSA) establishes targeted public distribution to guarantee subsidized foodgrains to eligible Indian citizens. Two primary welfare categories exist: (1) Antyodaya Anna Yojana (AAY): designated for the poorest socio-economic households, entitling the family to a flat allocation of 35.0 kg of subsidized foodgrains per month regardless of family size. (2) Priority Household (PHH): category entitling eligible families to 5.0 kg of foodgrains per person per month. Each distribution is strictly authenticated via biometric Aadhaar electronic Point-of-Sale (ePOS) terminals at licensed Fair Price Shops (FPS)."
    )
    doc.add_paragraph(
        "RAG Retrieval Context: When users ask about quota entitlements, verify whether the beneficiary belongs to 'AAY' (flat 35kg) or 'PHH' (5kg multiplied by total family members). Example: A PHH cardholder with 4 family members receives exactly 20.0 kg monthly."
    )

    doc.add_section_header("2. OPERATIONAL TELEMETRY & STRATEGIC KPI BENCHMARKS", "Live platform metrics recorded across districts and storage silos")
    doc.add_card("KEY METRICS SUMMARY (CURRENT FISCAL RUN)", [
        ("Total Active Beneficiaries:", "24,582 (95.2% operational coverage rate)"),
        ("Monthly Outflow Rate:", "13,03,515 kg distributed across state networks"),
        ("Silo Storage Capacity:", "1,00,00,000 kg total nominal buffer capacity"),
        ("Current Reserve Holding:", "79,61,167.9 kg (79.6% reserve safety stock level)"),
        ("Stock Burn Pacing:", "88.2% allocation pacing vs 30-day forecast burn"),
        ("Active AI Sentinel Audits:", "4 Neural models running (1,248 daily real-time scans)"),
        ("Flagged Incident Cases:", "447 system alerts (148 High/Critical priority cases)"),
    ])

    # -------------------------------------------------------------
    # PAGE 2: BENEFICIARY DIRECTORY (PART 1)
    # -------------------------------------------------------------
    doc.new_page()
    doc.add_section_header("3. CITIZEN BENEFICIARY REGISTRY - DETAILED DOSSIERS (SECTION 1)", "Verified identity records, welfare tier, assigned FPS, and quota logs")
    doc.add_paragraph(
        "This section indexes active citizen beneficiary profiles for semantic search. Each card includes the Beneficiary Identifier, cardholder name, jurisdiction, assigned Fair Price Shop, household size, welfare category, risk level, and last recorded disbursement."
    )

    beneficiaries_part1 = [
        {
            "id": "BEN-88401", "name": "Aarav Sharma", "district": "Delhi", "fps": "FPS-DL-0021",
            "family": 4, "scheme": "PHH", "entitlement": "20.0 kg (12kg Rice + 8kg Wheat)",
            "risk": "Low", "status": "Verified", "last_dist": "2026-08-09",
            "narrative": "Aarav Sharma is an active Priority Household (PHH) cardholder registered under Delhi jurisdiction at Okhla FPS-DL-0021. With 4 family members, Aarav receives 20kg monthly foodgrains. Biometrics verified with zero fraud flags."
        },
        {
            "id": "BEN-19804", "name": "Rajesh Patel", "district": "Gwalior", "fps": "FPS-GW-0104",
            "family": 5, "scheme": "AAY", "entitlement": "35.0 kg (20kg Rice + 15kg Wheat)",
            "risk": "Medium", "status": "Pending", "last_dist": "2026-08-08",
            "narrative": "Rajesh Patel is an Antyodaya Anna Yojana (AAY) beneficiary at Lashkar West FPS-GW-0104 in Gwalior. Household of 5 members receiving the standard 35kg quota. Status is Pending due to annual biometric iris renewal."
        },
        {
            "id": "BEN-77621", "name": "Sunita Devi", "district": "East Delhi", "fps": "BENX1",
            "family": 3, "scheme": "PHH", "entitlement": "15.0 kg (10kg Rice + 5kg Wheat)",
            "risk": "High", "status": "Flagged", "last_dist": "2026-08-07",
            "narrative": "Sunita Devi is registered under PHH scheme with 3 family members at East Delhi center BENX1. The account is flagged with High Risk due to off-hours distribution timestamps occurring at 02:14 AM outside regulated hours."
        },
        {
            "id": "BEN-44912", "name": "Vikram Singh", "district": "Pune", "fps": "FPS-PN-0045",
            "family": 6, "scheme": "PHH", "entitlement": "30.0 kg (18kg Rice + 12kg Wheat)",
            "risk": "Low", "status": "Verified", "last_dist": "2026-08-09",
            "narrative": "Vikram Singh is a verified PHH cardholder in Hadapsar, Pune (FPS-PN-0045). Large household of 6 entitled to 30kg grains monthly. Verified biometric log with consistent collection history."
        },
        {
            "id": "BEN-65239", "name": "Fatima Sheikh", "district": "Lucknow", "fps": "FPS-LU-0098",
            "family": 4, "scheme": "AAY", "entitlement": "35.0 kg (25kg Wheat + 10kg Rice)",
            "risk": "Low", "status": "Verified", "last_dist": "2026-08-09",
            "narrative": "Fatima Sheikh is an Antyodaya Anna Yojana cardholder registered at Lucknow Sector 4 (FPS-LU-0098). Entitled to 35kg grains. Fully verified with zero anomalies."
        }
    ]

    for b in beneficiaries_part1:
        alert_style = "critical" if b["risk"] == "High" else ("highlight" if b["risk"] == "Medium" else "normal")
        doc.add_card(f"BENEFICIARY DOSSIER: {b['id']} - {b['name']} ({b['scheme']})", [
            ("Jurisdiction / District:", f"{b['district']} | Assigned FPS: {b['fps']}"),
            ("Welfare Scheme Category:", f"{b['scheme']} (Household size: {b['family']} members)"),
            ("Monthly Entitlement:", b["entitlement"]),
            ("Audit Status & Risk Level:", f"{b['status']} | Risk: {b['risk']}"),
            ("Last Recorded Transaction:", b["last_dist"]),
            ("RAG Ingestion Context:", b["narrative"])
        ], alert_type=alert_style)

    # -------------------------------------------------------------
    # PAGE 3: BENEFICIARY DIRECTORY (PART 2)
    # -------------------------------------------------------------
    doc.new_page()
    doc.add_section_header("3. CITIZEN BENEFICIARY REGISTRY - DETAILED DOSSIERS (SECTION 2)", "Additional verified profiles across North, Central, and West zones")

    beneficiaries_part2 = [
        {
            "id": "BEN-31084", "name": "Ananya Ghosh", "district": "Bhopal", "fps": "FPS-BP-0012",
            "family": 2, "scheme": "PHH", "entitlement": "10.0 kg (6kg Rice + 4kg Wheat)",
            "risk": "Medium", "status": "Pending", "last_dist": "2026-08-06",
            "narrative": "Ananya Ghosh is a Priority Household beneficiary in Govindpura, Bhopal (FPS-BP-0012). 2 family members entitled to 10kg monthly. Status Pending pending dealer physical register reconciliation."
        },
        {
            "id": "BEN-90234", "name": "Manoj Kumar", "district": "Delhi", "fps": "FPS-DL-0044",
            "family": 7, "scheme": "AAY", "entitlement": "35.0 kg (20kg Rice + 15kg Wheat)",
            "risk": "Critical", "status": "Flagged", "last_dist": "2026-08-09",
            "narrative": "CRITICAL ANOMALY: Manoj Kumar's ration card was flagged by Neural Agent 1 for ghost duplicate transaction attempts at two different terminals (FPS-DL-0044 and FPS-DL-0012) 24 kilometers apart within 180 seconds."
        },
        {
            "id": "BEN-51209", "name": "Priya Nair", "district": "Aurangabad", "fps": "FPS-AU-0077",
            "family": 5, "scheme": "PHH", "entitlement": "25.0 kg (15kg Rice + 10kg Wheat)",
            "risk": "Low", "status": "Verified", "last_dist": "2026-08-08",
            "narrative": "Priya Nair is a verified PHH beneficiary in CIDCO Zone 3, Aurangabad (FPS-AU-0077). 5 members entitled to 25kg monthly. Full biometric compliance recorded."
        },
        {
            "id": "BEN-63012", "name": "Ramesh Yadav", "district": "Delhi", "fps": "FPS-DL-0012",
            "family": 4, "scheme": "PHH", "entitlement": "20.0 kg (12kg Rice + 8kg Wheat)",
            "risk": "Low", "status": "Verified", "last_dist": "2026-08-09",
            "narrative": "Ramesh Yadav is registered at FPS-DL-0012 in South Delhi. 4 members, receiving 20kg grain quota. Clean transaction audit trail over last 24 months."
        },
        {
            "id": "BEN-74190", "name": "Geeta Verma", "district": "Gwalior", "fps": "FPS-GW-0104",
            "family": 3, "scheme": "AAY", "entitlement": "35.0 kg (20kg Rice + 15kg Wheat)",
            "risk": "High", "status": "Flagged", "last_dist": "2026-08-07",
            "narrative": "Geeta Verma is registered under AAY in Gwalior. Flagged due to repeated transaction denials caused by fingerprint sensor degradation; inspector verification recommended."
        }
    ]

    for b in beneficiaries_part2:
        alert_style = "critical" if b["risk"] in ["Critical", "High"] else ("highlight" if b["risk"] == "Medium" else "normal")
        doc.add_card(f"BENEFICIARY DOSSIER: {b['id']} - {b['name']} ({b['scheme']})", [
            ("Jurisdiction / District:", f"{b['district']} | Assigned FPS: {b['fps']}"),
            ("Welfare Scheme Category:", f"{b['scheme']} (Household size: {b['family']} members)"),
            ("Monthly Entitlement:", b["entitlement"]),
            ("Audit Status & Risk Level:", f"{b['status']} | Risk: {b['risk']}"),
            ("Last Recorded Transaction:", b["last_dist"]),
            ("RAG Ingestion Context:", b["narrative"])
        ], alert_type=alert_style)

    # -------------------------------------------------------------
    # PAGE 4: FAIR PRICE SHOP (FPS) NETWORK & LOGISTICS
    # -------------------------------------------------------------
    doc.new_page()
    doc.add_section_header("4. FAIR PRICE SHOP (FPS) NETWORK & TERMINAL DIRECTORY", "Licensed outlets, dealer credentials, cardholder counts, and storage buffers")
    doc.add_paragraph(
        "Each Fair Price Shop (FPS) serves as the primary retail point under the Public Distribution System. The table below outlines key operational centers monitored in real-time."
    )

    fps_centers = [
        ("FPS-DL-0021", "Okhla Industrial Area, South Delhi", "R.K. Gupta", "842 Active Cards", "18,200 kg on hand", "Nominal (Online)"),
        ("FPS-GW-0104", "Lashkar West Zone, Gwalior MP", "S.N. Tomar", "610 Active Cards", "12,400 kg on hand", "Nominal (Online)"),
        ("BENX1", "Krishna Nagar Buffer, East Delhi", "M.K. Bansal", "1,120 Active Cards", "24,500 kg on hand", "CRITICAL AUDIT REQ"),
        ("FPS-PN-0045", "Hadapsar Logistics Complex, Pune MH", "A.B. Patil", "950 Active Cards", "21,000 kg on hand", "Nominal (Online)"),
        ("FPS-LU-0098", "Alambagh Sector 4, Lucknow UP", "D.P. Shukla", "780 Active Cards", "16,800 kg on hand", "Standby / Offline Ping"),
        ("FPS-BP-0012", "Govindpura B-Sector, Bhopal MP", "V.K. Chouhan", "530 Active Cards", "11,500 kg on hand", "Nominal (Online)"),
        ("FPS-AU-0077", "CIDCO Zone 3, Aurangabad MH", "R.T. Jadhav", "690 Active Cards", "15,200 kg on hand", "Nominal (Online)")
    ]

    for fps, loc, dealer, cards, stock, status in fps_centers:
        alert_style = "critical" if "CRITICAL" in status else ("highlight" if "Standby" in status else "normal")
        doc.add_card(f"OUTLET: {fps} - {loc}", [
            ("Licensee / Authorized Dealer:", dealer),
            ("Registered Cardholder Count:", cards),
            ("Current Physical Stock on Hand:", stock),
            ("Terminal Connectivity Status:", status),
            ("RAG Retrieval Summary:", f"Center {fps} is managed by dealer {dealer} in {loc}. It serves {cards} and currently holds {stock}. Telemetry status is {status}.")
        ], alert_type=alert_style)

    # -------------------------------------------------------------
    # PAGE 5: COMMODITY BUFFER INVENTORY & GODOWNS
    # -------------------------------------------------------------
    doc.new_page()
    doc.add_section_header("5. COMMODITY BUFFER INVENTORY & FCI GODOWN RESERVES", "Stock levels, allocation quotas, burn rates, and replenishment challans")
    doc.add_paragraph(
        "Central grain reserves are maintained in Food Corporation of India (FCI) buffer godowns and dispatched to state silos. The table below details stock quotas across all monitored commodities."
    )

    commodities = [
        ("Rice (Grade A Paddy)", "42,50,000 kg", "38,00,000 kg", "89% Quota Used", "12 Low Stock Centers", "FCI Godown #12 (Central Reserve)"),
        ("Wheat (Standard Milling)", "28,50,000 kg", "25,00,000 kg", "88% Quota Used", "8 Low Stock Centers", "FCI Silo North Corridor (Delhi)"),
        ("Sugar (Refined Crystalline S-30)", "6,20,000 kg", "5,00,000 kg", "81% Quota Used", "4 Low Stock Centers", "Central Buffer Complex (Bhopal)"),
        ("Kerosene (PDS Household Grade)", "2,41,167.9 kg", "2,00,000 kg", "83% Quota Used", "15 Low Stock Centers", "Strategic Tank Silo #4 (Pune)")
    ]

    for name, stock, allocated, burn, low_centers, origin in commodities:
        doc.add_card(f"COMMODITY STOCK: {name}", [
            ("Total Physical Stock Reserve:", stock),
            ("Allocated Monthly Quota:", allocated),
            ("Consumption Burn Rate:", burn),
            ("Low-Stock Outlets Flagged:", low_centers),
            ("Primary Apex Supply Origin:", origin),
            ("RAG Semantic Note:", f"{name} holds {stock} in reserve with an allocation of {allocated}. Current burn rate is {burn}. Main replenishment hub is {origin}.")
        ], alert_type="highlight")

    doc.add_section_header("INFLOW CONSIGNMENT BATCH CHALLANS (AUDIT TRAIL)", "Recent restock transfers into state silos")
    doc.add_card("VERIFIED LOGISTICS CHALLAN LEDGER", [
        ("Batch Challan FCI-CH-3676:", "+50,000 kg Rice (Grade A) to East Delhi Silo | Origin: FCI Godown #12 | Inspector: P.K. Verma"),
        ("Batch Challan FCI-CH-1377:", "+50,000 kg Rice to East Delhi Silo | Origin: FCI Godown #12 | Inspector: P.K. Verma"),
        ("Batch Challan FCI-CH-3268:", "+1,00,000 kg Wheat to North Corridor | Origin: Central Silo | Inspector: R.S. Bisht"),
        ("Batch Challan FCI-CH-6819:", "+50,000 kg Sugar to Bhopal Hub | Origin: Western Godown | Inspector: K.L. Sharma"),
    ])

    # -------------------------------------------------------------
    # PAGE 6: AI SENTINEL FRAUD AUDIT CASES & INCIDENTS
    # -------------------------------------------------------------
    doc.new_page()
    doc.add_section_header("6. AI SENTINEL ANOMALY AUDITS & FRAUD INVESTIGATIONS", "Active enforcement cases identified by multi-agent machine learning models")
    doc.add_paragraph(
        "RationRight employs 4 autonomous AI sentinel agents (Agent 1: Volumetric Regression, Agent 2: Timestamp Sentinel, Agent 3: Ghost Duplication Detective, Agent 4: Inventory Depletion Forecaster). The following cases are active under judicial/administrative audit:"
    )

    incidents = [
        ("INVESTIGATION CASE #11: Off-Hours Distribution Spike at BENX1", [
            ("Target Facility / Center:", "BENX1 (East Delhi Fair Price Shop)"),
            ("AI Confidence Score:", "94.2% Neural Confidence"),
            ("Severity Classification:", "CRITICAL (Immediate Inspection Assigned)"),
            ("Model Reasoning:", "AI Agent 1 flagged BENX1 due to an anomalous pattern of back-to-back distributions with timestamps occurring in less than 45 seconds across distinct cardholders, indicating possible automated manual entries."),
            ("Enforcement Action:", "Trigger Agent 2 deterministic verify run and dispatch District Food Inspector to perform live transaction auditing.")
        ]),
        ("INVESTIGATION CASE #10: Success Rate Anomaly at BENX1", [
            ("Target Facility / Center:", "BENX1 (East Delhi Fair Price Shop)"),
            ("AI Confidence Score:", "89.5% Neural Confidence"),
            ("Severity Classification:", "HIGH (Audit Requested)"),
            ("Model Reasoning:", "Unusually high transaction success rate of 99.8% during off-hours, significantly diverging from the baseline operations standard of 84.5%."),
            ("Enforcement Action:", "Inspect offline terminal logs and cross-verify with beneficiary physical signatures.")
        ]),
        ("INVESTIGATION CASE #08: Terminal Silence Timeout at FPS-LU-0098", [
            ("Target Facility / Center:", "FPS-LU-0098 (Lucknow Sector 4)"),
            ("AI Confidence Score:", "98.1% Deterministic Ping Alert"),
            ("Severity Classification:", "MEDIUM (Dealer Inactive)"),
            ("Model Reasoning:", "No transactions recorded over the last 72 hours, despite normal stock delivery confirmation. Potential system malfunction or dealer outage."),
            ("Enforcement Action:", "Dispatch technical support engineer to inspect ePOS cellular modem and biometric sensor.")
        ]),
        ("INVESTIGATION CASE #06: Low Inventory Stockout Risk at FPS-WB-0013", [
            ("Target Facility / Center:", "FPS-WB-0013 (West Bengal Distribution Outlet)"),
            ("AI Confidence Score:", "91.0% Forecast Confidence"),
            ("Severity Classification:", "HIGH (Stock Depletion Imminent)"),
            ("Model Reasoning:", "Stock levels of Wheat are below 10% safety margin. Current burn rate suggests stockout will occur in approximately 1.5 days."),
            ("Enforcement Action:", "Route emergency consignment truck with 10,000 kg Wheat from Central Buffer Silo.")
        ])
    ]

    for title, details in incidents:
        doc.add_card(title, details, alert_type="critical")

    # -------------------------------------------------------------
    # PAGE 7: SYNTHETIC Q&A INDEX FOR RAG GROUNDING & BENCHMARKING
    # -------------------------------------------------------------
    doc.new_page()
    doc.add_section_header("7. SYNTHETIC QUESTION & ANSWER INDEX FOR RAG GROUNDING", "High-frequency question-answer chunks for vector indexing and cosine retrieval")
    doc.add_paragraph(
        "This index contains pre-formulated question-answer pairs directly corresponding to expected user queries. RAG embedding models will index these chunks to deliver precise, fact-grounded responses."
    )

    qas = [
        ("Q: What is the monthly grain allocation for an Antyodaya Anna Yojana (AAY) family?",
         "A: Under the NFSA guidelines implemented in RationRight, an AAY beneficiary household receives a flat entitlement of 35.0 kg of subsidized foodgrains per month, typically distributed as 20 kg Rice and 15 kg Wheat, irrespective of family size."),

        ("Q: How is the monthly ration calculated for a Priority Household (PHH) beneficiary?",
         "A: PHH beneficiaries receive 5.0 kg of foodgrains per family member per month. For example, beneficiary Aarav Sharma (BEN-88401) with 4 family members is entitled to exactly 20.0 kg of grains (12kg Rice + 8kg Wheat) each month."),

        ("Q: Which Fair Price Shop center has been flagged for fraudulent distribution patterns?",
         "A: Center BENX1 in East Delhi (managed by M.K. Bansal) has been flagged for multiple critical anomalies, including back-to-back distributions in under 45 seconds and an off-hours 99.8% transaction success rate."),

        ("Q: Who is beneficiary BEN-90234 and why is their account flagged as Critical?",
         "A: BEN-90234 is Manoj Kumar (AAY cardholder in Delhi with 7 family members). The account is flagged as Critical because AI Agent 3 detected concurrent transaction attempts from two distinct POS terminals 24 kilometers apart within 3 minutes."),

        ("Q: What are the current central reserve stock levels for Rice and Wheat in RationRight?",
         "A: Central reserves currently hold 42,50,000 kg of Rice (Grade A Paddy, 89% allocated) and 28,50,000 kg of Wheat (Standard Milling, 88% allocated) across buffer godowns."),

        ("Q: What is the total foodgrain outflow recorded across all distribution centers today?",
         "A: Today's total system outflow is 43,450.5 kg of foodgrains, distributed across 4,520 verified citizen transactions, representing an 88.2% quota pacing against target allocations."),

        ("Q: What action is triggered when an FPS outlet experiences terminal silence?",
         "A: As demonstrated in Investigation Case #08 for FPS-LU-0098 in Lucknow (inactive for 72 hours), the system alerts the logistics controller and dispatches a field engineer to inspect the ePOS cellular connectivity and hardware status.")
    ]

    for q, a in qas:
        doc.add_card(q, [("Direct Grounded Answer:", a)], alert_type="highlight")

    doc.add_paragraph(
        "END OF RATIONRIGHT RAG KNOWLEDGE CORPUS | Generated for LLM Vector Retrieval & Embedding Ingestion."
    )

    doc.save()

if __name__ == '__main__':
    target = sys.argv[1] if len(sys.argv) > 1 else 'RationRight_Beneficiary_and_Distribution_Data_RAG_Corpus.pdf'
    build_pdf(target)

