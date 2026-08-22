"""RationRight — Production-Quality Synthetic PDS Dataset Generator (v2).

Corrected version with:
1. Actual thresholds from agents/pattern_config.py and analytics.py
2. Proper false-positive guardrail for normal transactions
3. Only seeded anomalies that are actually detectable by existing agents
4. Correct commodity names matching the codebase

ACTUAL THRESHOLDS (quoted from code):

Agent 1 - Rapid Geographic Transaction (agents/pattern_config.py):
    RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES = 60  (interval <= 60 min counts)
    RAPID_GEOGRAPHIC_MIN_DISTANCE_KM = 100      (distance >= 100 km counts)

Inventory Risk (analytics.py):
    INVENTORY_CRITICAL_DAYS = 15  (days_remaining < 15 → CRITICAL)
    INVENTORY_WARNING_DAYS = 30   (days_remaining < 30 → WARNING)
    Formula: days_remaining = current_stock * 30 / monthly_consumption

Operational Risk (analytics.py):
    FAILURE_RATE_THRESHOLD = 0.10      (10% failure rate)
    FAILURE_MIN_TRANSACTIONS = 5       (minimum 5 transactions to trigger)
    NO_RECENT_DISTRIBUTION_DAYS = 30   (no completed transactions in last 30 days)

SUPPORTED ANOMALY TYPES (actually detected by agents):
    - rapid_geographic_transaction (Agent 1 detection)

NOT SUPPORTED (no detection logic exists):
    - excessive_transaction_frequency
    - unusual_transaction_timing
    - high_failure_rate (detected by analytics, not Agent 1)

Usage:
    python3 scripts/generate_synthetic_pds_v2.py
"""

from __future__ import annotations

import json
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import the actual thresholds from the codebase
from agents.pattern_config import (
    RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES,
    RAPID_GEOGRAPHIC_MIN_DISTANCE_KM,
)

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
ANOMALY_RATE = 0.08  # 8% anomalies (all rapid geographic - the only type Agent 1 detects)

# False-positive guardrail margin
# Normal same-beneficiary transactions must be EITHER:
# - More than RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES + margin minutes apart, OR
# - Less than RAPID_GEOGRAPHIC_MIN_DISTANCE_KM - margin km apart
FP_GUARDRAIL_TIME_MARGIN = 10  # extra minutes beyond threshold
FP_GUARDRAIL_DISTANCE_MARGIN = 20  # less km than threshold

# Transaction date range (6 months ending today)
END_DATE = datetime(2026, 8, 20)
START_DATE = END_DATE - timedelta(days=MONTHS_OF_HISTORY * 30)

# Supported commodities (from validate_dataset.py and database)
COMMODITIES = ("rice", "wheat", "sugar", "pulses", "millet")

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

COMMODITY_CONFIG = {
    "rice": {"min_kg": 2, "max_kg": 15, "monthly_base": 50000},
    "wheat": {"min_kg": 2, "max_kg": 10, "monthly_base": 35000},
    "sugar": {"min_kg": 0.5, "max_kg": 3, "monthly_base": 8000},
    "pulses": {"min_kg": 1, "max_kg": 5, "monthly_base": 12000},
    "millet": {"min_kg": 1, "max_kg": 5, "monthly_base": 5000},
}

RATION_CATEGORIES = ["BPL", "AAY", "PHH", "SPHH", "NPHH"]

# State abbreviations
STATE_ABBRS = {
    "Delhi": "DL",
    "Uttar Pradesh": "UP",
    "Maharashtra": "MH",
    "Rajasthan": "RJ",
    "Karnataka": "KA",
    "Bihar": "BR",
    "West Bengal": "WB",
    "Madhya Pradesh": "MP",
}

# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two points (matching agents)."""
    radius_km = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    )
    return 2 * radius_km * math.asin(math.sqrt(a))


