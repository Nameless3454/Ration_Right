"""RationRight — Production-Quality Synthetic PDS Dataset Generator.

Creates a realistic, internally consistent, deterministic synthetic dataset
that behaves like a real Indian Public Distribution System (PDS) transaction dataset.

This is SYNTHTHETIC DEMO DATA only. Do NOT claim it is real government data.
Do NOT use real beneficiary identities, Aadhaar numbers, phone numbers, or other PII.

Usage:
    python3 scripts/generate_synthetic_pds.py

Output:
    data/synthetic/pds_dataset.json
"""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 42
random.seed(SEED)

# Target volumes
TARGET_TRANSACTIONS = 25000
TARGET_BENEFICIARIES = 2500
TARGET_FPS_CENTERS = 120
TARGET_DISTRICTS = 20
TARGET_STATES = 8
MONTHS_OF_HISTORY = 6

# Anomaly distribution
ANOMALY_RATE = 0.08  # 8% anomalies
RAPID_GEO_ANOMALY_RATIO = 0.5  # 50% of anomalies are rapid geographic

# Transaction date range (6 months ending today)
END_DATE = datetime(2026, 8, 20)
START_DATE = END_DATE - timedelta(days=MONTHS_OF_HISTORY * 30)

# ---------------------------------------------------------------------------
# Realistic Indian Geographic Data (Synthetic)
# ---------------------------------------------------------------------------

STATES_DISTRICTS = {
    "Delhi": {
        "districts": ["North Delhi", "South Delhi", "East Delhi", "West Delhi", "Central Delhi"],
        "center": (28.6139, 77.2090),
        "spread": 0.15,
    },
    "Uttar Pradesh": {
        "districts": ["Lucknow", "Kanpur", "Agra", "Varanasi", "Meerut", "Prayagraj"],
        "center": (26.8467, 80.9462),
        "spread": 1.5,
    },
    "Maharashtra": {
        "districts": ["Mumbai", "Pune", "Nagpur", "Nashik", "Aurangabad"],
        "center": (19.7515, 75.7139),
        "spread": 1.2,
    },
    "Rajasthan": {
        "districts": ["Jaipur", "Jodhpur", "Udaipur", "Kota", "Ajmer"],
        "center": (27.0238, 74.2179),
        "spread": 1.0,
    },
    "Karnataka": {
        "districts": ["Bengaluru", "Mysuru", "Hubli", "Mangaluru", "Belgaum"],
        "center": (15.3173, 75.7139),
        "spread": 1.0,
    },
    "Bihar": {
        "districts": ["Patna", "Gaya", "Muzaffarpur", "Bhagalpur", "Darbhanga"],
        "center": (25.6093, 85.1376),
        "spread": 1.0,
    },
    "West Bengal": {
        "districts": ["Kolkata", "Howrah", "Durgapur", "Siliguri", "Asansol"],
        "center": (22.9868, 87.8550),
        "spread": 0.8,
    },
    "Madhya Pradesh": {
        "districts": ["Bhopal", "Indore", "Jabalpur", "Gwalior", "Ujjain"],
        "center": (22.9734, 78.6569),
        "spread": 1.0,
    },
}

COMMODITIES = {
    "rice": {"min_kg": 2, "max_kg": 15, "monthly_base": 50000},
    "wheat": {"min_kg": 2, "max_kg": 10, "monthly_base": 35000},
    "sugar": {"min_kg": 0.5, "max_kg": 3, "monthly_base": 8000},
    "pulses": {"min_kg": 1, "max_kg": 5, "monthly_base": 12000},
    "millet": {"min_kg": 1, "max_kg": 5, "monthly_base": 5000},
}

RATION_CATEGORIES = ["BPL", "AAY", "PHH", "SPHH", "NPHH"]

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def random_point_in_state(state_data: dict) -> tuple[float, float]:
    """Generate a random lat/lon within a state's approximate bounds."""
    center_lat, center_lon = state_data["center"]
    spread = state_data["spread"]
    lat = center_lat + random.uniform(-spread, spread)
    lon = center_lon + random.uniform(-spread, spread)
    return round(lat, 6), round(lon, 6)


