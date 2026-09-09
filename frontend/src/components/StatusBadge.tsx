interface StatusBadgeProps {
  status: string;
  size?: 'sm' | 'md';
}

const STATUS_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  ok: { bg: 'bg-status-active/10', text: 'text-status-active', dot: 'bg-status-active' },
  active: { bg: 'bg-status-active/10', text: 'text-status-active', dot: 'bg-status-active' },
  visible: { bg: 'bg-status-active/10', text: 'text-status-active', dot: 'bg-status-active' },
  degraded: { bg: 'bg-status-warning/10', text: 'text-status-warning', dot: 'bg-status-warning' },
  possibly_missing: { bg: 'bg-status-warning/10', text: 'text-status-warning', dot: 'bg-status-warning' },
  warning: { bg: 'bg-status-warning/10', text: 'text-status-warning', dot: 'bg-status-warning' },
  offline: { bg: 'bg-status-danger/10', text: 'text-status-danger', dot: 'bg-status-danger' },
  missing: { bg: 'bg-status-danger/10', text: 'text-status-danger', dot: 'bg-status-danger' },
  removed: { bg: 'bg-status-danger/10', text: 'text-status-danger', dot: 'bg-status-danger' },
  unknown: { bg: 'bg-text-muted/10', text: 'text-text-muted', dot: 'bg-text-muted' },
};

export default function StatusBadge({ status, size = 'sm' }: StatusBadgeProps) {
  const key = status.toLowerCase();
  const style = STATUS_STYLES[key] || STATUS_STYLES.unknown;

  const sizeClasses = size === 'sm' ? 'text-[10px] px-2 py-0.5' : 'text-xs px-2.5 py-1';
  const dotSize = size === 'sm' ? 'w-1 h-1' : 'w-1.5 h-1.5';

  return (
    <span
      className={`
        inline-flex items-center gap-1.5 rounded-full font-mono font-medium uppercase
        ${style.bg} ${style.text} ${sizeClasses}
      `}
    >
      <span className={`${dotSize} rounded-full ${style.dot}`} />
      {status}
    </span>
  );
}
