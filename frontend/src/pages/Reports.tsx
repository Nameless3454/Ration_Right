import React from 'react';
import { FileText, Download } from 'lucide-react';

export const Reports: React.FC = () => {
  const downloadMockPdf = (filename: string, title: string, reportLines: string[]) => {
    // Basic PDF syntax with a text stream
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
  };

  const handleDownloadMonthly = () => {
    downloadMockPdf(
      'monthly_audit_report_august_2026.pdf',
      'RationRight - Monthly Audit Report - August 2026',
      [
        'Total Registered Beneficiaries: 24,582 (Active: 23,410)',
        'Total Ration Distributed: 43,450.5 kg (Rice, Wheat, Sugar)',
        'Active Alert Flags Triggered: 447',
        'Unresolved High-Risk Cases: 148',
        'Data Sync Pipeline Status: 100% Operational',
        'Report compiled on: August 22, 2026',
        'Verification Authority: Food Security Command Center (RationRight)'
      ]
    );
  };

  const handleDownloadDiscrepancy = () => {
    downloadMockPdf(
      'district_allocation_discrepancy_index.pdf',
      'District Allocation Discrepancy Index',
      [
        'Report listing FPS terminal status and stock allocation records:',
        '-----------------------------------------------------------------',
        'Lucknow: 124 FPS Centers | 8,420 kg Distributed | Status: Healthy',
        'Delhi: 98 FPS Centers | 6,210 kg Distributed | Status: Warning',
        'Gwalior: 76 FPS Centers | 4,890 kg Distributed | Status: Healthy',
        'Aurangabad: 64 FPS Centers | 3,765 kg Distributed | Status: Warning',
        'East Delhi: 52 FPS Centers | 2,980 kg Distributed | Status: Critical',
        '-----------------------------------------------------------------',
        'Report compiled on: August 22, 2026',
        'RationRight Open Data sync verified.'
      ]
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl md:text-2xl font-bold text-slate-800 tracking-tight">Reports & Dispatches</h1>
        <p className="text-xs md:text-sm text-slate-500 mt-1">Export transaction logs and distribution audit sheets.</p>
      </div>

      <div className="bg-white border border-slate-200 rounded-lg p-5 divide-y divide-slate-100 space-y-4">
        <div className="flex items-center justify-between pb-4">
          <div className="flex gap-3 items-start">
            <FileText size={18} className="text-slate-400 mt-0.5" />
            <div>
              <h4 className="font-semibold text-slate-800 text-sm">Monthly Audit Report - August 2026</h4>
              <p className="text-xs text-slate-400 mt-0.5">Summary of transaction anomalies, verified cases, and inventory audits.</p>
            </div>
          </div>
          <button 
            onClick={handleDownloadMonthly}
            className="p-2 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded transition-colors"
          >
            <Download size={14} />
          </button>
        </div>

        <div className="flex items-center justify-between pt-4">
          <div className="flex gap-3 items-start">
            <FileText size={18} className="text-slate-400 mt-0.5" />
            <div>
              <h4 className="font-semibold text-slate-800 text-sm">District Allocation Discrepancy Index</h4>
              <p className="text-xs text-slate-400 mt-0.5">Spreadsheet recording FPS stock discrepancies sorted by regional risk indices.</p>
            </div>
          </div>
          <button 
            onClick={handleDownloadDiscrepancy}
            className="p-2 border border-slate-200 hover:bg-slate-50 text-slate-600 rounded transition-colors"
          >
            <Download size={14} />
          </button>
        </div>
      </div>
    </div>
  );
};
