import type { Detection } from '../types';

interface DetectionCardProps {
  detection: Detection;
  index: number;
}

export default function DetectionCard({ detection, index }: DetectionCardProps) {
  const confPercent = Math.round(detection.confidence * 100);

  const confColor =
    confPercent >= 70
      ? 'text-status-active'
      : confPercent >= 50
        ? 'text-status-warning'
        : 'text-status-danger';

  const barColor =
    confPercent >= 70
      ? 'bg-status-active'
      : confPercent >= 50
        ? 'bg-status-warning'
        : 'bg-status-danger';

  return (
    <div className="glass-panel p-3 animate-slide-up" style={{ animationDelay: `${index * 50}ms` }}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-accent-cyan bg-accent-cyan/10 px-1.5 py-0.5 rounded">
            #{index + 1}
          </span>
          <span className="text-sm font-semibold text-text-primary capitalize">
            {detection.class_name}
          </span>
        </div>
        <span className={`text-sm font-mono font-bold ${confColor}`}>
          {confPercent}%
        </span>
      </div>

      {/* Confidence bar */}
      <div className="w-full bg-bg-input rounded-full h-1.5 mb-3">
        <div
          className={`h-1.5 rounded-full ${barColor} transition-all duration-500`}
          style={{ width: `${confPercent}%` }}
        />
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
        <div className="flex justify-between">
          <span className="text-text-muted">Position</span>
          <span className="font-mono text-text-secondary">
            ({Math.round(detection.center_x)}, {Math.round(detection.center_y)})
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">Size</span>
          <span className="font-mono text-text-secondary">
            {Math.round(detection.width)}×{Math.round(detection.height)}
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">Bbox</span>
          <span className="font-mono text-text-secondary">
            ({Math.round(detection.bbox.x)}, {Math.round(detection.bbox.y)})
          </span>
        </div>
        <div className="flex justify-between">
          <span className="text-text-muted">Frame</span>
          <span className="font-mono text-text-secondary">
            {detection.frame_id}
          </span>
        </div>
      </div>
    </div>
  );
}
