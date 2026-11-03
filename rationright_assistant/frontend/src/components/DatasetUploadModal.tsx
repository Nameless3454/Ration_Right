import React, { useState, useRef } from "react";
import { X, UploadCloud, CheckCircle2, AlertTriangle, FileArchive, Loader2 } from "lucide-react";
import { apiService } from "../services/api";
import { ImportBatchResponse } from "../types/api";

interface DatasetUploadModalProps {
  isOpen: boolean;
  onClose: () => void;
  onUploadSuccess: (batch: ImportBatchResponse) => void;
}

export const DatasetUploadModal: React.FC<DatasetUploadModalProps> = ({
  isOpen,
  onClose,
  onUploadSuccess,
}) => {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successBatch, setSuccessBatch] = useState<ImportBatchResponse | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);

  if (!isOpen) return null;

  const handleFileDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      validateAndSetFile(file);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      validateAndSetFile(e.target.files[0]);
    }
  };

  const validateAndSetFile = (file: File) => {
    setErrorMsg(null);
    setSuccessBatch(null);

    const ext = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
    if (![".zip", ".csv", ".json"].includes(ext)) {
      setErrorMsg("Only .zip, .csv, and .json files are supported.");
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setErrorMsg("File exceeds the 50MB maximum upload limit.");
      return;
    }

    setSelectedFile(file);
    if (!datasetName) {
      setDatasetName(file.name.replace(/\.[^/.]+$/, ""));
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedFile) {
      setErrorMsg("Please select a valid dataset file to upload.");
      return;
    }

    setIsUploading(true);
    setErrorMsg(null);

    try {
      const response = await apiService.uploadDataset(selectedFile, datasetName);
      setSuccessBatch(response);
      onUploadSuccess(response);
    } catch (err: any) {
      setErrorMsg(err.message || "Failed to upload and import dataset.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleReset = () => {
    setSelectedFile(null);
    setDatasetName("");
    setErrorMsg(null);
    setSuccessBatch(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/60 backdrop-blur-sm animate-in fade-in duration-150">
      <div className="bg-white rounded-xl shadow-2xl border border-slate-200 max-w-lg w-full overflow-hidden">
        {/* Header */}
        <div className="px-6 py-4 bg-gov-900 text-white flex items-center justify-between border-b border-gov-800">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 rounded-lg bg-gov-800 border border-gov-700">
              <UploadCloud className="w-5 h-5 text-india-saffron" />
            </div>
            <div>
              <h3 className="text-base font-bold">Import Weekly Dataset</h3>
              <p className="text-xs text-gov-300">Preserves historical snapshots and updates metrics</p>
            </div>
          </div>
          <button
            onClick={() => {
              handleReset();
              onClose();
            }}
            className="text-gov-300 hover:text-white p-1 rounded-md transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          {successBatch ? (
            <div className="text-center py-4 space-y-4">
              <div className="w-12 h-12 mx-auto rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600">
                <CheckCircle2 className="w-7 h-7" />
              </div>
              <div>
                <h4 className="text-base font-bold text-slate-900">Dataset Imported Successfully</h4>
                <p className="text-xs text-slate-500 mt-1">
                  Batch ID: <span className="font-mono font-medium text-slate-800">{successBatch.import_id}</span>
                </p>
              </div>

              {/* Table counts grid */}
              <div className="bg-slate-50 border border-slate-200 rounded-lg p-3 text-left">
                <p className="text-xs font-semibold text-slate-700 mb-2">Processed Record Totals:</p>
                <div className="grid grid-cols-2 gap-2 text-xs">
                  {Object.entries(successBatch.table_counts || {}).map(([table, count]) => (
                    <div key={table} className="flex justify-between py-1 border-b border-slate-200/60">
                      <span className="capitalize text-slate-600">{table.replace("_", " ")}:</span>
                      <span className="font-semibold text-slate-900">{count.toLocaleString()}</span>
                    </div>
                  ))}
                  <div className="flex justify-between py-1 font-bold text-gov-800 col-span-2 pt-2 border-t border-slate-300">
                    <span>Total Records:</span>
                    <span>{successBatch.total_records.toLocaleString()}</span>
                  </div>
                </div>
              </div>

              <div className="flex justify-center gap-2 pt-2">
                <button
                  type="button"
                  onClick={handleReset}
                  className="px-4 py-2 text-xs font-semibold rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-100 transition"
                >
                  Upload Another File
                </button>
                <button
                  type="button"
                  onClick={() => {
                    handleReset();
                    onClose();
                  }}
                  className="px-4 py-2 text-xs font-semibold rounded-lg bg-gov-700 hover:bg-gov-600 text-white transition shadow-sm"
                >
                  View Operations Metrics
                </button>
              </div>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="space-y-4">
              {/* Dropzone */}
              <div
                onDragOver={(e) => {
                  e.preventDefault();
                  setIsDragOver(true);
                }}
                onDragLeave={() => setIsDragOver(false)}
                onDrop={handleFileDrop}
                onClick={() => fileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-6 text-center cursor-pointer transition ${
                  isDragOver
                    ? "border-gov-500 bg-gov-50"
                    : selectedFile
                    ? "border-emerald-400 bg-emerald-50/50"
                    : "border-slate-300 hover:border-gov-400 hover:bg-slate-50"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".zip,.csv,.json"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                {selectedFile ? (
                  <div className="flex flex-col items-center">
                    <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-600 mb-2">
                      <FileArchive className="w-5 h-5" />
                    </div>
                    <p className="text-sm font-semibold text-slate-800">{selectedFile.name}</p>
                    <p className="text-xs text-slate-500 mt-0.5">
                      {(selectedFile.size / (1024 * 1024)).toFixed(2)} MB • Click to change
                    </p>
                  </div>
                ) : (
                  <div className="flex flex-col items-center">
                    <div className="w-10 h-10 rounded-full bg-gov-100 flex items-center justify-center text-gov-700 mb-2">
                      <UploadCloud className="w-5 h-5" />
                    </div>
                    <p className="text-sm font-semibold text-slate-800">
                      Drag and drop your weekly dataset here
                    </p>
                    <p className="text-xs text-slate-500 mt-1">
                      Supports ZIP archives (containing CSVs/JSON) or individual CSV files (up to 50MB)
                    </p>
                  </div>
                )}
              </div>

              {/* Dataset Name Input */}
              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Dataset Batch Label (Optional)
                </label>
                <input
                  type="text"
                  value={datasetName}
                  onChange={(e) => setDatasetName(e.target.value)}
                  placeholder="e.g. RationRight_Week_43_Snapshot"
                  className="w-full text-xs px-3 py-2 border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-gov-500"
                />
              </div>

              {/* Error Alert */}
              {errorMsg && (
                <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">
                  <AlertTriangle className="w-4 h-4 text-red-500 shrink-0 mt-0.5" />
                  <span>{errorMsg}</span>
                </div>
              )}

              {/* Submit / Cancel Buttons */}
              <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-100">
                <button
                  type="button"
                  onClick={() => {
                    handleReset();
                    onClose();
                  }}
                  disabled={isUploading}
                  className="px-4 py-2 text-xs font-medium rounded-lg text-slate-600 hover:bg-slate-100 transition disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!selectedFile || isUploading}
                  className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold rounded-lg bg-gov-700 hover:bg-gov-600 text-white transition disabled:opacity-50 disabled:cursor-not-allowed shadow-sm"
                >
                  {isUploading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      <span>Ingesting Dataset...</span>
                    </>
                  ) : (
                    <>
                      <UploadCloud className="w-4 h-4" />
                      <span>Upload & Ingest</span>
                    </>
                  )}
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

