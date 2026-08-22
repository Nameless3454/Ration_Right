export interface Beneficiary {
  id: string;
  name: string;
  district: string;
  fps: string;
  lastDistribution: string;
  risk: 'Low' | 'Medium' | 'High' | 'Critical';
  status: 'Verified' | 'Unverified' | 'Pending' | 'Flagged';
  familyMembers: number;
  schemeType: string;
}

export interface FPSCenter {
  id: string;
  name: string;
  district: string;
  operatorName: string;
  activeBeneficiaries: number;
  status: 'Active' | 'Suspended' | 'Under Review';
}

export interface Distribution {
  id: string;
  fpsId: string;
  district: string;
  commodity: 'Rice' | 'Wheat' | 'Sugar' | 'Kerosene';
  quantityKg: number;
  transactionsCount: number;
  timestamp: string;
}

export interface Inventory {
  commodity: 'Rice' | 'Wheat' | 'Sugar' | 'Kerosene';
  totalStockKg: number;
  allocatedKg: number;
  lowStockFpsCount: number;
  lastStockRefill: string;
}

export interface Investigation {
  id: string;
  title: string;
  severity: 'Low' | 'Medium' | 'High' | 'Critical';
  status: 'Open' | 'Reviewing' | 'Resolved';
  updatedAt: string;
  fps: string;
  district: string;
  confidence: number;
  reasoning: string;
  recommendedAction: string;
}

export interface Alert {
  id: string;
  title: string;
  severity: 'Low' | 'Medium' | 'High' | 'Critical';
  status: 'Open' | 'Acknowledged' | 'Resolved';
  createdAt: string;
  fps: string;
  district: string;
  description: string;
}

export interface AIInsight {
  id: string;
  title: string;
  fps: string;
  district: string;
  severity: 'Low' | 'Medium' | 'High' | 'Critical';
  description: string;
}

export interface District {
  name: string;
  fpsCenters: number;
  distributionsKg: number;
  transactions: number;
  status: 'Healthy' | 'Warning' | 'Critical';
}
