"""RationRight — shared suspicious-pattern configuration (MVP).

Single source of truth for the MVP anomaly pattern so that detection
(Agent 1), verification (Agent 2), and Phase 1 dataset validation all use the
same thresholds instead of duplicating values in multiple places.
"""

RAPID_GEOGRAPHIC_ANOMALY_TYPE = "rapid_geographic_transaction"
# Short-time threshold in minutes (inclusive: interval <= threshold counts).
RAPID_GEOGRAPHIC_MAX_INTERVAL_MINUTES = 60
# Large-distance threshold in km (inclusive: distance >= threshold counts).
RAPID_GEOGRAPHIC_MIN_DISTANCE_KM = 100
RAPID_GEOGRAPHIC_SEVERITY = "high"
