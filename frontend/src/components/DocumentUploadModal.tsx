import { useCallback, useRef, useState, type ChangeEvent } from "react";

import { uploadWorkflowDocument, getOrchestratorErrorMessage } from "../api/orchestrator";

interface DocumentUploadModalProps {
  workflowId: string;
  missingDocuments: string[];
  onClose: () => void;
  onUploadComplete: (files: Array<{ name: string; size: string }>) => void;
}

export const DocumentUploadModal = ({
  workflowId,
  missingDocuments,
  onClose,
  onUploadComplete,
}: DocumentUploadModalProps) => {
  const [selectedType, setSelectedType] = useState(
    missingDocuments.length > 0 ? missingDocuments[0] : "",
  );
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadedFiles, setUploadedFiles] = useState<
    Array<{ name: string; size: string }>
  >([]);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const formatSize = (bytes: number): string => {
    const kb = Math.round(bytes / 1024);
    return kb > 1024 ? `${(kb / 1024).toFixed(1)} MB` : `${kb} KB`;
  };

  const handleFileChange = (event: ChangeEvent<HTMLInputElement>) => {
    const files = event.target.files;
    if (files && files.length > 0) {
      setSelectedFiles(Array.from(files));
      setError(null);
      setSuccessMessage(null);
    }
  };

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) {
      setError("Please select at least one file to upload.");
      return;
    }

    setUploading(true);
    setError(null);
    setSuccessMessage(null);

    const newUploaded: Array<{ name: string; size: string }> = [];

    for (const file of selectedFiles) {
      try {
        await uploadWorkflowDocument(
          workflowId,
          file,
          selectedType || undefined,
        );
        newUploaded.push({ name: file.name, size: formatSize(file.size) });
      } catch (uploadErr) {
        setError(getOrchestratorErrorMessage(uploadErr));
        setUploading(false);
        return;
      }
    }

    setUploadedFiles((prev) => [...prev, ...newUploaded]);
    setSuccessMessage(
      `Successfully uploaded ${newUploaded.length} document(s).`,
    );
    setSelectedFiles([]);
    if (fileInputRef.current) fileInputRef.current.value = "";
    setUploading(false);
  }, [selectedFiles, selectedType, workflowId]);

  const handleClose = () => {
    if (uploadedFiles.length > 0) {
      onUploadComplete(uploadedFiles);
    }
    onClose();
  };

  const handleOverlayClick = (event: React.MouseEvent<HTMLDivElement>) => {
    if (event.target === event.currentTarget) {
      handleClose();
    }
  };

  return (
    <div
      className="upload-modal-overlay"
      onClick={handleOverlayClick}
      role="dialog"
      aria-modal="true"
      aria-label="Upload Claim Documents"
    >
      <div className="upload-modal">
        <div className="upload-modal-header">
          <h2>Upload Claim Documents</h2>
          <button
            type="button"
            className="upload-modal-close"
            onClick={handleClose}
            aria-label="Close upload dialog"
          >
            ✕
          </button>
        </div>

        <div className="upload-modal-body">
          {missingDocuments.length > 0 && (
            <div className="upload-modal-section">
              <label
                htmlFor="upload-doc-type"
                className="upload-modal-label"
              >
                Document Type
              </label>
              <select
                id="upload-doc-type"
                className="upload-modal-select"
                value={selectedType}
                onChange={(e) => setSelectedType(e.target.value)}
                disabled={uploading}
              >
                {missingDocuments.map((doc) => (
                  <option key={doc} value={doc}>
                    {doc.replace(/_/g, " ")}
                  </option>
                ))}
              </select>
            </div>
          )}

          <div className="upload-modal-section">
            <label htmlFor="upload-file-input" className="upload-modal-label">
              Select File
            </label>
            <input
              ref={fileInputRef}
              id="upload-file-input"
              type="file"
              className="upload-modal-file-input"
              onChange={handleFileChange}
              multiple
              accept=".pdf,.png,.jpg,.jpeg,.doc,.docx"
              disabled={uploading}
            />
          </div>

          {selectedFiles.length > 0 && (
            <div className="upload-modal-selected">
              {selectedFiles.map((f, i) => (
                <span key={`${f.name}-${i}`} className="upload-modal-file-chip">
                  📄 {f.name} ({formatSize(f.size)})
                </span>
              ))}
            </div>
          )}

          {error && (
            <div className="alert alert-error upload-modal-alert" role="alert">
              {error}
            </div>
          )}

          {successMessage && (
            <div
              className="alert alert-success upload-modal-alert"
              role="status"
            >
              {successMessage}
            </div>
          )}

          {uploadedFiles.length > 0 && (
            <div className="upload-modal-uploaded">
              <p className="upload-modal-label">
                Uploaded ({uploadedFiles.length})
              </p>
              <div className="uploaded-file-chips">
                {uploadedFiles.map((f, i) => (
                  <span key={`${f.name}-${i}`} className="uploaded-file-chip">
                    <span aria-hidden="true">📄</span> {f.name} ({f.size})
                    <span className="file-check" aria-label="Uploaded">
                      ✓
                    </span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>

        <div className="upload-modal-footer">
          <button
            type="button"
            className="button button-secondary"
            onClick={handleClose}
          >
            Close
          </button>
          <button
            type="button"
            className="button button-primary"
            onClick={handleUpload}
            disabled={uploading || selectedFiles.length === 0}
          >
            {uploading ? "Uploading…" : "Upload"}
          </button>
        </div>
      </div>
    </div>
  );
};
