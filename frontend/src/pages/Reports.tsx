import React, { useState, useMemo } from 'react';
import { createPortal } from 'react-dom';
import { 
  FileText, 
  Download, 
  Search, 
  CheckCircle2, 
  ShieldCheck, 
  PlusCircle, 
  Printer, 
  X, 
  Eye, 
  Clock, 
  Sparkles, 
  Database, 
  FileDown,
  ChevronDown
} from 'lucide-react';

interface ReportItem {
  id: string;
  title: string;
  category: 'Statutory' | 'Logistics' | 'AI Audits' | 'Beneficiary';
  format: 'PDF' | 'CSV' | 'XLSX';
  size: string;
  generatedDate: string;
  description: string;
  recordCount: string;
  status: 'Certified' | 'Draft' | 'Archived';
  lines: string[];
}

export const Reports: React.FC = () => {
  const [selectedCategory, setSelectedCategory] = useState<string>('All');
  const [searchQuery, setSearchQuery] = useState('');
  const [previewReport, setPreviewReport] = useState<ReportItem | null>(null);
  const [isGeneratorOpen, setIsGeneratorOpen] = useState(false);
  const [toastMessage, setToastMessage] = useState<string | null>(null);

  // Custom Generator Form State
  const [generatorForm, setGeneratorForm] = useState({
    title: 'Custom Regional Welfare Audit',
    category: 'Statutory',
    district: 'All Districts',
    format: 'PDF' as 'PDF' | 'CSV',
    timeframe: 'August 2026'
  });

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  const reportsList: ReportItem[] = useMemo(() => [
    {
      id: 'REP-2026-08A',
      title: 'Monthly NFSA Statutory Compliance & Allocation Dossier',
      category: 'Statutory',
      format: 'PDF',
      size: '3.4 MB',
      generatedDate: '22 Aug 2026',
      description: 'Comprehensive state-wide grain distribution ledger, cardholder quota fills, and Fair Price Shop allocations.',
      recordCount: '24,582 Beneficiaries',
      status: 'Certified',
      lines: [
        'Total Registered Beneficiaries: 24,582 (Active: 23,410 cardholders)',
        'Total Grain Allocation Dispatched: 43,450.5 kg across 5 state districts',
        'Rice (Grade A Paddy): 23,800 kg delivered | Wheat: 14,200 kg delivered',
        'Sugar & Subsidized Fuel Quota Fill Rate: 94.8% baseline standard',
        'NFSA Statutory Section 12 Compliance: 100% verified without divergence',
        'Verification Authority: Food Security Command Center (RationRight)'
      ]
    },
    {
      id: 'REP-2026-08B',
      title: 'District Grain Discrepancy & Theft Risk Index',
      category: 'AI Audits',
      format: 'PDF',
      size: '2.8 MB',
      generatedDate: '20 Aug 2026',
      description: 'Granular assessment of temporal anomalies, offline POS overrides, and suspicious stock shrinkage by district.',
      recordCount: '52 Hotspot Centers',
      status: 'Certified',
      lines: [
        'High-Risk Hotspot Centers Identified: 148 flagged FPS terminals',
        'East Delhi (BENX1): Critical temporal divergence - 14 rapid back-to-back entries',
        'Lucknow FPS02: Inactivity anomaly flagged - 72 hours zero transaction rate',
        'Aurangabad FPS-AB-0099: Wheat inventory variance of 510kg without card logs',
        'Composite Regional Discrepancy Index: 1.82% (Threshold safety margin: <2.5%)',
        'Prescribed Audit Protocol: Deploy State Food Inspector to East Delhi'
      ]
    },
    {
      id: 'REP-2026-08C',
      title: 'Central FCI Godown Inflow & Buffer Reserve Audit',
      category: 'Logistics',
      format: 'XLSX',
      size: '1.9 MB',
      generatedDate: '18 Aug 2026',
      description: 'Reconciliation of FCI Godown #12 consignment shipments, silo capacity reserves, and burn-rate projections.',
      recordCount: '79.6 Lakh kg Managed',
      status: 'Certified',
      lines: [
        'Central FCI Reserve Total Stock: 79,61,167.9 kg foodgrains in state silos',
        'Allocated Distribution Quota: 70,00,000 kg committed to Fair Price network',
        'Available Emergency Safety Buffer: 9,61,167.9 kg (Runway: 58.4 days)',
        'Latest Inflow Consignment: FCI-CH-3676 (+50,000 kg Grade A Rice)',
        'Low Stock Shortage Centers: 39 centers currently under 15% safety threshold'
      ]
    },
    {
      id: 'REP-2026-08D',
      title: 'Biometric Optical Scanner & OTP Bypass Audit Trail',
      category: 'AI Audits',
      format: 'PDF',
      size: '4.1 MB',
      generatedDate: '15 Aug 2026',
      description: 'Audit of authentication methods, fingerprint match rates, and manual OTP override authorizations across terminals.',
      recordCount: '18,420 POS Scans',
      status: 'Certified',
      lines: [
        'Biometric Authentication Success Rate: 92.4% on primary optical scanner',
        'Manual OTP Override Requests: 1,420 transactions (7.6% frequency)',
        'Iris Recognition Fallback: 840 transactions in rural Lucknow sectors',
        'Zero-Touch Verification Precision: 98.4% model accuracy rating',
        'Ghost Beneficiary Anomaly Flags: 12 invalid Aadhaar links suspended'
      ]
    },
    {
      id: 'REP-2026-08E',
      title: 'Antyodaya Anna Yojana (AAY) Priority Welfare Registry',
      category: 'Beneficiary',
      format: 'CSV',
      size: '2.2 MB',
      generatedDate: '12 Aug 2026',
      description: 'Direct entitlement tracking for vulnerable and below-poverty-line families across urban and rural zones.',
      recordCount: '4,890 AAY Families',
      status: 'Certified',
      lines: [
        'Total AAY Registered Households: 4,890 priority families',
        'Subsidized Ration Distribution: 35 kg grain per family per month standard',
        'Grain Delivery Completion Rate: 99.1% across verified households',
        'Doorstep Logistics Dispatch: 184 elderly beneficiary kits delivered'
      ]
    },
    {
      id: 'REP-2026-08F',
      title: 'State Fair Price Shop Terminal Health & Network Telemetry',
      category: 'Logistics',
      format: 'PDF',
      size: '1.5 MB',
      generatedDate: '10 Aug 2026',
      description: 'Hardware calibration records, electronic weighing scale certs, and live network latency logs for 414 FPS.',
      recordCount: '414 Center Terminals',
      status: 'Certified',
      lines: [
        'Active Operational FPS Terminals: 402 / 414 (97.1% network connectivity)',
        'Offline Terminal Stores: 12 centers running on encrypted store-and-forward',
        'Electronic Weigh Scale ISO-9001 Calibration Check: 98.2% compliance',
        'Scheduled Maintenance Window: Lucknow & Gwalior sector check on Aug 28'
      ]
    }
  ], []);

  const downloadMockPdf = (filename: string, title: string, reportLines: string[]) => {
    const textStream = [
      'BT',
      '/F1 16 Tf',
      '50 750 Td',
      `(${title}) Tj`,
      '/F1 10 Tf',
      '0 -40 Td',
      ...reportLines.map(line => `(${line}) Tj\n0 -20 Td`),
      'ET'
    ].join('\n');

    const pdfContent = `%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length ${textStream.length} >>
stream
${textStream}
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f
trailer
<< /Size 6 /Root 1 0 R >>
startxref
150
%%EOF`;

    const blob = new Blob([pdfContent], { type: 'application/pdf' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
    showToast(`Downloaded "${filename}" successfully.`);
  };

  const handleDownload = (report: ReportItem) => {
    const safeFilename = `${report.title.toLowerCase().replace(/[^a-z0-9]/g, '_')}.${report.format.toLowerCase()}`;
    if (report.format === 'CSV') {
      const csvText = report.lines.join('\n');
      const blob = new Blob([csvText], { type: 'text/csv' });
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = safeFilename;
      link.click();
      URL.revokeObjectURL(url);
      showToast(`Exported "${safeFilename}" as CSV.`);
    } else {
      downloadMockPdf(safeFilename, report.title, report.lines);
    }
  };

  const handleCompileCustomDossier = (e: React.FormEvent) => {
    e.preventDefault();
    setIsGeneratorOpen(false);
    showToast(`Custom Dossier "${generatorForm.title}" compiled & downloaded.`);
    downloadMockPdf(
      `${generatorForm.title.toLowerCase().replace(/[^a-z0-9]/g, '_')}.pdf`,
      `RationRight - ${generatorForm.title}`,
      [
        `Target District Scope: ${generatorForm.district}`,
        `Classification Category: ${generatorForm.category}`,
        `Reporting Timeframe: ${generatorForm.timeframe}`,
        `Verified Records: 24,582 Beneficiaries | 414 FPS Centers`,
        'Cryptographic NFSA Audit Seal: Verified Authentic'
      ]
    );
  };

  const filteredReports = reportsList.filter(rep => {
    const matchesCategory = selectedCategory === 'All' || rep.category === selectedCategory;
    const matchesSearch = 
      rep.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rep.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rep.recordCount.toLowerCase().includes(searchQuery.toLowerCase()) ||
      rep.id.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesCategory && matchesSearch;
  });

  return (
    <div className="space-y-6 pb-12">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed bottom-6 right-6 z-[120] flex items-center gap-3 bg-[#0a3d2e] text-white px-5 py-3.5 rounded-2xl shadow-2xl border border-[#7fd8aa]/40 animate-in fade-in slide-in-from-bottom-5">
          <CheckCircle2 size={18} className="text-[#7fd8aa]" />
          <span className="text-xs md:text-sm font-semibold">{toastMessage}</span>
          <button onClick={() => setToastMessage(null)} className="ml-2 text-white/60 hover:text-white cursor-pointer">
            <X size={14} />
          </button>
        </div>
      )}

      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2.5">
            <h1 className="text-2xl md:text-3xl font-extrabold text-[#10261c] tracking-tight font-display">
              Official Reports & Compliance Dispatches
            </h1>
            <span className="px-2.5 py-0.5 rounded-full text-[11px] font-bold tracking-wide uppercase bg-[#2fa56f]/15 text-[#0d6840] border border-[#2fa56f]/30 flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#2fa56f] animate-pulse"></span>
              NFSA Certified
            </span>
          </div>
          <p className="text-xs md:text-sm text-[#5d7468] mt-1 font-medium">
            Generate cryptographic audit dossiers, regional grain reconciliations, and statutory NFSA compliance reports.
          </p>
        </div>

        {/* Action Header Buttons */}
        <div className="flex items-center gap-2.5 self-start sm:self-center">
          <button
            type="button"
            onClick={() => {
              downloadMockPdf('all_dossiers_bundle.pdf', 'RationRight - Master Compliance Dossier', reportsList.flatMap(r => r.lines.slice(0, 2)));
            }}
            className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full border border-slate-200/80 bg-white/80 hover:bg-white text-xs md:text-sm font-bold text-[#10261c] shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
          >
            <FileDown size={15} className="text-[#5d7468]" />
            <span>Batch Export All</span>
          </button>

          <button
            type="button"
            onClick={() => setIsGeneratorOpen(true)}
            className="inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-full font-bold text-xs md:text-sm shadow-md transition-all duration-300 hover:scale-[1.02] active:scale-[0.98] cursor-pointer !text-white text-white shrink-0"
            style={{
              background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
              color: '#ffffff',
              boxShadow: '0 8px 20px -4px rgba(20, 101, 74, 0.4)'
            }}
          >
            <PlusCircle size={16} className="text-white" strokeWidth={2.4} />
            <span className="font-bold text-white">Generate Custom Dossier</span>
          </button>
        </div>
      </div>

      {/* 4 Luxury Glass KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Card 1: Available Reports */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Statutory Dossiers</span>
            <div className="w-8 h-8 rounded-full bg-[#14654a]/12 flex items-center justify-center text-[#14654a]">
              <FileText size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              {reportsList.length} Files
            </span>
            <span className="text-[11px] font-bold text-[#0d6840]">
              PDF • CSV • XLSX
            </span>
          </div>
        </div>

        {/* Card 2: Audited Inflow */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Audited Grain Vol.</span>
            <div className="w-8 h-8 rounded-full bg-cyan-500/15 flex items-center justify-center text-cyan-700">
              <Database size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              79.6L kg
            </span>
            <span className="text-[11px] font-bold text-cyan-700">
              100% Reconciled
            </span>
          </div>
        </div>

        {/* Card 3: Audit Compliance Score */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">CAG Audit Index</span>
            <div className="w-8 h-8 rounded-full bg-emerald-500/15 flex items-center justify-center text-[#14654a]">
              <ShieldCheck size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#14654a] font-display">
              99.2%
            </span>
            <span className="text-[11px] font-bold text-[#14654a] bg-emerald-100/70 px-2 py-0.5 rounded-full">
              Exceeds Standard
            </span>
          </div>
        </div>

        {/* Card 4: Last Batch Sync */}
        <div className="bg-white/85 backdrop-blur-xl border border-white/90 rounded-[24px] p-5 shadow-sm hover:shadow-md hover:-translate-y-1 transition-all duration-300 flex flex-col justify-between min-h-[120px]">
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-bold text-[#7a8b84] uppercase tracking-wider">Official Ledger Sync</span>
            <div className="w-8 h-8 rounded-full bg-amber-500/15 flex items-center justify-center text-amber-700">
              <Clock size={18} />
            </div>
          </div>
          <div className="mt-2 flex items-baseline justify-between">
            <span className="text-2xl md:text-3xl font-extrabold text-[#10261c] font-display">
              Today 14:30
            </span>
            <span className="text-[11px] font-bold text-amber-700">
              Daily Auto-Batch
            </span>
          </div>
        </div>
      </div>

      {/* Directory Filter & Search Toolbar */}
      <div className="bg-white/90 backdrop-blur-xl border border-white/90 rounded-[28px] p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-3.5">
          {/* Category Filter Tabs */}
          <div className="flex items-center gap-1.5 overflow-x-auto pb-1 md:pb-0">
            {['All', 'Statutory', 'Logistics', 'AI Audits', 'Beneficiary'].map(cat => (
              <button
                key={cat}
                type="button"
                onClick={() => setSelectedCategory(cat)}
                className={`px-4 py-2 rounded-full text-xs font-bold transition-all cursor-pointer whitespace-nowrap ${
                  selectedCategory === cat
                    ? 'bg-[#14654a] text-white shadow-xs'
                    : 'bg-slate-100 hover:bg-slate-200 text-slate-600'
                }`}
              >
                {cat === 'All' ? `All Reports (${reportsList.length})` : cat}
              </button>
            ))}
          </div>

          {/* Search Box */}
          <div className="relative min-w-[260px]">
            <Search size={14} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Search dossiers, month, ID..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-3.5 py-2 rounded-full border border-slate-200/90 bg-slate-50/80 hover:bg-white focus:bg-white text-xs text-[#10261c] placeholder-slate-400 focus:outline-none focus:border-[#14654a] transition-all font-medium"
            />
            {searchQuery && (
              <button 
                onClick={() => setSearchQuery('')}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 cursor-pointer"
              >
                <X size={12} />
              </button>
            )}
          </div>
        </div>

        {/* Reports Cards Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 pt-2">
          {filteredReports.map((report) => (
            <div 
              key={report.id}
              className="bg-white border border-slate-100 hover:border-emerald-300/80 rounded-[24px] p-5 shadow-xs hover:shadow-md transition-all duration-200 flex flex-col justify-between space-y-4 group"
            >
              <div className="space-y-3">
                {/* Card Top Pill Row */}
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-extrabold text-[11px] text-[#14654a] bg-[#14654a]/8 px-2.5 py-0.5 rounded-lg border border-[#14654a]/20">
                      {report.id}
                    </span>
                    <span className="text-[10.5px] font-bold text-slate-600 bg-slate-100 px-2.5 py-0.5 rounded-full">
                      {report.category}
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-extrabold tracking-wider uppercase text-emerald-800 bg-emerald-100/80 px-2 py-0.5 rounded-full flex items-center gap-1">
                      <ShieldCheck size={11} className="text-emerald-700" />
                      {report.status}
                    </span>
                    <span className="text-xs font-mono font-bold text-slate-400">
                      {report.format} • {report.size}
                    </span>
                  </div>
                </div>

                {/* Title & Description */}
                <div>
                  <h3 className="font-extrabold text-[#10261c] text-sm md:text-base font-display group-hover:text-[#14654a] transition-colors leading-snug">
                    {report.title}
                  </h3>
                  <p className="text-xs text-[#5d7468] mt-1 line-clamp-2 font-medium leading-relaxed">
                    {report.description}
                  </p>
                </div>
              </div>

              {/* Card Meta & Bottom Buttons */}
              <div className="pt-3 border-t border-slate-100/90 flex items-center justify-between flex-wrap gap-2">
                <div className="text-[11px] text-slate-500 font-medium">
                  <span className="font-bold text-[#10261c]">{report.recordCount}</span> • Compiled {report.generatedDate}
                </div>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setPreviewReport(report)}
                    className="inline-flex items-center gap-1 px-3 py-1.5 rounded-full text-xs font-bold text-[#14654a] bg-[#14654a]/10 hover:bg-[#14654a]/20 transition-colors cursor-pointer"
                  >
                    <Eye size={13} />
                    <span>Preview</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => handleDownload(report)}
                    className="inline-flex items-center gap-1.5 px-4 py-1.5 rounded-full text-xs font-bold text-white shadow-xs transition-all hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
                    style={{
                      background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)'
                    }}
                  >
                    <Download size={13} className="text-white" />
                    <span>Download</span>
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* =====================================================================
          OFFICIAL REPORT PREVIEW MODAL (Portaled to document.body)
          ===================================================================== */}
      {previewReport && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setPreviewReport(null)}
        >
          <div 
            className="w-full max-w-[620px] rounded-[32px] overflow-hidden flex flex-col bg-white border border-slate-100 shadow-[0_24px_70px_-12px_rgba(16,38,28,0.3)] animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-7 py-5 border-b border-slate-100 bg-gradient-to-b from-[#f2f8f5]/90 to-white">
              <div className="flex items-center gap-3.5 flex-1 min-w-0 pr-3">
                <div 
                  className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 shadow-md shadow-[#14654a]/20"
                  style={{
                    background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                    color: '#ffffff'
                  }}
                >
                  <FileText size={22} className="text-white" strokeWidth={2.2} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-extrabold text-[#10261c] text-base md:text-lg font-display tracking-tight truncate">
                      {previewReport.title}
                    </h3>
                  </div>
                  <p className="text-xs text-[#5d7468] mt-0.5 font-medium">
                    Official Statutory Preview • Ref: {previewReport.id}
                  </p>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setPreviewReport(null)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-800 bg-slate-100/80 hover:bg-slate-200/80 transition-all shrink-0 cursor-pointer hover:rotate-90 duration-200"
                aria-label="Close dialog"
              >
                <X size={16} strokeWidth={2.2} />
              </button>
            </div>

            {/* Modal Document Body */}
            <div className="p-7 space-y-4 text-xs md:text-sm">
              {/* Document Header Crest & Reference */}
              <div className="p-4 rounded-2xl bg-slate-50/80 border border-slate-200/80 flex items-center justify-between">
                <div>
                  <span className="text-[10px] font-bold text-[#7a8b84] uppercase tracking-wider block">Issuing Authority</span>
                  <span className="font-extrabold text-xs text-[#10261c] font-display">Ministry of Consumer Affairs, Food & Public Distribution</span>
                  <span className="text-[11px] text-slate-500 block">State NFSA Automated Oversight Division</span>
                </div>
                <div className="text-right">
                  <span className="text-[10.5px] font-bold text-emerald-800 bg-emerald-100/80 px-2.5 py-0.5 rounded-full inline-block">
                    ✓ Cryptographically Signed
                  </span>
                  <span className="text-[10px] text-slate-400 block mt-1">Verified on 2026-08-22</span>
                </div>
              </div>

              {/* Structured Key Findings Lines */}
              <div className="space-y-2">
                <span className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Dossier Executive Summary & Metrics
                </span>
                <div className="p-4 rounded-2xl bg-[#f2f8f5]/90 border border-[#d3ebd9] space-y-2 text-xs text-slate-700 leading-relaxed font-medium">
                  {previewReport.lines.map((line, idx) => (
                    <div key={idx} className="flex items-start gap-2">
                      <span className="text-[#14654a] font-bold mt-0.5">•</span>
                      <span>{line}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Compliance Sign-off */}
              <div className="p-3 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-between text-xs text-[#5d7468]">
                <span>Logistics Controller: P. K. Verma (UID: FCI-LOG-884)</span>
                <span className="font-mono text-[11px] font-bold text-slate-600">SHA-256: 8f4b...19c2</span>
              </div>

              {/* Modal Actions */}
              <div className="flex items-center justify-between pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setPreviewReport(null)}
                  className="px-4 py-2.5 rounded-full text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Close Preview
                </button>

                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      window.print();
                    }}
                    className="inline-flex items-center gap-1.5 px-4 py-2.5 rounded-full text-xs font-bold text-slate-700 bg-slate-100 hover:bg-slate-200 transition-colors cursor-pointer"
                  >
                    <Printer size={14} />
                    <span>Print Dossier</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      handleDownload(previewReport);
                      setPreviewReport(null);
                    }}
                    className="inline-flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-bold text-white shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
                    style={{
                      background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                      boxShadow: '0 8px 18px -4px rgba(20, 101, 74, 0.45)'
                    }}
                  >
                    <Download size={14} className="text-white" />
                    <span>Download {previewReport.format}</span>
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>,
        document.body
      )}

      {/* =====================================================================
          GENERATE CUSTOM DOSSIER WIZARD MODAL (Portaled to document.body)
          ===================================================================== */}
      {isGeneratorOpen && createPortal(
        <div 
          className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-md animate-in fade-in duration-200"
          onClick={() => setIsGeneratorOpen(false)}
        >
          <div 
            className="w-full max-w-[560px] rounded-[32px] overflow-hidden flex flex-col bg-white border border-slate-100 shadow-[0_24px_70px_-12px_rgba(16,38,28,0.3)] animate-in zoom-in-95 duration-200"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal Header */}
            <div className="flex items-center justify-between px-7 py-5 border-b border-slate-100 bg-gradient-to-b from-[#f2f8f5]/90 to-white">
              <div className="flex items-center gap-3.5 flex-1 min-w-0 pr-3">
                <div 
                  className="w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 shadow-md shadow-[#14654a]/20"
                  style={{
                    background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                    color: '#ffffff'
                  }}
                >
                  <PlusCircle size={22} className="text-white" strokeWidth={2.2} />
                </div>
                <div className="flex-1 min-w-0">
                  <h3 className="font-extrabold text-[#10261c] text-lg font-display tracking-tight">
                    Compile Custom Compliance Dossier
                  </h3>
                  <p className="text-xs text-[#5d7468] mt-0.5 font-medium">
                    Filter regional datasets and export statutory audit spreadsheets
                  </p>
                </div>
              </div>
              <button 
                type="button"
                onClick={() => setIsGeneratorOpen(false)} 
                className="w-8 h-8 rounded-full flex items-center justify-center text-slate-400 hover:text-slate-800 bg-slate-100/80 hover:bg-slate-200/80 transition-all shrink-0 cursor-pointer hover:rotate-90 duration-200"
                aria-label="Close dialog"
              >
                <X size={16} strokeWidth={2.2} />
              </button>
            </div>

            {/* Modal Form */}
            <form onSubmit={handleCompileCustomDossier} className="p-7 space-y-4 text-xs md:text-sm">
              <div className="space-y-1.5">
                <label className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Dossier Title *
                </label>
                <input
                  type="text"
                  required
                  value={generatorForm.title}
                  onChange={(e) => setGeneratorForm({ ...generatorForm, title: e.target.value })}
                  className="w-full px-3.5 py-2.5 border border-slate-200/90 rounded-xl text-xs font-bold text-[#10261c] bg-white focus:outline-none focus:border-[#14654a] focus:ring-2 focus:ring-[#14654a]/15 transition-all"
                />
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                    Category Scope
                  </label>
                  <div className="relative">
                    <select
                      value={generatorForm.category}
                      onChange={(e) => setGeneratorForm({ ...generatorForm, category: e.target.value })}
                      className="w-full px-3 py-2.5 border border-slate-200/90 rounded-xl text-xs font-semibold text-[#10261c] bg-white focus:outline-none focus:border-[#14654a] appearance-none cursor-pointer pr-8"
                    >
                      <option value="Statutory">Statutory Compliance</option>
                      <option value="Logistics">Logistics & Silo</option>
                      <option value="AI Audits">AI Anomaly Audits</option>
                      <option value="Beneficiary">Beneficiary Welfare</option>
                    </select>
                    <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  </div>
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                    Target District
                  </label>
                  <div className="relative">
                    <select
                      value={generatorForm.district}
                      onChange={(e) => setGeneratorForm({ ...generatorForm, district: e.target.value })}
                      className="w-full px-3 py-2.5 border border-slate-200/90 rounded-xl text-xs font-semibold text-[#10261c] bg-white focus:outline-none focus:border-[#14654a] appearance-none cursor-pointer pr-8"
                    >
                      <option value="All Districts">All Districts (Consolidated)</option>
                      <option value="East Delhi">East Delhi</option>
                      <option value="Delhi">Delhi Central</option>
                      <option value="Lucknow">Lucknow</option>
                      <option value="Aurangabad">Aurangabad</option>
                      <option value="Gwalior">Gwalior</option>
                    </select>
                    <ChevronDown size={14} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                  </div>
                </div>
              </div>

              {/* Format Selection */}
              <div className="space-y-1.5 pt-1">
                <label className="text-[11px] font-bold text-[#5d7468] uppercase tracking-wider block">
                  Output Format
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    onClick={() => setGeneratorForm({ ...generatorForm, format: 'PDF' })}
                    className={`p-3 rounded-2xl border text-center transition-all cursor-pointer ${
                      generatorForm.format === 'PDF'
                        ? 'bg-[#14654a]/8 border-[#14654a] text-[#14654a] shadow-xs font-bold'
                        : 'bg-slate-50 border-slate-200 text-slate-600'
                    }`}
                  >
                    <span className="block font-bold">Official PDF Document</span>
                    <span className="text-[10px] text-slate-500">Includes seals & sign-off</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => setGeneratorForm({ ...generatorForm, format: 'CSV' })}
                    className={`p-3 rounded-2xl border text-center transition-all cursor-pointer ${
                      generatorForm.format === 'CSV'
                        ? 'bg-[#14654a]/8 border-[#14654a] text-[#14654a] shadow-xs font-bold'
                        : 'bg-slate-50 border-slate-200 text-slate-600'
                    }`}
                  >
                    <span className="block font-bold">CSV Raw Spreadsheet</span>
                    <span className="text-[10px] text-slate-500">Excel / BI Tool Import</span>
                  </button>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => setIsGeneratorOpen(false)}
                  className="px-5 py-2.5 rounded-full text-xs font-bold text-slate-600 hover:text-slate-900 hover:bg-slate-100 transition-colors cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="inline-flex items-center gap-2 px-6 py-2.5 rounded-full text-xs font-bold text-white shadow-md transition-all duration-200 hover:scale-[1.02] active:scale-[0.98] cursor-pointer"
                  style={{
                    background: 'linear-gradient(135deg, #062d22 0%, #14654a 52%, #2fa56f 100%)',
                    boxShadow: '0 8px 18px -4px rgba(20, 101, 74, 0.45)'
                  }}
                >
                  <Sparkles size={14} className="text-white" />
                  <span>Compile & Download</span>
                </button>
              </div>
            </form>
          </div>
        </div>,
        document.body
      )}
    </div>
  );
};
