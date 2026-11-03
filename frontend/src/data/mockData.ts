import { Beneficiary, Inventory, Investigation, Alert, AIInsight, District } from '../types';

export const mockKpis = {
  beneficiaries: { value: 24582, change: 3.2, text: 'vs last 7 days', sub: '20 demo records (18 verified, 2 flagged)' },
  distributed: { value: 9450.0, change: 9.7, text: 'October 2026 run', sub: '5,600 kg Rice, 3,850 kg Wheat' },
  inventory: { value: 16400.0, change: -5.4, text: 'Opening + Received', sub: '6,070 kg physical (-880 kg discrepancy)' },
  alerts: { value: 5, change: 100, text: 'Active dataset anomalies', sub: 'Shortages, duplicates, failed audits' },
  highRisk: { value: 4, change: 33.3, text: 'Critical priority', sub: 'PWD002, PWD004, BEN007, BEN019' },
};

export const mockInvestigations: Investigation[] = [
  {
    id: 'ALT-DEMO-CLAIM-02',
    title: 'Multiple Claims in Single Entitlement Period (BEN019)',
    severity: 'Critical',
    status: 'Open',
    updatedAt: '12 Oct 2026',
    fps: 'PWD005',
    district: 'Ghaziabad',
    confidence: 96,
    reasoning: 'Beneficiary BEN019 recorded two consecutive 10.0 kg Rice collection events (TXN004 & TXN005) on 2026-10-12 at Lok Kalyan FPS (PWD005) via manual override authorization.',
    recommendedAction: 'Freeze secondary manual override distributions and summon dealer DLR005 for register cross-examination.'
  },
  {
    id: 'ALT-DEMO-STOCK-03',
    title: 'Physical Stock Shortage of 280 kg Rice at PWD002',
    severity: 'Critical',
    status: 'Open',
    updatedAt: '15 Oct 2026',
    fps: 'PWD002',
    district: 'Ghaziabad',
    confidence: 94,
    reasoning: 'Jan Seva Ration Kendra (PWD002) has opening 1000kg + received 700kg - distributed 900kg = expected closing 800kg. Physical verification audited only 520kg (deficit of 280 kg / 35%).',
    recommendedAction: 'Dispatch district enforcement squad to seal terminal scales and check off-book grain diversion.'
  },
  {
    id: 'ALT-DEMO-STOCK-04',
    title: 'Physical Stock Shortage of 200 kg Rice at PWD004',
    severity: 'High',
    status: 'Open',
    updatedAt: '15 Oct 2026',
    fps: 'PWD004',
    district: 'Noida',
    confidence: 91,
    reasoning: 'Bharat Ration Point (PWD004) has expected closing stock of 500kg Rice, but physically verified stock is only 300kg (200 kg unexplained deficit).',
    recommendedAction: 'Reconcile electronic delivery notes with warehouse dispatch gate passes.'
  },
  {
    id: 'ALT-DEMO-AUDIT-05',
    title: 'Fair Price Shop PWD004 Failed Administrative Inspection',
    severity: 'Critical',
    status: 'Open',
    updatedAt: '18 Oct 2026',
    fps: 'PWD004',
    district: 'Noida',
    confidence: 98,
    reasoning: 'Bharat Ration Point (PWD004) recorded 4 late opening days, 7 manual overrides, and 6 citizen complaints during the October 2026 audit period. Official inspection status: FAILED.',
    recommendedAction: 'Issue immediate show-cause suspension notice to dealer DLR004 and divert cardholders to PWD003.'
  },
  {
    id: 'ALT-DEMO-DUP-01',
    title: 'Duplicate Household Fingerprint Detected (BEN007 & BEN014)',
    severity: 'High',
    status: 'Open',
    updatedAt: '08 Oct 2026',
    fps: 'PWD002',
    district: 'Ghaziabad',
    confidence: 89,
    reasoning: 'Beneficiary BEN007 at PWD002 (Ghaziabad) shares identical demographic and biometric fingerprint with BEN014 at PWD004 (Noida), indicating potential duplicate ration card issuance.',
    recommendedAction: 'Require physical Aadhaar biometric reverification before subsequent month distribution.'
  }
];

