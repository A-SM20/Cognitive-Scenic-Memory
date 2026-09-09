import { useCallback, useState, useRef } from 'react';

interface ImageUploaderProps {
  onUpload: (file: File) => void;
  isProcessing: boolean;
  accept?: string;
  maxSizeMB?: number;
}

export default function ImageUploader({
  onUpload,
  isProcessing,
  accept = 'image/*',
  maxSizeMB = 20,
}: ImageUploaderProps) {
  const [isDragging, setIsDragging] = useState(false);
  const [preview, setPreview] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateAndSetFile = useCallback(
    (file: File) => {
      setError(null);

      if (!file.type.startsWith('image/')) {
        setError('Please upload an image file (JPEG, PNG, WebP, etc.)');
        return;
      }

      if (file.size > maxSizeMB * 1024 * 1024) {
        setError(`File too large. Maximum size: ${maxSizeMB}MB`);
        return;
      }

      setSelectedFile(file);

      // Create preview
      const reader = new FileReader();
      reader.onload = (e) => setPreview(e.target?.result as string);
      reader.readAsDataURL(file);
    },
    [maxSizeMB]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setIsDragging(false);
      const file = e.dataTransfer.files[0];
      if (file) validateAndSetFile(file);
    },
    [validateAndSetFile]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) validateAndSetFile(file);
    },
    [validateAndSetFile]
  );

  const handleProcess = () => {
    if (selectedFile) onUpload(selectedFile);
  };

  const handleClear = () => {
    setSelectedFile(null);
    setPreview(null);
    setError(null);
    if (fileInputRef.current) fileInputRef.current.value = '';
  };

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !isProcessing && fileInputRef.current?.click()}
        className={`
          relative rounded-xl border-2 border-dashed transition-all duration-200 cursor-pointer
          ${
            isDragging
              ? 'border-accent-cyan bg-accent-cyan/5 scale-[1.01]'
              : preview
                ? 'border-border bg-bg-card'
                : 'border-border hover:border-accent-cyan/50 bg-bg-card/50 hover:bg-bg-card'
          }
          ${isProcessing ? 'opacity-60 pointer-events-none' : ''}
        `}
      >
        {preview ? (
          <div className="p-2">
            <img
              src={preview}
              alt="Preview"
              className="w-full max-h-64 object-contain rounded-lg"
            />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center py-10 px-4">
            <div className="w-12 h-12 rounded-xl bg-accent-cyan/10 flex items-center justify-center mb-3">
              <span className="text-2xl text-accent-cyan">◎</span>
            </div>
            <p className="text-sm font-medium text-text-primary mb-1">
              Drop an image here or click to browse
            </p>
            <p className="text-xs text-text-muted">
              JPEG, PNG, WebP · Max {maxSizeMB}MB
            </p>
          </div>
        )}

        <input
          ref={fileInputRef}
          type="file"
          accept={accept}
          onChange={handleFileSelect}
          className="hidden"
          disabled={isProcessing}
        />
      </div>

      {/* Error */}
      {error && (
        <div className="text-xs text-status-danger bg-status-danger/10 px-3 py-2 rounded-lg">
          {error}
        </div>
      )}

      {/* File info & actions */}
      {selectedFile && (
        <div className="flex items-center justify-between gap-3">
          <div className="text-xs text-text-muted font-mono truncate flex-1">
            {selectedFile.name} · {(selectedFile.size / 1024).toFixed(1)} KB
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleClear}
              disabled={isProcessing}
              className="px-3 py-1.5 text-xs font-medium text-text-secondary bg-bg-card border border-border rounded-lg hover:bg-bg-card-hover transition-colors disabled:opacity-50"
            >
              Clear
            </button>
            <button
              onClick={handleProcess}
              disabled={isProcessing}
              className="px-4 py-1.5 text-xs font-semibold text-bg-primary bg-gradient-to-r from-accent-cyan to-accent-emerald rounded-lg hover:opacity-90 transition-opacity disabled:opacity-50 flex items-center gap-2"
            >
              {isProcessing ? (
                <>
                  <span className="w-3 h-3 border-2 border-bg-primary/30 border-t-bg-primary rounded-full animate-spin" />
                  Processing...
                </>
              ) : (
                <>◎ Detect Objects</>
              )}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
