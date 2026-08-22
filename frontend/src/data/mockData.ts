import { Beneficiary, Inventory, Investigation, Alert, AIInsight, District } from '../types';

export const mockKpis = {
  beneficiaries: { value: 24582, change: 3.2, text: 'vs last 7 days', sub: '23,410 active' },
  distributed: { value: 43450.5, change: 9.7, text: 'vs last 7 days', sub: '4,520 records' },
  inventory: { value: 7961167.9, change: 2.1, text: 'vs last 7 days', sub: '7.9M total' },
  alerts: { value: 447, change: -12.4, text: 'vs last 7 days', sub: 'Requiring attention' },
  highRisk: { value: 148, change: -8.6, text: 'vs last 7 days', sub: 'Critical priority' },
};

export const mockInvestigations: Investigation[] = [
  {
    id: '11',
    title: 'Recommendation: Human verification',
    severity: 'High',
    status: 'Open',
    updatedAt: '9 Aug 2026',
    fps: 'BENX1',
    district: 'East Delhi',
    confidence: 94,
    reasoning: 'AI Agent 1 flagged BENX1 due to an anomalous pattern of back-to-back distributions with time-stamps occurring in less than 45 seconds across distinct cardholders, indicating possible automated manual entries.',
    recommendedAction: 'Trigger Agent 2 deterministic verify run and dispatch District Food Inspector to perform live transaction auditing.'
  },
  {
    id: '10',
    title: 'Distribution anomaly detected for BENX1',
    severity: 'High',
    status: 'Open',
    updatedAt: '9 Aug 2026',
    fps: 'BENX1',
    district: 'East Delhi',
    confidence: 89,
    reasoning: 'Unusually high transaction success rate of 99.8% during off-hours, significantly diverging from the baseline operations standard of 84.5%.',
    recommendedAction: 'Inspect offline terminal logs and cross-verify with beneficiary physical logs.'
  },
  {
    id: '9',
    title: 'No recent distribution activity at FPS02',
    severity: 'Low',
    status: 'Open',
    updatedAt: '9 Aug 2026',
    fps: 'FPS02',
    district: 'Lucknow',
    confidence: 78,
    reasoning: 'No transactions recorded over the last 72 hours, despite normal stock delivery confirmation. Potential system malfunction or dealer outage.',
    recommendedAction: 'Contact FPS operator to check terminal network status.'
  },
  {
    id: '8',
    title: 'Low inventory risk at FPS-WB-0013',
    severity: 'Medium',
    status: 'Reviewing',
    updatedAt: '8 Aug 2026',
    fps: 'FPS-WB-0013',
    district: 'Aurangabad',
    confidence: 83,
    reasoning: 'Stock levels of Wheat are below 10% safety margin. Current burn rate suggests stockout will occur in approximately 1.5 days.',
    recommendedAction: 'Initiate emergency buffer stock release from Lucknow warehouse.'
  },
  {
    id: '7',
    title: 'Demand spike detected for Rice',
    severity: 'Medium',
    status: 'Open',
    updatedAt: '8 Aug 2026',
    fps: 'FPS-DL-0045',
    district: 'Delhi',
    confidence: 81,
    reasoning: '45% increase in daily rice allocations over historical baseline, suggesting panic buying or inventory hoarding behavior.',
    recommendedAction: 'Re-verify regional quota parameters and enforce strict daily transaction limits.'
  }
];

export const mockDistricts: District[] = [
  { name: 'Lucknow', fpsCenters: 124, distributionsKg: 8420, transactions: 1245, status: 'Healthy' },
  { name: 'Delhi', fpsCenters: 98, distributionsKg: 6210, transactions: 982, status: 'Warning' },
  { name: 'Gwalior', fpsCenters: 76, distributionsKg: 4890, transactions: 731, status: 'Healthy' },
  { name: 'Aurangabad', fpsCenters: 64, distributionsKg: 3765, transactions: 612, status: 'Warning' },
  { name: 'East Delhi', fpsCenters: 52, distributionsKg: 2980, transactions: 487, status: 'Critical' }
];

export const mockAlertSummary = {
  critical: 148,
  high: 290,
  medium: 98,
  low: 47
};

export const mockAIInsights: AIInsight[] = [
  {
    id: 'INS-01',
    title: 'Distribution anomaly detected',
    fps: 'BENX1',
    district: 'East Delhi',
    severity: 'High',
    description: '3 distribution anomalies require human verification. Systematic anomalies suggest temporal collusion risks.'
  }
];

export const mockBeneficiaries: Beneficiary[] = [
  { id: 'BEN-88401', name: 'Aarav Sharma', district: 'Delhi', fps: 'FPS-DL-0021', lastDistribution: '2026-08-09', risk: 'Low', status: 'Verified', familyMembers: 4, schemeType: 'PHH' },
  { id: 'BEN-19804', name: 'Rajesh Patel', district: 'Gwalior', fps: 'FPS-GW-0104', lastDistribution: '2026-08-08', risk: 'Medium', status: 'Pending', familyMembers: 5, schemeType: 'AAY' },
  { id: 'BEN-77621', name: 'Sunita Devi', district: 'East Delhi', fps: 'BENX1', lastDistribution: '2026-08-09', risk: 'High', status: 'Flagged', familyMembers: 3, schemeType: 'PHH' },
  { id: 'BEN-34012', name: 'Amit Singh', district: 'Lucknow', fps: 'FPS-LU-0012', lastDistribution: '2026-08-07', risk: 'Low', status: 'Verified', familyMembers: 6, schemeType: 'PHH' },
  { id: 'BEN-90234', name: 'Pooja Verma', district: 'Aurangabad', fps: 'FPS-AB-0099', lastDistribution: '2026-08-05', risk: 'Critical', status: 'Flagged', familyMembers: 2, schemeType: 'AAY' }
];

export const mockInventory: Inventory[] = [
  { commodity: 'Rice', totalStockKg: 4250000, allocatedKg: 3800000, lowStockFpsCount: 12, lastStockRefill: '2026-08-01' },
  { commodity: 'Wheat', totalStockKg: 2850000, allocatedKg: 2500000, lowStockFpsCount: 8, lastStockRefill: '2026-08-03' },
  { commodity: 'Sugar', totalStockKg: 620000, allocatedKg: 500000, lowStockFpsCount: 4, lastStockRefill: '2026-07-28' },
  { commodity: 'Kerosene', totalStockKg: 241167.9, allocatedKg: 200000, lowStockFpsCount: 15, lastStockRefill: '2026-08-05' }
];

export const mockAlerts: Alert[] = [
  { id: 'ALT-104', title: 'Ghost Beneficiary Alert', severity: 'Critical', status: 'Open', createdAt: '2026-08-09 11:24', fps: 'FPS-DL-0012', district: 'Delhi', description: 'Beneficiary ID BEN-90234 flagged: multiple concurrent transaction attempts from separate terminals.' },
  { id: 'ALT-105', title: 'Suspicious Inventory Drop', severity: 'High', status: 'Acknowledged', createdAt: '2026-08-09 09:12', fps: 'BENX1', district: 'East Delhi', description: '500kg Wheat inventory drop recorded without corresponding transaction log entries.' },
  { id: 'ALT-106', title: 'Terminal Inactivity Timeout', severity: 'Low', status: 'Resolved', createdAt: '2026-08-08 17:30', fps: 'FPS-LU-0090', district: 'Lucknow', description: 'FPS terminal has failed ping checks for 6 consecutive hours.' }
];