export const mockDistricts: District[] = [
  { name: 'Ghaziabad', fpsCenters: 3, distributionsKg: 5150, transactions: 1840, status: 'Warning' },
  { name: 'East Delhi', fpsCenters: 1, distributionsKg: 2600, transactions: 980, status: 'Healthy' },
  { name: 'Noida', fpsCenters: 1, distributionsKg: 1850, transactions: 620, status: 'Critical' }
];

export const mockAlertSummary = {
  critical: 3,
  high: 2,
  medium: 0,
  low: 0
};

export const mockAIInsights: AIInsight[] = [
  {
    id: 'INS-01',
    title: 'Physical Stock Deficit in Ghaziabad & Noida',
    fps: 'PWD002 & PWD004',
    district: 'Ghaziabad / Noida',
    severity: 'High',
    description: '880 kg net grain shortage detected between recorded ledger closing and physical weighment checks across Rice allocations.'
  },
  {
    id: 'INS-02',
    title: 'Manual Override Concentration at PWD004',
    fps: 'PWD004',
    district: 'Noida',
    severity: 'Critical',
    description: '7 manual overrides and 6 citizen complaints recorded. Terminal inspection status: FAILED.'
  }
];

export const mockBeneficiaries: Beneficiary[] = [
  { id: 'BEN001', name: 'Demo Beneficiary 01', district: 'Ghaziabad', fps: 'PWD001', lastDistribution: '2026-10-02', risk: 'Low', status: 'Verified', familyMembers: 2, schemeType: 'PHH' },
  { id: 'BEN002', name: 'Demo Beneficiary 02', district: 'Ghaziabad', fps: 'PWD001', lastDistribution: '2026-10-03', risk: 'Low', status: 'Verified', familyMembers: 3, schemeType: 'PHH' },
  { id: 'BEN003', name: 'Demo Beneficiary 03', district: 'Ghaziabad', fps: 'PWD001', lastDistribution: '2026-10-04', risk: 'Low', status: 'Verified', familyMembers: 4, schemeType: 'PHH' },
  { id: 'BEN004', name: 'Demo Beneficiary 04', district: 'Ghaziabad', fps: 'PWD001', lastDistribution: '2026-10-05', risk: 'Low', status: 'Verified', familyMembers: 5, schemeType: 'AAY' },
  { id: 'BEN005', name: 'Demo Beneficiary 05', district: 'Ghaziabad', fps: 'PWD002', lastDistribution: '2026-10-06', risk: 'Low', status: 'Verified', familyMembers: 6, schemeType: 'PHH' },
  { id: 'BEN006', name: 'Demo Beneficiary 06', district: 'Ghaziabad', fps: 'PWD002', lastDistribution: '2026-10-07', risk: 'Low', status: 'Verified', familyMembers: 2, schemeType: 'PHH' },
  { id: 'BEN007', name: 'Demo Beneficiary 07', district: 'Ghaziabad', fps: 'PWD002', lastDistribution: '2026-10-08', risk: 'High', status: 'Flagged', familyMembers: 3, schemeType: 'PHH' },
  { id: 'BEN008', name: 'Demo Beneficiary 08', district: 'Ghaziabad', fps: 'PWD002', lastDistribution: '2026-10-09', risk: 'Low', status: 'Verified', familyMembers: 4, schemeType: 'AAY' },
  { id: 'BEN009', name: 'Demo Beneficiary 09', district: 'East Delhi', fps: 'PWD003', lastDistribution: '2026-10-10', risk: 'Low', status: 'Verified', familyMembers: 5, schemeType: 'PHH' },
  { id: 'BEN010', name: 'Demo Beneficiary 10', district: 'East Delhi', fps: 'PWD003', lastDistribution: '2026-10-11', risk: 'Low', status: 'Verified', familyMembers: 6, schemeType: 'PHH' },
  { id: 'BEN011', name: 'Demo Beneficiary 11', district: 'East Delhi', fps: 'PWD003', lastDistribution: '2026-10-12', risk: 'Low', status: 'Verified', familyMembers: 2, schemeType: 'PHH' },
  { id: 'BEN012', name: 'Demo Beneficiary 12', district: 'East Delhi', fps: 'PWD003', lastDistribution: '2026-10-13', risk: 'Low', status: 'Verified', familyMembers: 3, schemeType: 'AAY' },
  { id: 'BEN013', name: 'Demo Beneficiary 13', district: 'Noida', fps: 'PWD004', lastDistribution: '2026-10-14', risk: 'Low', status: 'Verified', familyMembers: 4, schemeType: 'PHH' },
  { id: 'BEN014', name: 'Demo Beneficiary 14', district: 'Noida', fps: 'PWD004', lastDistribution: '2026-10-15', risk: 'High', status: 'Flagged', familyMembers: 5, schemeType: 'PHH' },
  { id: 'BEN015', name: 'Demo Beneficiary 15', district: 'Noida', fps: 'PWD004', lastDistribution: '2026-10-16', risk: 'Low', status: 'Verified', familyMembers: 6, schemeType: 'PHH' },
  { id: 'BEN016', name: 'Demo Beneficiary 16', district: 'Noida', fps: 'PWD004', lastDistribution: '2026-10-17', risk: 'Low', status: 'Verified', familyMembers: 2, schemeType: 'AAY' },
  { id: 'BEN017', name: 'Demo Beneficiary 17', district: 'Ghaziabad', fps: 'PWD005', lastDistribution: '2026-10-18', risk: 'Low', status: 'Verified', familyMembers: 3, schemeType: 'PHH' },
  { id: 'BEN018', name: 'Demo Beneficiary 18', district: 'Ghaziabad', fps: 'PWD005', lastDistribution: '2026-10-19', risk: 'Low', status: 'Verified', familyMembers: 4, schemeType: 'PHH' },
  { id: 'BEN019', name: 'Demo Beneficiary 19', district: 'Ghaziabad', fps: 'PWD005', lastDistribution: '2026-10-20', risk: 'Critical', status: 'Flagged', familyMembers: 5, schemeType: 'PHH' },
  { id: 'BEN020', name: 'Demo Beneficiary 20', district: 'Ghaziabad', fps: 'PWD005', lastDistribution: '2026-10-21', risk: 'Low', status: 'Verified', familyMembers: 6, schemeType: 'AAY' }
];

