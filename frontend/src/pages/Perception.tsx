import { useState, useEffect } from 'react';
import ImageUploader from '../components/ImageUploader';
import DetectionCard from '../components/DetectionCard';
import type { DetectionResult } from '../types';
import { processImage, getLatestDetection } from '../services/api';

export default function Perception() {
  const [result, setResult] = useState<DetectionResult | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);

  const fetchLatest = async () => {
    setIsSyncing(true);
    try {
      const latest = await getLatestDetection();
      if (latest) {
        setResult(latest);
      }
    } catch {
      // Ignore error if no scenes exist yet
    } finally {
      setIsSyncing(false);
    }
  };

  useEffect(() => {
    fetchLatest();
  }, []);

  const handleUpload = async (file: File) => {
    setIsProcessing(true);
    setError(null);
    setResult(null);

    try {
      const detectionResult = await processImage(file);
      setResult(detectionResult);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Detection failed');
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Live Perception</h2>
          <p className="text-sm text-text-muted mt-1">
            Real-time YOLO object detection with Pi 5 robot sync and manual upload
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={fetchLatest}
            disabled={isSyncing}
            className="px-3 py-1.5 text-xs font-medium rounded-lg bg-accent-cyan/15 hover:bg-accent-cyan/25 text-accent-cyan border border-accent-cyan/30 transition flex items-center gap-1.5"
            title="Fetch the latest image processed from the Raspberry Pi or upload"
          >
            <span className={isSyncing ? 'animate-spin' : ''}>🔄</span>
            <span>{isSyncing ? 'Syncing...' : 'Sync Robot Scan'}</span>
          </button>

          {result && (
            <div className="text-right">
              <div className="text-xs text-text-muted">Active Scene</div>
              <div className="text-sm font-mono text-accent-cyan">{result.scene_id}</div>
            </div>
          )}
        </div>
      </div>

      {/* Upload Area */}
      <div className="glass-panel p-5">
        <div className="flex items-center gap-2 mb-3">
          <span className="text-accent-cyan">◎</span>
          <h3 className="text-sm font-semibold text-text-primary">Image Input</h3>
        </div>
        <ImageUploader onUpload={handleUpload} isProcessing={isProcessing} />
      </div>

      {/* Error */}
      {error && (
        <div className="glass-panel p-4 border-status-danger/30">
          <div className="flex items-center gap-2 text-status-danger text-sm">
            <span>⚠</span>
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Results */}
      {result && (
        <>
          {/* Annotated Image */}
          <div className="glass-panel p-5">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <span className="text-accent-emerald">◉</span>
                <h3 className="text-sm font-semibold text-text-primary">Detection Results</h3>
              </div>
              <div className="flex items-center gap-4 text-xs">
                <MetaTag label="Objects" value={String(result.total_objects)} accent="emerald" />
                <MetaTag label="Time" value={`${result.processing_time_ms.toFixed(0)}ms`} accent="cyan" />
                <MetaTag label="Model" value={result.model_name} accent="purple" />
                <MetaTag label="Size" value={`${result.image_width}×${result.image_height}`} />
              </div>
            </div>

            {/* Annotated image display */}
            <div className="bg-bg-input rounded-xl overflow-hidden border border-border">
              <img
                src={result.annotated_image_url}
                alt="Detection results with bounding boxes"
                className="w-full max-h-[500px] object-contain"
              />
            </div>
          </div>

          {/* Detection List */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="text-accent-amber">▣</span>
              <h3 className="text-sm font-semibold text-text-primary">
                Detected Objects ({result.detections.length})
              </h3>
            </div>

            {result.detections.length === 0 ? (
              <div className="glass-panel p-8 text-center">
                <p className="text-sm text-text-muted">
                  No objects detected above the confidence threshold.
                </p>
                <p className="text-xs text-text-muted mt-1">
                  Try a different image or lower the confidence threshold in settings.
                </p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                {result.detections.map((det, i) => (
                  <DetectionCard key={i} detection={det} index={i} />
                ))}
              </div>
            )}
          </div>

          {/* Detection Summary Table */}
          {result.detections.length > 0 && (
            <div className="glass-panel p-5">
              <div className="flex items-center gap-2 mb-3">
                <span className="text-accent-blue">≡</span>
                <h3 className="text-sm font-semibold text-text-primary">Detection Summary</h3>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full text-xs">
                  <thead>
                    <tr className="text-text-muted border-b border-border">
                      <th className="text-left py-2 px-3 font-semibold">#</th>
                      <th className="text-left py-2 px-3 font-semibold">Class</th>
                      <th className="text-left py-2 px-3 font-semibold">Confidence</th>
                      <th className="text-left py-2 px-3 font-semibold">Center</th>
                      <th className="text-left py-2 px-3 font-semibold">Bbox</th>
                      <th className="text-left py-2 px-3 font-semibold">Size</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.detections.map((det, i) => {
                      const conf = Math.round(det.confidence * 100);
                      const confColor =
                        conf >= 70
                          ? 'text-status-active'
                          : conf >= 50
                            ? 'text-status-warning'
                            : 'text-status-danger';

                      return (
                        <tr key={i} className="border-b border-border/50 hover:bg-bg-card-hover/50 transition-colors">
                          <td className="py-2 px-3 font-mono text-accent-cyan">{i + 1}</td>
                          <td className="py-2 px-3 font-medium text-text-primary capitalize">{det.class_name}</td>
                          <td className={`py-2 px-3 font-mono font-bold ${confColor}`}>{conf}%</td>
                          <td className="py-2 px-3 font-mono text-text-secondary">
                            ({Math.round(det.center_x)}, {Math.round(det.center_y)})
                          </td>
                          <td className="py-2 px-3 font-mono text-text-secondary">
                            ({Math.round(det.bbox.x)}, {Math.round(det.bbox.y)})
                          </td>
                          <td className="py-2 px-3 font-mono text-text-secondary">
                            {Math.round(det.width)}×{Math.round(det.height)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

function MetaTag({
  label,
  value,
  accent = 'cyan',
}: {
  label: string;
  value: string;
  accent?: string;
}) {
  const accentMap: Record<string, string> = {
    cyan: 'text-accent-cyan bg-accent-cyan/10',
    emerald: 'text-accent-emerald bg-accent-emerald/10',
    purple: 'text-accent-purple bg-accent-purple/10',
    amber: 'text-accent-amber bg-accent-amber/10',
  };

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-text-muted">{label}</span>
      <span className={`font-mono font-medium px-1.5 py-0.5 rounded ${accentMap[accent] || 'text-text-secondary'}`}>
        {value}
      </span>
    </div>
  );
}