def random_timestamp(date: datetime) -> str:
    """Generate a realistic timestamp during business hours (8 AM - 6 PM)."""
    hour = random.choices(
        range(8, 18),
        weights=[3, 8, 12, 15, 14, 13, 12, 10, 8, 5],
        k=1,
    )[0]
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return f"{date.year:04d}-{date.month:02d}-{date.day:02d}T{hour:02d}:{minute:02d}:{second:02d}"


def generate_beneficiary_id(state_abbr: str, index: int) -> str:
    """Generate realistic beneficiary ID: BEN-XX-NNNNN."""
    return f"BEN-{state_abbr}-{index:05d}"


def generate_fps_id(state_abbr: str, index: int) -> str:
    """Generate realistic FPS ID: FPS-XX-NNNN."""
    return f"FPS-{state_abbr}-{index:04d}"


def generate_transaction_id(state_abbr: str, date: datetime, index: int) -> str:
    """Generate realistic transaction ID: TX-XX-YYYYMMDD-NNNNNN."""
    return f"TX-{state_abbr}-{date.year:04d}{date.month:02d}{date.day:02d}-{index:06d}"


# ---------------------------------------------------------------------------
# Generator classes
# ---------------------------------------------------------------------------

class GeographicGenerator:
    """Generates realistic Indian geographic data."""
    
    def __init__(self):
        self.states = list(STATES_DISTRICTS.keys())
        self.state_abbrs = {
            "Delhi": "DL",
            "Uttar Pradesh": "UP",
            "Maharashtra": "MH",
            "Rajasthan": "RJ",
            "Karnataka": "KA",
            "Bihar": "BR",
            "West Bengal": "WB",
            "Madhya Pradesh": "MP",
        }
    
    def get_state_abbr(self, state: str) -> str:
        return self.state_abbrs.get(state, "XX")
    
    def get_random_state(self) -> str:
        return random.choice(self.states)
    
    def get_random_district(self, state: str) -> str:
        return random.choice(STATES_DISTRICTS[state]["districts"])
    
    def get_state_center(self, state: str) -> tuple[float, float]:
        return STATES_DISTRICTS[state]["center"]


class BeneficiaryGenerator:
    """Generates realistic beneficiary data."""
    
    def __init__(self, geo: GeographicGenerator):
        self.geo = geo
        self.beneficiaries = []
        self.counter = {}
    
    def generate_beneficiaries(self) -> list[dict]:
        """Generate target number of beneficiaries across states."""
        for i in range(TARGET_BENEFICIARIES):
            state = self.geo.get_random_state()
            district = self.geo.get_random_district(state)
            state_abbr = self.geo.get_state_abbr(state)
            
            self.counter[state] = self.counter.get(state, 0) + 1
            ben_id = generate_beneficiary_id(state_abbr, self.counter[state])
            
            # Generate home coordinates near state center
            home_lat, home_lon = random_point_in_state(STATES_DISTRICTS[state])
            
            beneficiary = {
                "beneficiary_id": ben_id,
                "state": state,
                "district": district,
                "block": f"Block-{random.randint(1, 20)}",
                "ration_category": random.choice(RATION_CATEGORIES),
                "family_size": random.choices(
                    [2, 3, 4, 5, 6, 7, 8],
                    weights=[5, 15, 25, 30, 15, 7, 3],
                    k=1,
                )[0],
                "home_latitude": home_lat,
                "home_longitude": home_lon,
                "status": "ACTIVE",
            }
            self.beneficiaries.append(beneficiary)
        
        return self.beneficiaries