export const mockInventory: Inventory[] = [
  { commodity: 'Rice', totalStockKg: 2825, allocatedKg: 3200, lowStockFpsCount: 2, lastStockRefill: '2026-10-01' },
  { commodity: 'Wheat', totalStockKg: 3245, allocatedKg: 3100, lowStockFpsCount: 0, lastStockRefill: '2026-10-01' },
  { commodity: 'Sugar', totalStockKg: 1200, allocatedKg: 1000, lowStockFpsCount: 0, lastStockRefill: '2026-10-01' },
  { commodity: 'Kerosene', totalStockKg: 800, allocatedKg: 750, lowStockFpsCount: 1, lastStockRefill: '2026-10-01' }
];

export const mockAlerts: Alert[] = [
  { id: 'ALT-DEMO-DUP-01', title: 'Possible Duplicate Identity Fingerprint', severity: 'High', status: 'Open', createdAt: '2026-10-08 14:20', fps: 'PWD002', district: 'Ghaziabad', description: 'BEN007 shares identical biometric household fingerprint with BEN014 at PWD004.' },
  { id: 'ALT-DEMO-CLAIM-02', title: 'Multiple Claims in Single Entitlement Period', severity: 'Critical', status: 'Open', createdAt: '2026-10-12 16:45', fps: 'PWD005', district: 'Ghaziabad', description: 'BEN019 recorded two consecutive 10kg disbursements on 2026-10-12 via manual override.' },
  { id: 'ALT-DEMO-STOCK-03', title: 'Physical Stock Shortage (280 kg Rice)', severity: 'Critical', status: 'Open', createdAt: '2026-10-15 09:30', fps: 'PWD002', district: 'Ghaziabad', description: 'Expected closing stock: 800kg, physical stock: 520kg. Shortage: -280kg (35%).' },
  { id: 'ALT-DEMO-STOCK-04', title: 'Physical Stock Shortage (200 kg Rice)', severity: 'High', status: 'Acknowledged', createdAt: '2026-10-15 11:15', fps: 'PWD004', district: 'Noida', description: 'Expected closing stock: 500kg, physical stock: 300kg. Shortage: -200kg (40%).' },
  { id: 'ALT-DEMO-AUDIT-05', title: 'Failed Administrative Shop Inspection', severity: 'Critical', status: 'Open', createdAt: '2026-10-18 10:00', fps: 'PWD004', district: 'Noida', description: 'PWD004 logged 4 late opening days, 7 manual overrides, and 6 citizen complaints.' }
];