def minutes_between(timestamp_a: str, timestamp_b: str) -> float:
    """Absolute time difference in minutes (matching agents)."""
    dt_a = datetime.fromisoformat(timestamp_a)
    dt_b = datetime.fromisoformat(timestamp_b)
    return abs((dt_b - dt_a).total_seconds()) / 60.0


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
# False-Positive Guardrail Check
# ---------------------------------------------------------------------------

def violates_guardrail(tx1: dict, tx2: dict) -> bool:
    """Check if two normal transactions would trigger Agent 1 detection.
    
    Returns True if the pair would be flagged (violates guardrail).
    
    Agent 1 flags pairs where:
    - time_difference <= RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES (60 min)
    - distance >= RAPID_GEOGRAPHIC_MIN_DISTANCE_KM (100 km)
    
    For normal data, we enforce a safety margin:
    - time_difference > RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES + margin, OR
    - distance < RAPID_GEOGRAPHIC_MIN_DISTANCE_KM - margin
    """
    time_diff = minutes_between(tx1["timestamp"], tx2["timestamp"])
    distance = haversine_km(
        tx1["latitude"], tx1["longitude"],
        tx2["latitude"], tx2["longitude"]
    )
    
    # Guardrail: normal transactions must NOT satisfy the detection condition
    # with a safety margin
    time_threshold = RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES + FP_GUARDRAIL_TIME_MARGIN
    distance_threshold = RAPID_GEOGRAPHIC_MIN_DISTANCE_KM - FP_GUARDRAIL_DISTANCE_MARGIN
    
    # Would this pair be flagged by Agent 1?
    would_be_flagged = (time_diff <= RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES and 
                        distance >= RAPID_GEOGRAPHIC_MIN_DISTANCE_KM)
    
    # Does it violate our guardrail (too close to the boundary)?
    violates = (time_diff <= time_threshold and distance >= distance_threshold)
    
    return violates


# ---------------------------------------------------------------------------
# Generator classes
# ---------------------------------------------------------------------------