class FPSCenterGenerator:
    """Generates realistic Fair Price Shop centers."""
    
    def __init__(self, geo: GeographicGenerator):
        self.geo = geo
        self.centers = []
        self.counter = {}
    
    def generate_centers(self) -> list[dict]:
        """Generate target number of FPS centers."""
        for i in range(TARGET_FPS_CENTERS):
            state = self.geo.get_random_state()
            district = self.geo.get_random_district(state)
            state_abbr = self.geo.get_state_abbr(state)
            
            self.counter[state] = self.counter.get(state, 0) + 1
            fps_id = generate_fps_id(state_abbr, self.counter[state])
            
            # Generate center coordinates near district
            lat, lon = random_point_in_state(STATES_DISTRICTS[state])
            
            center = {
                "fps_id": fps_id,
                "fps_code": fps_id,
                "name": f"FPS {district} #{self.counter[state]}",
                "state": state,
                "district": district,
                "block": f"Block-{random.randint(1, 20)}",
                "latitude": lat,
                "longitude": lon,
                "capacity": random.randint(100, 500),
                "status": "ACTIVE",
                "opening_stock": random.randint(500, 5000),
                "received_stock": random.randint(1000, 10000),
                "monthly_consumption_base": random.randint(800, 5000),
            }
            self.centers.append(center)
        
        return self.centers


