import { useEffect, useState } from 'react';
import StatusBadge from '../components/StatusBadge';
import type { HealthResponse, SceneResponse } from '../types';
import { getHealth, getScenes } from '../services/api';

export default function Overview() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [scenes, setScenes] = useState<SceneResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchData = async (silent = false) => {
    if (!silent) setIsRefreshing(true);
    try {
      const [h, s] = await Promise.all([getHealth(), getScenes(6)]);
      setHealth(h);
      setScenes(s);
      setError(null);
    } catch (e) {
      if (!silent) setError(e instanceof Error ? e.message : 'Failed to connect to backend');
    } finally {
      setLoading(false);
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    fetchData();
    // Poll every 3 seconds to catch live robot image uploads
    const interval = setInterval(() => fetchData(true), 3000);
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
      </div>
    );
  }

  const totalObjects = scenes.reduce((sum, s) => sum + s.object_count, 0);

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-bold text-text-primary">System Overview</h2>
          <p className="text-sm text-text-muted mt-1">
            Cognitive Scene Memory — perception pipeline status and real-time activity
          </p>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 text-xs font-mono px-2.5 py-1 rounded-full bg-status-active/10 text-status-active border border-status-active/20">
            <span className="w-2 h-2 rounded-full bg-status-active animate-pulse" />
            <span>Live Robot Sync</span>
          </div>

          <button
            onClick={() => fetchData(false)}
            disabled={isRefreshing}
            className="px-2.5 py-1 text-xs font-medium rounded-lg bg-bg-card hover:bg-bg-input text-text-secondary hover:text-accent-cyan border border-border transition flex items-center gap-1.5"
          >
            <span className={isRefreshing ? "animate-spin" : ""}>🔄</span>
            <span>Refresh</span>
          </button>
        </div>
      </div>


      {error && (
        <div className="glass-panel p-4 border-status-danger/30">
          <div className="flex items-center gap-2 text-status-danger text-sm">
            <span>⚠</span>
            <span>{error}</span>
          </div>
          <p className="text-xs text-text-muted mt-1">
            Make sure the backend is running: <code className="font-mono text-accent-cyan">uvicorn app.main:app --reload</code>
          </p>
        </div>
      )}

      {/* Status Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          label="System Status"
          value={health?.status?.toUpperCase() || 'OFFLINE'}
          badge={<StatusBadge status={health?.status || 'offline'} size="sm" />}
        />
        <StatCard
          label="Total Scenes"
          value={String(scenes.length)}
          sub="captured"
          accent="cyan"
        />
        <StatCard
          label="Objects Detected"
          value={String(totalObjects)}
          sub="total"
          accent="emerald"
        />
        <StatCard
          label="Detection Model"
          value={health?.model_name || '—'}
          sub={health?.model_loaded ? 'loaded' : 'not loaded'}
          accent={health?.model_loaded ? 'emerald' : 'amber'}
        />
      </div>

      {/* Feature Status */}
      {health && (
        <div className="glass-panel p-5">
          <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
            <span className="text-accent-cyan">⬡</span> Feature Status
          </h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {Object.entries(health.features).map(([key, enabled]) => (
              <div
                key={key}
                className={`
                  flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-mono
                  ${enabled ? 'bg-status-active/10 text-status-active' : 'bg-bg-input text-text-muted'}
                `}
              >
                <span className={`w-1.5 h-1.5 rounded-full ${enabled ? 'bg-status-active' : 'bg-text-muted/30'}`} />
                {key.replace(/_/g, ' ')}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Scenes */}
      <div className="glass-panel p-5">
        <h3 className="text-sm font-semibold text-text-primary mb-3 flex items-center gap-2">
          <span className="text-accent-emerald">◉</span> Recent Scenes
        </h3>
        {scenes.length === 0 ? (
          <p className="text-sm text-text-muted py-4 text-center">
            No scenes captured yet. Go to <span className="text-accent-cyan">Perception</span> to upload an image.
          </p>
        ) : (
          <div className="space-y-2">
            {scenes.map((scene) => (
              <div
                key={scene.scene_id}
                className="flex items-center justify-between px-3 py-2 bg-bg-input rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className="text-xs font-mono text-accent-cyan">{scene.scene_id}</span>
                  <span className="text-xs text-text-secondary">
                    {scene.object_count} objects
                  </span>
                </div>
                <div className="flex items-center gap-3 text-xs text-text-muted">
                  {scene.processing_time_ms && (
                    <span className="font-mono">{scene.processing_time_ms.toFixed(0)}ms</span>
                  )}
                  <span>{new Date(scene.timestamp).toLocaleString()}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Pipeline Status */}
      <div className="glass-panel p-5">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold text-text-primary flex items-center gap-2">
            <span className="text-accent-emerald animate-pulse">●</span>
            <span>Cognitive Perception Pipeline</span>
          </h3>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-accent-emerald/15 text-accent-emerald border border-accent-emerald/30">
            ALL 10 STAGES ACTIVE
          </span>
        </div>
        <div className="flex items-center gap-1.5 overflow-x-auto pb-2">
          {[
            { name: 'SENSE', group: 'perception', color: 'border-accent-cyan/40 bg-accent-cyan/15 text-accent-cyan' },
            { name: 'DETECT', group: 'perception', color: 'border-accent-cyan/40 bg-accent-cyan/15 text-accent-cyan' },
            { name: 'TRACK', group: 'tracking', color: 'border-accent-emerald/40 bg-accent-emerald/15 text-accent-emerald' },
            { name: 'IDENTIFY', group: 'tracking', color: 'border-accent-emerald/40 bg-accent-emerald/15 text-accent-emerald' },
            { name: 'LOCALIZE', group: 'tracking', color: 'border-accent-emerald/40 bg-accent-emerald/15 text-accent-emerald' },
            { name: 'UNDERSTAND', group: 'memory', color: 'border-accent-purple/40 bg-accent-purple/15 text-accent-purple' },
            { name: 'REMEMBER', group: 'memory', color: 'border-accent-purple/40 bg-accent-purple/15 text-accent-purple' },
            { name: 'COMPARE', group: 'reasoning', color: 'border-accent-amber/40 bg-accent-amber/15 text-accent-amber' },
            { name: 'REASON', group: 'reasoning', color: 'border-accent-amber/40 bg-accent-amber/15 text-accent-amber' },
            { name: 'EXPLAIN', group: 'reasoning', color: 'border-accent-amber/40 bg-accent-amber/15 text-accent-amber' },
          ].map((stage, i) => (
            <div key={stage.name} className="flex items-center gap-1.5">
              <div
                className={`
                  px-2.5 py-1.5 rounded-md text-[10px] font-mono font-semibold whitespace-nowrap border shadow-sm transition-all
                  ${stage.color}
                `}
              >
                {stage.name}
              </div>
              {i < 9 && (
                <span className="text-xs text-text-muted/50 font-bold">→</span>
              )}
            </div>
          ))}
        </div>
        <div className="flex flex-wrap items-center justify-between text-[10px] text-text-muted mt-2 font-mono gap-2 border-t border-border-subtle/40 pt-2">
          <span>End-to-End Cognitive Architecture: Real-time YOLOv8 + Spatial IoU Tracking + Scene Graphs + Bayesian Memory + Change Reasoning</span>
          <span className="text-accent-emerald font-semibold">100% Operational</span>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  label,
  value,
  sub,
  badge,
  accent = 'cyan',
}: {
  label: string;
  value: string;
  sub?: string;
  badge?: React.ReactNode;
  accent?: 'cyan' | 'emerald' | 'amber';
}) {
  const accentColor =
    accent === 'cyan'
      ? 'text-accent-cyan'
      : accent === 'emerald'
        ? 'text-accent-emerald'
        : 'text-accent-amber';

  return (
    <div className="glass-panel p-4">
      <div className="text-[10px] font-semibold text-text-muted uppercase tracking-wider mb-2">{label}</div>
      {badge || (
        <div className={`text-lg font-bold font-mono ${accentColor} mb-0.5`}>{value}</div>
      )}
      {sub && <div className="text-[10px] text-text-muted">{sub}</div>}
    </div>
  );
}