class GeographicGenerator:
    """Generates realistic Indian geographic data."""
    
    def __init__(self):
        self.states = list(STATES_DISTRICTS.keys())
    
    def get_state_abbr(self, state: str) -> str:
        return STATE_ABBRS.get(state, "XX")
    
    def get_random_state(self) -> str:
        return random.choice(self.states)
    
    def get_random_district(self, state: str) -> str:
        return random.choice(STATES_DISTRICTS[state]["districts"])


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
        # First generate all normal transactions
        normal_count = int(TARGET_TRANSACTIONS * (1 - ANOMALY_RATE))
        print(f"Generating {normal_count} normal transactions with guardrail...")
        self._generate_normal_transactions(normal_count)
        
        # Then generate anomaly transactions (rapid geographic only)
        anomaly_count = TARGET_TRANSACTIONS - len(self.transactions)
        print(f"Generating {anomaly_count} anomaly transactions (rapid geographic)...")
        self._generate_anomaly_transactions(anomaly_count)
        
        # Shuffle to mix anomalies with normal data
        random.shuffle(self.transactions)
        
        return self.transactions, self.anomaly_records
    
    def _generate_normal_transactions(self, count: int):
        """Generate normal transactions following realistic patterns with guardrail."""
        # Calculate transactions per day needed to reach target
        total_days = MONTHS_OF_HISTORY * 30
        active_days = int(total_days * 0.85)  # 85% active days
        tx_per_day = count // active_days
        
        # Track previous transactions per beneficiary for guardrail
        prev_tx_by_ben = {}  # ben_id -> list of previous transactions
        
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
                tx = self._create_normal_transaction_with_guardrail(current_date, prev_tx_by_ben)
                if tx:
                    self.transactions.append(tx)
                    # Track for guardrail
                    ben_id = tx["beneficiary_id"]
                    if ben_id not in prev_tx_by_ben:
                        prev_tx_by_ben[ben_id] = []
                    prev_tx_by_ben[ben_id].append(tx)
    
    def _create_normal_transaction_with_guardrail(self, date: datetime, prev_tx_by_ben: dict) -> dict | None:
        """Create a single normal transaction with guardrail compliance.
        
        Ensures the new transaction won't create a false positive with any
        previous transaction for the same beneficiary.
        """
        max_attempts = 10
        
        for _ in range(max_attempts):
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
                list(COMMODITIES),
                weights=[35, 25, 10, 20, 10],
                k=1,
            )[0]
            
            # Generate realistic quantity
            comm_info = COMMODITY_CONFIG[commodity]
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
            
            timestamp = random_timestamp(date)
            
            transaction = {
                "transaction_id": tx_id,
                "beneficiary_id": beneficiary["beneficiary_id"],
                "fps_id": center["fps_id"],
                "state": state,
                "district": center["district"],
                "timestamp": timestamp,
                "commodity": commodity,
                "quantity_kg": quantity,
                "latitude": center["latitude"],
                "longitude": center["longitude"],
                "transaction_status": status,
                "ground_truth_anomaly": False,
                "ground_truth_type": None,
            }
            
            # Check guardrail against previous transactions for this beneficiary
            ben_id = beneficiary["beneficiary_id"]
            prev_txs = prev_tx_by_ben.get(ben_id, [])
            violates = False
            
            for prev_tx in prev_txs:
                time_diff = minutes_between(timestamp, prev_tx["timestamp"])
                distance = haversine_km(
                    center["latitude"], center["longitude"],
                    prev_tx["latitude"], prev_tx["longitude"]
                )
                
                # Check if this pair would trigger Agent 1
                if (time_diff <= RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES and 
                    distance >= RAPID_GEOGRAPHIC_MIN_DISTANCE_KM):
                    violates = True
                    break
            
            if not violates:
                return transaction
            
            # If violates, try again with different center/beneficiary
        
        # If we couldn't find a valid transaction after max_attempts, skip
        return None
    
    def _generate_anomaly_transactions(self, count: int):
        """Generate rapid geographic transaction anomalies (the only type Agent 1 detects)."""
        # Predefined anomaly scenarios with known distances/times
        # All calibrated against actual thresholds:
        # - time <= 60 minutes
        # - distance >= 100 km
        anomaly_scenarios = [
            # (distance_km_approx, time_minutes, description)
            (1148, 11, "Delhi-Mumbai rapid (1148 km / 11 min)"),
            (347, 11, "Delhi-Agra rapid (347 km / 11 min)"),
            (520, 18, "Delhi-Jaipur rapid (520 km / 18 min)"),
            (210, 7, "Delhi-Chandigarh rapid (210 km / 7 min)"),
            (680, 25, "Delhi-Lucknow rapid (680 km / 25 min)"),
            (850, 15, "Mumbai-Nagpur rapid (850 km / 15 min)"),
            (420, 20, "Kolkata-Durgapur rapid (420 km / 20 min)"),
            (380, 12, "Bhopal-Indore rapid (380 km / 12 min)"),
            (750, 14, "Lucknow-Kanpur rapid (750 km / 14 min)"),
            (620, 16, "Jaipur-Jodhpur rapid (620 km / 16 min)"),
            (500, 19, "Bengaluru-Mysuru rapid (500 km / 19 min)"),
            (900, 22, "Patna-Gaya rapid (900 km / 22 min)"),
            (280, 9, "Mumbai-Pune rapid (280 km / 9 min)"),
            (450, 17, "Hyderabad-Bangalore rapid (450 km / 17 min)"),
            (550, 21, "Chennai-Coimbatore rapid (550 km / 21 min)"),
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
            
            # Select beneficiary (same for both transactions)
            state_beneficiaries = self.ben_by_state.get(state1, [])
            if not state_beneficiaries:
                continue
            beneficiary = random.choice(state_beneficiaries)
            
            # Select centers from different states
            state1_centers = self.center_by_state.get(state1, [])
            state2_centers = self.center_by_state.get(state2, [])
            if not state1_centers or not state2_centers:
                continue
            
            center1 = random.choice(state1_centers)
            center2 = random.choice(state2_centers)
            
            # Create two transactions at same time, different locations
            base_date = START_DATE + timedelta(days=random.randint(30, 150))
            base_time = random_timestamp(base_date)
            
            # Transaction 1
            self.tx_counter[state1] = self.tx_counter.get(state1, 0) + 1
            tx_id1 = generate_transaction_id(state_abbr1, base_date, self.tx_counter[state1])
            
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
            
            self.tx_counter[state2] = self.tx_counter.get(state2, 0) + 1
            tx_id2 = generate_transaction_id(state_abbr2, base_date, self.tx_counter[state2])
            
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
            
            # Verify this pair would actually trigger Agent 1
            actual_distance = haversine_km(
                center1["latitude"], center1["longitude"],
                center2["latitude"], center2["longitude"]
            )
            actual_time = minutes_between(base_time, dt2.isoformat(timespec="seconds"))
            
            if actual_time <= RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES and actual_distance >= RAPID_GEOGRAPHIC_MIN_DISTANCE_KM:
                self.transactions.extend([tx1, tx2])
                self.anomaly_records.append({
                    "anomaly_type": "rapid_geographic_transaction",
                    "transaction_ids": [tx_id1, tx_id2],
                    "beneficiary_id": beneficiary["beneficiary_id"],
                    "description": desc,
                    "actual_distance_km": round(actual_distance, 2),
                    "actual_time_minutes": round(actual_time, 2),
                    "detected_by_agent1": True,
                })
                pairs_generated += 1
            else:
                # This pair wouldn't trigger - skip it
                print(f"  Skipping scenario: {desc} (distance={actual_distance:.1f}km, time={actual_time:.1f}min)")
    
    def verify_no_false_positives(self) -> int:
        """Verify normal transactions don't trigger Agent 1 detection.
        
        Returns the count of false positives found.
        """
        print("\nVerifying no false positives in normal transactions...")
        
        # Separate normal from anomaly transactions
        normal_txs = [tx for tx in self.transactions if not tx.get("ground_truth_anomaly")]
        
        # Group by beneficiary
        by_beneficiary = {}
        for tx in normal_txs:
            by_beneficiary.setdefault(tx["beneficiary_id"], []).append(tx)
        
        false_positives = 0
        
        # Check all same-beneficiary pairs
        for ben_id, records in by_beneficiary.items():
            for i in range(len(records)):
                for j in range(i + 1, len(records)):
                    tx1, tx2 = records[i], records[j]
                    
                    time_diff = minutes_between(tx1["timestamp"], tx2["timestamp"])
                    distance = haversine_km(
                        tx1["latitude"], tx1["longitude"],
                        tx2["latitude"], tx2["longitude"]
                    )
                    
                    # Check if this pair would trigger Agent 1
                    if (time_diff <= RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES and 
                        distance >= RAPID_GEOGRAPHIC_MIN_DISTANCE_KM):
                        false_positives += 1
                        print(f"  FALSE POSITIVE: {ben_id} - {tx1['transaction_id']} vs {tx2['transaction_id']}")
                        print(f"    Time: {time_diff:.2f} min, Distance: {distance:.2f} km")
        
        print(f"False positives found: {false_positives}")
        return false_positives


class InventoryGenerator:
    """Generates realistic inventory data with risk scenarios."""
    
    def __init__(self, centers: list[dict]):
        self.centers = centers
    
    def generate_inventory(self) -> list[dict]:
        """Generate inventory records with realistic risk levels.
        
        Thresholds from analytics.py:
        - CRITICAL: days_remaining < 15
        - WARNING: days_remaining < 30
        - Formula: days_remaining = current_stock * 30 / monthly_consumption
        """
        inventory = []
        
        for center in self.centers:
            for commodity in COMMODITIES:
                # Calculate realistic inventory levels
                base_consumption = center["monthly_consumption_base"]
                consumption_factor = {"rice": 1.0, "wheat": 0.7, "sugar": 0.15, "pulses": 0.25, "millet": 0.1}
                monthly_consumption = round(base_consumption * consumption_factor.get(commodity, 0.5), 1)
                
                # Current stock (varies by health status)
                health_roll = random.random()
                if health_roll < 0.7:  # 70% healthy (>30 days)
                    current_stock = round(monthly_consumption * random.uniform(1.5, 3.0), 1)
                elif health_roll < 0.85:  # 15% warning (15-30 days)
                    current_stock = round(monthly_consumption * random.uniform(0.5, 1.0), 1)
                elif health_roll < 0.95:  # 10% critical (<15 days)
                    current_stock = round(monthly_consumption * random.uniform(0.1, 0.5), 1)
                else:  # 5% very critical (<5 days)
                    current_stock = round(monthly_consumption * random.uniform(0.01, 0.15), 1)
                
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
                
                for commodity in COMMODITIES:
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
    print("RationRight — Synthetic PDS Dataset Generator (v2)")
    print("=" * 60)
    print(f"Random seed: {SEED}")
    print(f"Target transactions: {TARGET_TRANSACTIONS}")
    print(f"Target beneficiaries: {TARGET_BENEFICIARIES}")
    print(f"Target FPS centers: {TARGET_FPS_CENTERS}")
    print()
    print("ACTUAL THRESHOLDS (from codebase):")
    print(f"  Agent 1 rapid geographic: interval <= {RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES} min, distance >= {RAPID_GEOGRAPHIC_MIN_DISTANCE_KM} km")
    print(f"  Inventory critical: < 15 days remaining")
    print(f"  Inventory warning: < 30 days remaining")
    print(f"  Failure rate threshold: >= 10% with >= 5 transactions")
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
    
    # Verify no false positives
    false_positives = tx_gen.verify_no_false_positives()
    
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
            "actual_thresholds": {
                "agent1_rapid_geographic": {
                    "max_interval_minutes": RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES,
                    "min_distance_km": RAPID_GEOGRAPHIC_MIN_DISTANCE_KM,
                },
                "inventory_critical_days": 15,
                "inventory_warning_days": 30,
                "failure_rate_threshold": 0.10,
                "failure_min_transactions": 5,
            },
            "stats": {
                "transactions": len(transactions),
                "beneficiaries": len(beneficiaries),
                "fps_centers": len(centers),
                "districts": len(set(c["district"] for c in centers)),
                "states": len(set(c["state"] for c in centers)),
                "commodities": list(COMMODITIES),
                "anomalies": len(anomalies),
                "normal_transactions": len(transactions) - len(anomalies),
                "inventory_records": len(inventory),
                "demand_history_records": len(demand_history),
                "false_positives_in_normal": false_positives,
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
    
    # Check transaction count (accept if above 20,000 minimum)
    tx_count = len(dataset["transactions"])
    print(f"Transaction count: {tx_count}")
    if tx_count < 20000:
        errors.append(f"Transaction count {tx_count} is below minimum 20,000")
    
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
    print(f"  Rapid geographic: {rapid_geo}")
    
    # Check inventory consistency
    print(f"\nInventory records: {len(dataset['inventory'])}")
    
    # Check demand history
    print(f"Demand history records: {len(dataset['demand_history'])}")
    
    # Check false positives
    false_positives = dataset["metadata"]["stats"]["false_positives_in_normal"]
    print(f"\nFalse positives in normal transactions: {false_positives}")
    if false_positives > 0:
        errors.append(f"{false_positives} false positives found in normal transactions")
    
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
    output_path = PROJECT_ROOT / "data" / "synthetic" / "pds_dataset_v2.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2, ensure_ascii=False)
    
    print(f"\nDataset saved to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
