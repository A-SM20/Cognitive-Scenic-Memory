import { useState, useEffect } from 'react';
import { getScenes, getRecentChanges, compareScenes } from '../services/api';
import type { SceneResponse, ChangeEvent, SceneComparison } from '../types';

const CHANGE_CONFIG: Record<string, { color: string; bg: string; icon: string }> = {
  ADDED: { color: 'text-accent-emerald', bg: 'bg-accent-emerald/15', icon: '+' },
  REMOVED: { color: 'text-accent-red', bg: 'bg-accent-red/15', icon: '−' },
  MOVED: { color: 'text-accent-blue', bg: 'bg-accent-blue/15', icon: '↔' },
  REPLACED: { color: 'text-accent-amber', bg: 'bg-accent-amber/15', icon: '⇄' },
  STATUS_CHANGED: { color: 'text-accent-purple', bg: 'bg-accent-purple/15', icon: '◎' },
  CONFIDENCE_CHANGED: { color: 'text-accent-cyan', bg: 'bg-accent-cyan/15', icon: '△' },
};

function ChangeBadge({ type }: { type: string }) {
  const config = CHANGE_CONFIG[type] || { color: 'text-text-muted', bg: 'bg-bg-card', icon: '?' };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-semibold ${config.color} ${config.bg}`}>
      <span className="text-sm">{config.icon}</span>
      {type.replace('_', ' ')}
    </span>
  );
}

function ChangeCard({ change }: { change: ChangeEvent }) {
  return (
    <div className="glass-panel p-4 animate-slide-up hover:border-border-focus transition-all">
      <div className="flex items-start justify-between mb-2">
        <ChangeBadge type={change.change_type} />
        <span className="text-[10px] text-text-muted font-mono">
          {new Date(change.created_at).toLocaleString()}
        </span>
      </div>
      <p className="text-sm text-text-primary mb-2">{change.description}</p>
      <div className="flex items-center gap-4 text-xs text-text-muted">
        {change.object_id && (
          <span className="font-mono">
            <span className="text-text-muted">obj:</span>{' '}
            <span className="text-accent-cyan">{change.object_id}</span>
          </span>
        )}
        {change.magnitude != null && (
          <span className="font-mono">
            <span className="text-text-muted">mag:</span>{' '}
            <span className="text-accent-amber">{change.magnitude.toFixed(1)}</span>
          </span>
        )}
        <span className="font-mono">
          {change.scene_before_id} → {change.scene_after_id}
        </span>
      </div>
    </div>
  );
}

export default function Changes() {
  const [scenes, setScenes] = useState<SceneResponse[]>([]);
  const [recentChanges, setRecentChanges] = useState<ChangeEvent[]>([]);
  const [loading, setLoading] = useState(true);

  // Comparison tool state
  const [beforeId, setBeforeId] = useState('');
  const [afterId, setAfterId] = useState('');
  const [comparison, setComparison] = useState<SceneComparison | null>(null);
  const [comparing, setComparing] = useState(false);

  const [activeTab, setActiveTab] = useState<'recent' | 'compare'>('recent');

  useEffect(() => {
    Promise.all([getScenes(30), getRecentChanges(30)])
      .then(([s, c]) => {
        setScenes(s);
        setRecentChanges(c);
        if (s.length >= 2) {
          setBeforeId(s[1].scene_id);
          setAfterId(s[0].scene_id);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleCompare = async () => {
    if (!beforeId || !afterId || beforeId === afterId) return;
    setComparing(true);
    try {
      const result = await compareScenes(beforeId, afterId);
      setComparison(result);
    } catch (err) {
      console.error('Comparison failed:', err);
    } finally {
      setComparing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-text-muted animate-pulse">Loading change data...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-xl font-bold text-text-primary">Change Detection</h2>
        <p className="text-sm text-text-muted mt-0.5">
          Environment changes detected between scenes
        </p>
      </div>

      {/* Tab Bar */}
      <div className="flex items-center gap-1 p-1 bg-bg-secondary rounded-lg border border-border w-fit">
        {(['recent', 'compare'] as const).map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-1.5 rounded-md text-sm font-medium transition-all
              ${activeTab === tab
                ? 'bg-accent-cyan/15 text-accent-cyan'
                : 'text-text-muted hover:text-text-secondary'
              }`}
          >
            {tab === 'recent' ? '⏱ Recent Changes' : '⟷ Compare Scenes'}
          </button>
        ))}
      </div>

      {/* ── Recent Changes Tab ── */}
      {activeTab === 'recent' && (
        <div className="space-y-4">
          {/* Summary stats */}
          {recentChanges.length > 0 && (
            <div className="flex items-center gap-3 flex-wrap">
              {Object.entries(
                recentChanges.reduce((acc, c) => {
                  acc[c.change_type] = (acc[c.change_type] || 0) + 1;
                  return acc;
                }, {} as Record<string, number>)
              ).sort((a, b) => b[1] - a[1]).map(([type, count]) => {
                const config = CHANGE_CONFIG[type] || { color: 'text-text-muted', bg: 'bg-bg-card', icon: '?' };
                return (
                  <div
                    key={type}
                    className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-border text-xs ${config.color}`}
                  >
                    <span className="font-bold text-sm">{config.icon}</span>
                    <span>{type.replace('_', ' ')}</span>
                    <span className="font-mono font-bold">{count}</span>
                  </div>
                );
              })}
            </div>
          )}

          {/* Change cards */}
          <div className="space-y-3">
            {recentChanges.map(change => (
              <ChangeCard key={change.id} change={change} />
            ))}
            {recentChanges.length === 0 && (
              <div className="glass-panel p-8 text-center text-text-muted">
                <div className="text-3xl mb-2 opacity-30">△</div>
                <p>No changes detected yet.</p>
                <p className="text-xs mt-1">Upload multiple images to start detecting environment changes.</p>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Compare Scenes Tab ── */}
      {activeTab === 'compare' && (
        <div className="space-y-4">
          {/* Scene selector */}
          <div className="glass-panel p-4">
            <div className="flex items-end gap-4">
              <div className="flex-1">
                <label className="text-xs text-text-muted block mb-1">Before Scene</label>
                <select
                  value={beforeId}
                  onChange={e => setBeforeId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-bg-input border border-border text-text-primary
                             text-sm focus:border-accent-cyan outline-none"
                >
                  <option value="">Select scene...</option>
                  {scenes.map(s => (
                    <option key={s.scene_id} value={s.scene_id}>
                      {s.scene_id} ({s.object_count} objects)
                    </option>
                  ))}
                </select>
              </div>
              <div className="text-text-muted text-lg pb-2">→</div>
              <div className="flex-1">
                <label className="text-xs text-text-muted block mb-1">After Scene</label>
                <select
                  value={afterId}
                  onChange={e => setAfterId(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-bg-input border border-border text-text-primary
                             text-sm focus:border-accent-cyan outline-none"
                >
                  <option value="">Select scene...</option>
                  {scenes.map(s => (
                    <option key={s.scene_id} value={s.scene_id}>
                      {s.scene_id} ({s.object_count} objects)
                    </option>
                  ))}
                </select>
              </div>
              <button
                onClick={handleCompare}
                disabled={comparing || !beforeId || !afterId || beforeId === afterId}
                className="px-5 py-2 rounded-lg bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/25
                           hover:bg-accent-cyan/25 transition-all text-sm font-medium disabled:opacity-50"
              >
                {comparing ? 'Comparing…' : '⟷ Compare'}
              </button>
            </div>
          </div>

          {/* Comparison Results */}
          {comparison && (
            <div className="space-y-4">
              {/* Summary */}
              <div className="glass-panel p-4">
                <div className="flex items-center justify-between mb-3">
                  <h3 className="text-sm font-semibold text-text-primary">
                    Comparison Result
                  </h3>
                  <span className="text-xs text-text-muted font-mono">
                    {comparison.total_changes} total changes
                  </span>
                </div>
                <div className="flex items-center gap-3 flex-wrap">
                  {Object.entries(comparison.summary).map(([type, count]) => {
                    const config = CHANGE_CONFIG[type] || { color: 'text-text-muted', bg: 'bg-bg-card', icon: '?' };
                    return (
                      <div
                        key={type}
                        className={`flex items-center gap-1.5 px-3 py-2 rounded-lg ${config.bg} text-xs ${config.color}`}
                      >
                        <span className="text-lg font-bold">{count}</span>
                        <span>{type.replace('_', ' ')}</span>
                      </div>
                    );
                  })}
                  {comparison.total_changes === 0 && (
                    <span className="text-text-muted text-sm">No changes detected between these scenes.</span>
                  )}
                </div>
              </div>

              {/* Change details */}
              <div className="space-y-3">
                {comparison.changes.map(change => (
                  <ChangeCard key={change.id} change={change} />
                ))}
              </div>
            </div>
          )}

          {!comparison && !comparing && (
            <div className="glass-panel p-8 text-center text-text-muted">
              <div className="text-3xl mb-2 opacity-30">⟷</div>
              <p>Select two scenes and click Compare to detect changes.</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
