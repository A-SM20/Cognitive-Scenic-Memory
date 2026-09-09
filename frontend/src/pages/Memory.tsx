import { useState, useEffect, useCallback } from 'react';
import { getMemorySummary, getMemoryObjects, triggerDecay, clearMemory } from '../services/api';
import type { MemorySummary, MemoryObject } from '../types';

const STATUS_CONFIG: Record<string, { color: string; bg: string; icon: string }> = {
  ACTIVE: { color: 'text-accent-emerald', bg: 'bg-accent-emerald/15', icon: '●' },
  POSSIBLY_MISSING: { color: 'text-accent-amber', bg: 'bg-accent-amber/15', icon: '◐' },
  MISSING: { color: 'text-accent-red', bg: 'bg-accent-red/15', icon: '○' },
  REMOVED: { color: 'text-text-muted', bg: 'bg-bg-card', icon: '✕' },
  UNKNOWN: { color: 'text-accent-purple', bg: 'bg-accent-purple/15', icon: '?' },
};

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color =
    value >= 0.7 ? 'bg-accent-emerald' :
    value >= 0.4 ? 'bg-accent-amber' :
    'bg-accent-red';

  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-1.5 bg-bg-input rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-500 ${color}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-mono text-text-muted w-8 text-right">{pct}%</span>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const config = STATUS_CONFIG[status] || STATUS_CONFIG.UNKNOWN;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium ${config.color} ${config.bg}`}>
      <span>{config.icon}</span>
      {status.replace('_', ' ')}
    </span>
  );
}

function SummaryCard({ label, value, color, icon }: { label: string; value: number; color: string; icon: string }) {
  return (
    <div className="glass-panel p-4 flex items-center gap-3 animate-slide-up">
      <div className={`w-10 h-10 rounded-lg ${color} flex items-center justify-center text-lg`}>
        {icon}
      </div>
      <div>
        <div className="text-2xl font-bold text-text-primary tabular-nums">{value}</div>
        <div className="text-xs text-text-muted">{label}</div>
      </div>
    </div>
  );
}

export default function Memory() {
  const [summary, setSummary] = useState<MemorySummary | null>(null);
  const [objects, setObjects] = useState<MemoryObject[]>([]);
  const [loading, setLoading] = useState(true);
  const [decaying, setDecaying] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [filter, setFilter] = useState<string>('ALL');

  const loadData = useCallback(async () => {
    try {
      const [s, o] = await Promise.all([getMemorySummary(), getMemoryObjects()]);
      setSummary(s);
      setObjects(o);
    } catch (err) {
      console.error('Failed to load memory data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDecay = async () => {
    setDecaying(true);
    try {
      await triggerDecay();
      await loadData();
    } catch (err) {
      console.error('Decay failed:', err);
    } finally {
      setDecaying(false);
    }
  };

  const handleClear = async () => {
    if (!window.confirm('Are you sure you want to clear all stored object memory and scene history?')) {
      return;
    }
    setClearing(true);
    try {
      await clearMemory();
      await loadData();
    } catch (err) {
      console.error('Clear failed:', err);
    } finally {
      setClearing(false);
    }
  };

  const filtered = filter === 'ALL' ? objects : objects.filter(o => o.status === filter);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-text-muted animate-pulse">Loading memory state...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Cognitive Memory</h2>
          <p className="text-sm text-text-muted mt-0.5">
            Persistent object memory with Bayesian confidence model
          </p>
        </div>
        <div className="flex items-center gap-2.5">
          <button
            onClick={handleClear}
            disabled={clearing}
            className="px-3.5 py-2 rounded-lg bg-accent-red/15 text-accent-red border border-accent-red/25
                       hover:bg-accent-red/25 transition-all text-sm font-medium disabled:opacity-50"
          >
            {clearing ? 'Clearing…' : '🗑 Clear Memory'}
          </button>
          <button
            onClick={handleDecay}
            disabled={decaying}
            className="px-4 py-2 rounded-lg bg-accent-amber/15 text-accent-amber border border-accent-amber/25
                       hover:bg-accent-amber/25 transition-all text-sm font-medium disabled:opacity-50"
          >
            {decaying ? 'Decaying…' : '⚡ Trigger Decay'}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <SummaryCard label="Active" value={summary.active} color="bg-accent-emerald/15" icon="●" />
          <SummaryCard label="Possibly Missing" value={summary.possibly_missing} color="bg-accent-amber/15" icon="◐" />
          <SummaryCard label="Missing" value={summary.missing} color="bg-accent-red/15" icon="○" />
          <SummaryCard label="Removed" value={summary.removed} color="bg-bg-card" icon="✕" />
        </div>
      )}

      {/* Stats Bar */}
      {summary && (
        <div className="glass-panel p-3 flex items-center gap-6 text-xs text-text-muted">
          <span>Total Objects: <span className="text-text-primary font-semibold">{summary.total_objects}</span></span>
          <span>Scenes: <span className="text-text-primary font-semibold">{summary.total_scenes}</span></span>
          <span>Avg Confidence: <span className="text-accent-cyan font-semibold">{(summary.average_confidence * 100).toFixed(1)}%</span></span>
        </div>
      )}

      {/* Filter Bar */}
      <div className="flex items-center gap-2">
        {['ALL', 'ACTIVE', 'POSSIBLY_MISSING', 'MISSING', 'REMOVED'].map(s => (
          <button
            key={s}
            onClick={() => setFilter(s)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border
              ${filter === s
                ? 'bg-accent-cyan/15 text-accent-cyan border-accent-cyan/25'
                : 'text-text-muted border-border hover:bg-bg-card hover:text-text-secondary'
              }`}
          >
            {s.replace('_', ' ')}
            {s !== 'ALL' && summary && (
              <span className="ml-1 opacity-60">
                ({s === 'ACTIVE' ? summary.active
                  : s === 'POSSIBLY_MISSING' ? summary.possibly_missing
                  : s === 'MISSING' ? summary.missing
                  : summary.removed})
              </span>
            )}
          </button>
        ))}
      </div>

      {/* Object Table */}
      <div className="glass-panel overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border text-xs text-text-muted">
                <th className="text-left px-4 py-3 font-medium">Object</th>
                <th className="text-left px-4 py-3 font-medium">Class</th>
                <th className="text-left px-4 py-3 font-medium">Status</th>
                <th className="text-left px-4 py-3 font-medium">Confidence</th>
                <th className="text-left px-4 py-3 font-medium">Observations</th>
                <th className="text-left px-4 py-3 font-medium">First Seen</th>
                <th className="text-left px-4 py-3 font-medium">Last Seen</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((obj) => (
                <tr
                  key={obj.object_id}
                  className="border-b border-border/50 hover:bg-bg-card-hover transition-colors"
                >
                  <td className="px-4 py-3">
                    <span className="font-mono text-xs text-accent-cyan">{obj.object_id}</span>
                  </td>
                  <td className="px-4 py-3">
                    <span className="font-medium text-text-primary">{obj.class_name}</span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={obj.status} />
                  </td>
                  <td className="px-4 py-3">
                    <ConfidenceBar value={obj.current_confidence} />
                  </td>
                  <td className="px-4 py-3 text-text-secondary tabular-nums">
                    {obj.observation_count}
                  </td>
                  <td className="px-4 py-3 text-text-muted text-xs font-mono">
                    {new Date(obj.first_seen).toLocaleString()}
                  </td>
                  <td className="px-4 py-3 text-text-muted text-xs font-mono">
                    {new Date(obj.last_seen).toLocaleString()}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-text-muted">
                    No objects found{filter !== 'ALL' ? ` with status ${filter}` : ''}
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