class TransactionGenerator:
    """Generates realistic transaction data with seeded anomalies."""
    
    def __init__(self, geo: GeographicGenerator, beneficiaries: list[dict], centers: list[dict]):
        self.geo = geo
        self.beneficiaries = beneficiaries
        self.centers = centers
        self.ben_by_state = {}
        self.center_by_state = {}
        self.transactions = []
        self.tx_counter = {}
        self.anomaly_records = []
        
        # Index beneficiaries and centers by state
        for ben in beneficiaries:
            self.ben_by_state.setdefault(ben["state"], []).append(ben)
        for center in centers:
            self.center_by_state.setdefault(center["state"], []).append(center)
    
    def generate_transactions(self) -> tuple[list[dict], list[dict]]:
        """Generate transactions with realistic patterns and seeded anomalies."""
        normal_count = int(TARGET_TRANSACTIONS * (1 - ANOMALY_RATE))
        anomaly_count = TARGET_TRANSACTIONS - normal_count
        
        print(f"Generating {normal_count} normal transactions...")
        self._generate_normal_transactions(normal_count)
        
        print(f"Generating {anomaly_count} anomalous transactions...")
        self._generate_anomaly_transactions(anomaly_count)
        
        # Shuffle to mix anomalies with normal data
        random.shuffle(self.transactions)
        
        return self.transactions, self.anomaly_records
    
    def _generate_normal_transactions(self, count: int):
        """Generate normal transactions following realistic patterns."""
        # Calculate transactions per day needed to reach target
        total_days = MONTHS_OF_HISTORY * 30
        active_days = int(total_days * 0.85)  # 85% active days
        tx_per_day = count // active_days
        
        for day_offset in range(MONTHS_OF_HISTORY * 30):
            current_date = START_DATE + timedelta(days=day_offset)
            
            # Skip some days (weekends, holidays)
            if current_date.weekday() == 6:  # Sunday
                continue
            if random.random() < 0.05:  # 5% chance of holiday
                continue
            
            # Generate transactions for this day with variation
            daily_count = int(tx_per_day * random.uniform(0.8, 1.2))
            
            for _ in range(daily_count):
                tx = self._create_normal_transaction(current_date)
                if tx:
                    self.transactions.append(tx)
    
    def _create_normal_transaction(self, date: datetime, anomaly_type: str = None) -> dict | None:
        """Create a single normal transaction."""
        state = self.geo.get_random_state()
        state_abbr = self.geo.get_state_abbr(state)
        
        # Select beneficiary and center from same state
        state_beneficiaries = self.ben_by_state.get(state, [])
        state_centers = self.center_by_state.get(state, [])
        
        if not state_beneficiaries or not state_centers:
            return None
        
        beneficiary = random.choice(state_beneficiaries)
        center = random.choice(state_centers)
        
        # Select commodity with realistic distribution
        commodity = random.choices(
            list(COMMODITIES.keys()),
            weights=[35, 25, 10, 20, 10],
            k=1,
        )[0]
        
        # Generate realistic quantity
        comm_info = COMMODITIES[commodity]
        quantity = round(random.uniform(comm_info["min_kg"], comm_info["max_kg"]), 1)
        
        # Generate transaction ID
        self.tx_counter[state] = self.tx_counter.get(state, 0) + 1
        tx_id = generate_transaction_id(state_abbr, date, self.tx_counter[state])
        
        # Transaction status (98% completed, 2% failed/pending)
        status = random.choices(
            ["COMPLETED", "FAILED", "PENDING"],
            weights=[98, 1.5, 0.5],
            k=1,
        )[0]
        
        transaction = {
            "transaction_id": tx_id,
            "beneficiary_id": beneficiary["beneficiary_id"],
            "fps_id": center["fps_id"],
            "state": state,
            "district": center["district"],
            "timestamp": random_timestamp(date),
            "commodity": commodity,
            "quantity_kg": quantity,
            "latitude": center["latitude"],
            "longitude": center["longitude"],
            "transaction_status": status,
            "ground_truth_anomaly": False,
            "ground_truth_type": None,
        }
        
        return transaction
    
    def _generate_anomaly_transactions(self, count: int):
        """Generate anomalous transactions detectable by existing agents."""
        # Generate more anomalies to ensure we hit target
        rapid_geo_count = max(int(count * RAPID_GEO_ANOMALY_RATIO), 20)
        high_freq_count = max(int(count * 0.25), 100)
        op_risk_count = count - rapid_geo_count - high_freq_count
        
        # 1. Rapid Geographic Anomalies (Agent 1 detection)
        self._generate_rapid_geo_anomalies(rapid_geo_count)
        
        # 2. High Frequency Anomalies
        self._generate_high_frequency_anomalies(high_freq_count)
        
        # 3. Operational Risk Anomalies
        self._generate_operational_risk_anomalies(op_risk_count)
    
    def _generate_rapid_geo_anomalies(self, count: int):
        """Generate rapid geographic transaction anomalies (Agent 1 detection)."""
        # Predefined anomaly scenarios with known distances/times
        anomaly_scenarios = [
            # (distance_km, time_minutes, description)
            (1148, 11, "Delhi-Mumbai rapid"),
            (347, 11, "Delhi-Agra rapid"),
            (520, 18, "Delhi-Jaipur rapid"),
            (210, 7, "Delhi-Chandigarh rapid"),
            (680, 25, "Delhi-Lucknow rapid"),
            (850, 15, "Mumbai-Pune extreme"),
            (420, 20, "Kolkata-Durgapur rapid"),
            (380, 12, "Bhopal-Indore rapid"),
            (750, 14, "Lucknow-Kanpur rapid"),
            (620, 16, "Jaipur-Jodhpur rapid"),
            (500, 19, "Bengaluru-Mysuru rapid"),
            (900, 22, "Patna-Gaya rapid"),
            (280, 9, "Mumbai-Pune rapid"),
            (450, 17, "Hyderabad-Bangalore rapid"),
            (550, 21, "Chennai-Coimbatore rapid"),
        ]
        
        pairs_generated = 0
        for scenario_idx, (target_dist, target_time, desc) in enumerate(anomaly_scenarios):
            if pairs_generated >= count // 2:
                break
            
            # Select two different states for the anomaly
            state1 = self.geo.get_random_state()
            state2 = self.geo.get_random_state()
            while state2 == state1:
                state2 = self.geo.get_random_state()
            
            state_abbr1 = self.geo.get_state_abbr(state1)
            state_abbr2 = self.geo.get_state_abbr(state2)
            
            # Select beneficiaries and centers
            ben1 = random.choice(self.ben_by_state.get(state1, []))
            ben2 = random.choice(self.ben_by_state.get(state2, []))
            center1 = random.choice(self.center_by_state.get(state1, []))
            center2 = random.choice(self.center_by_state.get(state2, []))
            
            # Ensure same beneficiary for rapid geo anomaly
            beneficiary = ben1
            
            # Create two transactions at same time, different locations
            base_date = START_DATE + timedelta(days=random.randint(30, 150))
            base_time = random_timestamp(base_date)
            
            # Transaction 1
            tx_id1 = generate_transaction_id(state_abbr1, base_date, self.tx_counter.get(state1, 0) + 1)
            self.tx_counter[state1] = self.tx_counter.get(state1, 0) + 1
            
            tx1 = {
                "transaction_id": tx_id1,
                "beneficiary_id": beneficiary["beneficiary_id"],
                "fps_id": center1["fps_id"],
                "state": state1,
                "district": center1["district"],
                "timestamp": base_time,
                "commodity": "rice",
                "quantity_kg": 5.0,
                "latitude": center1["latitude"],
                "longitude": center1["longitude"],
                "transaction_status": "COMPLETED",
                "ground_truth_anomaly": True,
                "ground_truth_type": "rapid_geographic_transaction",
            }
            
            # Transaction 2 (same beneficiary, different location, within time window)
            dt = datetime.fromisoformat(base_time)
            dt2 = dt + timedelta(minutes=target_time)
            tx_id2 = generate_transaction_id(state_abbr2, base_date, self.tx_counter.get(state2, 0) + 1)
            self.tx_counter[state2] = self.tx_counter.get(state2, 0) + 1
            
            tx2 = {
                "transaction_id": tx_id2,
                "beneficiary_id": beneficiary["beneficiary_id"],
                "fps_id": center2["fps_id"],
                "state": state2,
                "district": center2["district"],
                "timestamp": dt2.isoformat(timespec="seconds"),
                "commodity": "rice",
                "quantity_kg": 5.0,
                "latitude": center2["latitude"],
                "longitude": center2["longitude"],
                "transaction_status": "COMPLETED",
                "ground_truth_anomaly": True,
                "ground_truth_type": "rapid_geographic_transaction",
            }
            
            self.transactions.extend([tx1, tx2])
            self.anomaly_records.append({
                "anomaly_type": "rapid_geographic_transaction",
                "transaction_ids": [tx_id1, tx_id2],
                "beneficiary_id": beneficiary["beneficiary_id"],
                "description": desc,
                "target_distance_km": target_dist,
                "target_time_minutes": target_time,
            })
            pairs_generated += 1
    
    def _generate_high_frequency_anomalies(self, count: int):
        """Generate high frequency transaction anomalies."""
        # Create beneficiaries with unusually frequent transactions
        affected_beneficiaries = random.sample(
            self.beneficiaries,
            min(count // 10, len(self.beneficiaries)),
        )
        
        for beneficiary in affected_beneficiaries:
            state = beneficiary["state"]
            state_abbr = self.geo.get_state_abbr(state)
            state_centers = self.center_by_state.get(state, [])
            
            if not state_centers:
                continue
            
            # Generate 5-8 rapid transactions for this beneficiary
            base_date = START_DATE + timedelta(days=random.randint(30, 150))
            center = random.choice(state_centers)
            
            for i in range(random.randint(5, 8)):
                dt = base_date + timedelta(minutes=random.randint(1, 5))
                self.tx_counter[state] = self.tx_counter.get(state, 0) + 1
                tx_id = generate_transaction_id(state_abbr, base_date, self.tx_counter[state])
                
                tx = {
                    "transaction_id": tx_id,
                    "beneficiary_id": beneficiary["beneficiary_id"],
                    "fps_id": center["fps_id"],
                    "state": state,
                    "district": center["district"],
                    "timestamp": dt.isoformat(timespec="seconds"),
                    "commodity": "rice",
                    "quantity_kg": round(random.uniform(2, 5), 1),
                    "latitude": center["latitude"],
                    "longitude": center["longitude"],
                    "transaction_status": "COMPLETED",
                    "ground_truth_anomaly": True,
                    "ground_truth_type": "excessive_transaction_frequency",
                }
                self.transactions.append(tx)
                self.anomaly_records.append({
                    "anomaly_type": "excessive_transaction_frequency",
                    "transaction_ids": [tx_id],
                    "beneficiary_id": beneficiary["beneficiary_id"],
                    "description": f"Beneficiary {beneficiary['beneficiary_id']} made {i+1} rapid transactions",
                })
    
    def _generate_operational_risk_anomalies(self, count: int):
        """Generate operational risk anomalies (high failure rate, low stock)."""
        # Create FPS centers with high failure rates
        affected_centers = random.sample(
            self.centers,
            min(count // 20, len(self.centers)),
        )
        
        for center in affected_centers:
            state = center["state"]
            state_abbr = self.geo.get_state_abbr(state)
            
            # Generate failed transactions for this center
            base_date = START_DATE + timedelta(days=random.randint(30, 150))
            
            for i in range(random.randint(5, 15)):
                dt = base_date + timedelta(days=random.randint(0, 60))
                self.tx_counter[state] = self.tx_counter.get(state, 0) + 1
                tx_id = generate_transaction_id(state_abbr, dt, self.tx_counter[state])
                
                # Select random beneficiary from this state
                state_beneficiaries = self.ben_by_state.get(state, [])
                if not state_beneficiaries:
                    continue
                beneficiary = random.choice(state_beneficiaries)
                
                tx = {
                    "transaction_id": tx_id,
                    "beneficiary_id": beneficiary["beneficiary_id"],
                    "fps_id": center["fps_id"],
                    "state": state,
                    "district": center["district"],
                    "timestamp": random_timestamp(dt),
                    "commodity": "rice",
                    "quantity_kg": round(random.uniform(2, 5), 1),
                    "latitude": center["latitude"],
                    "longitude": center["longitude"],
                    "transaction_status": "FAILED",
                    "ground_truth_anomaly": True,
                    "ground_truth_type": "high_failure_rate",
                }
                self.transactions.append(tx)
                self.anomaly_records.append({
                    "anomaly_type": "high_failure_rate",
                    "transaction_ids": [tx_id],
                    "beneficiary_id": beneficiary["beneficiary_id"],
                    "fps_id": center["fps_id"],
                    "description": f"Failed transaction at {center['fps_id']}",
                })


class InventoryGenerator:
    """Generates realistic inventory data."""
    
    def __init__(self, centers: list[dict]):
        self.centers = centers
    
    def generate_inventory(self) -> list[dict]:
        """Generate inventory records for each FPS center and commodity."""
        inventory = []
        
        for center in self.centers:
            for commodity in COMMODITIES.keys():
                # Calculate realistic inventory levels
                base_consumption = center["monthly_consumption_base"]
                consumption_factor = {"rice": 1.0, "wheat": 0.7, "sugar": 0.15, "pulses": 0.25, "millet": 0.1}
                monthly_consumption = round(base_consumption * consumption_factor.get(commodity, 0.5), 1)
                
                # Current stock (varies by health status)
                health_roll = random.random()
                if health_roll < 0.7:  # 70% healthy
                    current_stock = round(monthly_consumption * random.uniform(1.5, 3.0), 1)
                elif health_roll < 0.9:  # 20% warning
                    current_stock = round(monthly_consumption * random.uniform(0.5, 1.5), 1)
                else:  # 10% critical
                    current_stock = round(monthly_consumption * random.uniform(0.1, 0.5), 1)
                
                reorder_threshold = round(monthly_consumption * 0.5, 1)
                
                inventory.append({
                    "fps_id": center["fps_id"],
                    "commodity": commodity,
                    "current_stock": current_stock,
                    "monthly_consumption": monthly_consumption,
                    "reorder_threshold": reorder_threshold,
                    "last_updated": (END_DATE - timedelta(days=random.randint(0, 7))).isoformat(),
                })
        
        return inventory


class DemandHistoryGenerator:
    """Generates historical demand data for forecasting."""
    
    def __init__(self, centers: list[dict]):
        self.centers = centers
    
    def generate_demand_history(self) -> list[dict]:
        """Generate 6 months of historical demand data."""
        history = []
        
        for center in self.centers:
            base_demand = center["monthly_consumption_base"]
            
            for month_offset in range(MONTHS_OF_HISTORY):
                month_date = START_DATE + timedelta(days=month_offset * 30)
                
                for commodity in COMMODITIES.keys():
                    # Calculate demand with realistic trends
                    trend_factor = random.uniform(0.95, 1.05)  # 5% variation
                    seasonal_factor = 1.0 + 0.1 * math.sin(month_offset * math.pi / 6)  # Seasonal
                    noise = random.uniform(0.9, 1.1)
                    
                    consumption_factor = {"rice": 1.0, "wheat": 0.7, "sugar": 0.15, "pulses": 0.25, "millet": 0.1}
                    demand = round(
                        base_demand * consumption_factor.get(commodity, 0.5) * trend_factor * seasonal_factor * noise,
                        1,
                    )
                    
                    history.append({
                        "fps_id": center["fps_id"],
                        "commodity": commodity,
                        "month": month_date.strftime("%Y-%m"),
                        "demand_kg": demand,
                    })
        
        return history


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_dataset() -> dict:
    """Generate the complete synthetic PDS dataset."""
    print("=" * 60)
    print("RationRight — Synthetic PDS Dataset Generator")
    print("=" * 60)
    print(f"Random seed: {SEED}")
    print(f"Target transactions: {TARGET_TRANSACTIONS}")
    print(f"Target beneficiaries: {TARGET_BENEFICIARIES}")
    print(f"Target FPS centers: {TARGET_FPS_CENTERS}")
    print()
    
    # Initialize generators
    geo = GeographicGenerator()
    
    print("Generating beneficiaries...")
    ben_gen = BeneficiaryGenerator(geo)
    beneficiaries = ben_gen.generate_beneficiaries()
    print(f"  Generated {len(beneficiaries)} beneficiaries")
    
    print("Generating FPS centers...")
    fps_gen = FPSCenterGenerator(geo)
    centers = fps_gen.generate_centers()
    print(f"  Generated {len(centers)} FPS centers")
    
    print("Generating transactions...")
    tx_gen = TransactionGenerator(geo, beneficiaries, centers)
    transactions, anomalies = tx_gen.generate_transactions()
    print(f"  Generated {len(transactions)} transactions")
    print(f"  Generated {len(anomalies)} anomaly records")
    
    print("Generating inventory...")
    inv_gen = InventoryGenerator(centers)
    inventory = inv_gen.generate_inventory()
    print(f"  Generated {len(inventory)} inventory records")
    
    print("Generating demand history...")
    demand_gen = DemandHistoryGenerator(centers)
    demand_history = demand_gen.generate_demand_history()
    print(f"  Generated {len(demand_history)} demand history records")
    
    # Compile dataset
    dataset = {
        "metadata": {
            "label": "RationRight Synthetic PDS Dataset",
            "version": "2.0",
            "description": "Production-quality synthetic PDS dataset for hackathon demo",
            "generated_at": datetime.now().isoformat(),
            "seed": SEED,
            "stats": {
                "transactions": len(transactions),
                "beneficiaries": len(beneficiaries),
                "fps_centers": len(centers),
                "districts": len(set(c["district"] for c in centers)),
                "states": len(set(c["state"] for c in centers)),
                "commodities": list(COMMODITIES.keys()),
                "anomalies": len(anomalies),
                "normal_transactions": len(transactions) - len(anomalies),
                "inventory_records": len(inventory),
                "demand_history_records": len(demand_history),
            },
        },
        "beneficiaries": beneficiaries,
        "fps_centers": centers,
        "transactions": transactions,
        "anomaly_ground_truth": anomalies,
        "inventory": inventory,
        "demand_history": demand_history,
    }
    
    return dataset


def validate_dataset(dataset: dict) -> list[str]:
    """Validate the generated dataset for consistency."""
    errors = []
    
    print("\n" + "=" * 60)
    print("Validating Dataset")
    print("=" * 60)
    
    # Check transaction count
    tx_count = len(dataset["transactions"])
    print(f"Transaction count: {tx_count}")
    if tx_count < TARGET_TRANSACTIONS * 0.9:
        errors.append(f"Transaction count {tx_count} is below target {TARGET_TRANSACTIONS}")
    
    # Check beneficiary count
    ben_count = len(dataset["beneficiaries"])
    print(f"Beneficiary count: {ben_count}")
    if ben_count < TARGET_BENEFICIARIES * 0.9:
        errors.append(f"Beneficiary count {ben_count} is below target {TARGET_BENEFICIARIES}")
    
    # Check FPS count
    fps_count = len(dataset["fps_centers"])
    print(f"FPS center count: {fps_count}")
    if fps_count < TARGET_FPS_CENTERS * 0.9:
        errors.append(f"FPS center count {fps_count} is below target {TARGET_FPS_CENTERS}")
    
    # Check referential integrity
    ben_ids = {b["beneficiary_id"] for b in dataset["beneficiaries"]}
    fps_ids = {f["fps_id"] for f in dataset["fps_centers"]}
    
    missing_ben = 0
    missing_fps = 0
    for tx in dataset["transactions"]:
        if tx["beneficiary_id"] not in ben_ids:
            missing_ben += 1
        if tx["fps_id"] not in fps_ids:
            missing_fps += 1
    
    print(f"Missing beneficiary references: {missing_ben}")
    print(f"Missing FPS references: {missing_fps}")
    
    if missing_ben > 0:
        errors.append(f"{missing_ben} transactions reference non-existent beneficiaries")
    if missing_fps > 0:
        errors.append(f"{missing_fps} transactions reference non-existent FPS centers")
    
    # Check for duplicate transaction IDs
    tx_ids = [tx["transaction_id"] for tx in dataset["transactions"]]
    unique_tx_ids = set(tx_ids)
    duplicates = len(tx_ids) - len(unique_tx_ids)
    print(f"Duplicate transaction IDs: {duplicates}")
    
    if duplicates > 0:
        errors.append(f"{duplicates} duplicate transaction IDs found")
    
    # Check anomaly distribution
    anomalies = dataset["anomaly_ground_truth"]
    print(f"Anomaly records: {len(anomalies)}")
    
    rapid_geo = sum(1 for a in anomalies if a["anomaly_type"] == "rapid_geographic_transaction")
    high_freq = sum(1 for a in anomalies if a["anomaly_type"] == "excessive_transaction_frequency")
    op_risk = sum(1 for a in anomalies if a["anomaly_type"] == "high_failure_rate")
    
    print(f"  Rapid geographic: {rapid_geo}")
    print(f"  High frequency: {high_freq}")
    print(f"  Operational risk: {op_risk}")
    
    # Check inventory consistency
    print(f"\nInventory records: {len(dataset['inventory'])}")
    
    # Check demand history
    print(f"Demand history records: {len(dataset['demand_history'])}")
    
    if errors:
        print("\n" + "=" * 60)
        print("VALIDATION FAILED")
        print("=" * 60)
        for error in errors:
            print(f"  ✗ {error}")
    else:
        print("\n" + "=" * 60)
        print("VALIDATION PASSED")
        print("=" * 60)
    
    return errors


def main():
    """Main entry point."""
    # Generate dataset
    dataset = generate_dataset()
    
    # Validate dataset
    errors = validate_dataset(dataset)
    
    if errors:
        print("\nDataset generation failed validation.")
        return 1
    
    # Save dataset
    output_path = PROJECT_ROOT / "data" / "synthetic" / "pds_dataset.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    
    print(f"\nDataset saved to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