export interface PWDShop {
  pwd_id: string;
  shop_name: string;
  district: string;
  state: string;
  dealer_id: string;
  monthly_capacity_kg: number;
  gps_lat: number;
  gps_lon: number;
  opening_stock_kg: number;
  received_kg: number;
  distributed_kg: number;
  closing_stock_kg: number;
  physical_stock_kg: number;
  discrepancy_kg: number;
  inspection_status: string;
  late_opening_days: number;
  manual_override_count: number;
  complaints_count: number;
}

export const mockPWDShops: PWDShop[] = [
  {
    pwd_id: 'PWD001',
    shop_name: 'Shakti Fair Price Shop',
    district: 'Ghaziabad',
    state: 'Uttar Pradesh',
    dealer_id: 'DLR001',
    monthly_capacity_kg: 5000,
    gps_lat: 28.6692,
    gps_lon: 77.4538,
    opening_stock_kg: 2100,
    received_kg: 1400,
    distributed_kg: 2500,
    closing_stock_kg: 1000,
    physical_stock_kg: 975,
    discrepancy_kg: -25,
    inspection_status: 'passed',
    late_opening_days: 0,
    manual_override_count: 1,
    complaints_count: 1
  },
  {
    pwd_id: 'PWD002',
    shop_name: 'Jan Seva Ration Kendra',
    district: 'Ghaziabad',
    state: 'Uttar Pradesh',
    dealer_id: 'DLR002',
    monthly_capacity_kg: 4200,
    gps_lat: 28.655,
    gps_lon: 77.44,
    opening_stock_kg: 1800,
    received_kg: 1200,
    distributed_kg: 1550,
    closing_stock_kg: 1450,
    physical_stock_kg: 1165,
    discrepancy_kg: -285,
    inspection_status: 'pending',
    late_opening_days: 2,
    manual_override_count: 3,
    complaints_count: 4
  },
  {
    pwd_id: 'PWD003',
    shop_name: 'Asha Public Distribution Store',
    district: 'East Delhi',
    state: 'Delhi',
    dealer_id: 'DLR003',
    monthly_capacity_kg: 6000,
    gps_lat: 28.625,
    gps_lon: 77.305,
    opening_stock_kg: 2600,
    received_kg: 1700,
    distributed_kg: 2600,
    closing_stock_kg: 1700,
    physical_stock_kg: 1695,
    discrepancy_kg: -5,
    inspection_status: 'passed',
    late_opening_days: 0,
    manual_override_count: 0,
    complaints_count: 0
  },
  {
    pwd_id: 'PWD004',
    shop_name: 'Bharat Ration Point',
    district: 'Noida',
    state: 'Uttar Pradesh',
    dealer_id: 'DLR004',
    monthly_capacity_kg: 4500,
    gps_lat: 28.581,
    gps_lon: 77.326,
    opening_stock_kg: 1700,
    received_kg: 1100,
    distributed_kg: 1850,
    closing_stock_kg: 950,
    physical_stock_kg: 748,
    discrepancy_kg: -202,
    inspection_status: 'failed',
    late_opening_days: 4,
    manual_override_count: 7,
    complaints_count: 6
  },
  {
    pwd_id: 'PWD005',
    shop_name: 'Lok Kalyan FPS',
    district: 'Ghaziabad',
    state: 'Uttar Pradesh',
    dealer_id: 'DLR005',
    monthly_capacity_kg: 3800,
    gps_lat: 28.682,
    gps_lon: 77.415,
    opening_stock_kg: 1600,
    received_kg: 900,
    distributed_kg: 1150,
    closing_stock_kg: 1350,
    physical_stock_kg: 1335,
    discrepancy_kg: -15,
    inspection_status: 'pending',
    late_opening_days: 1,
    manual_override_count: 5,
    complaints_count: 3
  }
];
