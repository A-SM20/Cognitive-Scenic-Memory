import React, { useState, useEffect } from 'react';
import { getTimeline } from '../services/api';
import type { TimelineEvent } from '../types';

export default function Timeline() {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterType, setFilterType] = useState<string>('all');
  const [selectedEvent, setSelectedEvent] = useState<TimelineEvent | null>(null);

  const fetchEvents = async () => {
    setLoading(true);
    setError(null);
    try {
      const typeParam = filterType === 'all' ? undefined : filterType;
      const res = await getTimeline(100, 0, typeParam);
      setEvents(res.events);
      if (res.events.length > 0 && !selectedEvent) {
        setSelectedEvent(res.events[0]);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch timeline');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
  }, [filterType]);

  const getEventBadge = (type: string) => {
    if (type.includes('ADDED')) {
      return { label: 'ADDED', bg: 'bg-status-active/10 text-status-active border-status-active/30' };
    }
    if (type.includes('REMOVED')) {
      return { label: 'REMOVED', bg: 'bg-status-danger/10 text-status-danger border-status-danger/30' };
    }
    if (type.includes('MOVED')) {
      return { label: 'MOVED', bg: 'bg-status-warning/10 text-status-warning border-status-warning/30' };
    }
    return { label: 'SCENE', bg: 'bg-accent-cyan/10 text-accent-cyan border-accent-cyan/30' };
  };

  return (
    <div className="space-y-6 animate-slide-up">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-4 border-b border-border pb-4">
        <div>
          <h2 className="text-xl font-bold text-text-primary flex items-center gap-2">
            <span>Environment Timeline</span>
            <span className="text-xs px-2.5 py-0.5 rounded-full bg-accent-cyan/10 text-accent-cyan font-mono border border-accent-cyan/20">
              {events.length} Events
            </span>
          </h2>
          <p className="text-xs text-text-muted mt-1">
            Chronological history of robot room observations, detected scene changes, and object movements
          </p>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap items-center gap-1.5 bg-bg-card p-1 rounded-lg border border-border text-xs">
          {['all', 'SCENE', 'ADDED', 'MOVED', 'REMOVED'].map((type) => (
            <button
              key={type}
              onClick={() => setFilterType(type)}
              className={`px-3 py-1 rounded font-medium transition ${
                filterType === type
                  ? 'bg-accent-cyan text-bg-primary'
                  : 'text-text-muted hover:text-text-primary'
              }`}
            >
              {type.toUpperCase()}
            </button>
          ))}
          <button
            onClick={fetchEvents}
            className="p-1 px-2 text-text-muted hover:text-accent-cyan transition ml-1"
            title="Refresh"
          >
            ↻
          </button>
        </div>
      </div>

      {error && (
        <div className="glass-panel p-4 border-status-danger/30 text-status-danger text-sm">
          {error}
        </div>
      )}

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="w-6 h-6 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
        </div>
      ) : events.length === 0 ? (
        <div className="glass-panel p-12 text-center text-text-muted">
          <div className="text-3xl mb-2">⏱</div>
          <p className="text-sm font-medium">No timeline events recorded yet</p>
          <p className="text-xs mt-1">
            Run a robot 4-direction room scan or upload an image to populate the timeline.
          </p>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Timeline Feed (Left 2 cols) */}
          <div className="lg:col-span-2 space-y-3">
            {events.map((ev) => {
              const badge = getEventBadge(ev.event_type);
              const isSelected = selectedEvent?.id === ev.id;
              const formattedTime = new Date(ev.timestamp).toLocaleString();

              return (
                <div
                  key={ev.id}
                  onClick={() => setSelectedEvent(ev)}
                  className={`glass-panel p-4 cursor-pointer transition flex items-start gap-3.5 rounded-xl border ${
                    isSelected
                      ? 'border-accent-cyan bg-accent-cyan/5 shadow-md'
                      : 'border-border hover:border-border-hover'
                  }`}
                >
                  {/* Left Icon Dot */}
                  <div className="mt-1 flex flex-col items-center">
                    <span className={`w-3 h-3 rounded-full border-2 ${
                      badge.label === 'ADDED' ? 'border-status-active bg-status-active/40' :
                      badge.label === 'MOVED' ? 'border-status-warning bg-status-warning/40' :
                      badge.label === 'REMOVED' ? 'border-status-danger bg-status-danger/40' :
                      'border-accent-cyan bg-accent-cyan/40'
                    }`} />
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between gap-2 mb-1">
                      <div className="flex items-center gap-2">
                        <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded border ${badge.bg}`}>
                          {badge.label}
                        </span>
                        <h4 className="text-sm font-semibold text-text-primary truncate">{ev.title}</h4>
                      </div>
                      <span className="text-[11px] text-text-muted font-mono shrink-0">{formattedTime}</span>
                    </div>

                    <p className="text-xs text-text-secondary line-clamp-2">{ev.description}</p>

                    {/* Metadata chips */}
                    <div className="flex flex-wrap gap-2 mt-2 text-[10px] text-text-muted font-mono">
                      {ev.scene_id && (
                        <span className="px-1.5 py-0.5 rounded bg-bg-secondary border border-border">
                          {ev.scene_id}
                        </span>
                      )}
                      {ev.object_id && (
                        <span className="px-1.5 py-0.5 rounded bg-bg-secondary border border-border">
                          Obj: {ev.object_id}
                        </span>
                      )}
                      {ev.metadata?.magnitude && (
                        <span className="px-1.5 py-0.5 rounded bg-status-warning/10 text-status-warning border border-status-warning/20">
                          Δ {Number(ev.metadata.magnitude).toFixed(1)}px
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Event Inspector / Detail Card (Right 1 col) */}
          <div className="glass-panel p-5 rounded-xl h-fit sticky top-6 space-y-4">
            <h3 className="text-sm font-bold text-text-primary border-b border-border pb-2">
              Event Inspector
            </h3>

            {selectedEvent ? (
              <div className="space-y-3 text-xs">
                <div>
                  <span className="text-text-muted uppercase text-[10px] font-semibold">Title</span>
                  <p className="font-semibold text-text-primary text-sm mt-0.5">{selectedEvent.title}</p>
                </div>

                <div>
                  <span className="text-text-muted uppercase text-[10px] font-semibold">Timestamp</span>
                  <p className="font-mono text-text-secondary mt-0.5">
                    {new Date(selectedEvent.timestamp).toLocaleString()}
                  </p>
                </div>

                <div>
                  <span className="text-text-muted uppercase text-[10px] font-semibold">Description</span>
                  <p className="text-text-secondary mt-0.5 leading-relaxed">{selectedEvent.description}</p>
                </div>

                {selectedEvent.image_url && (
                  <div>
                    <span className="text-text-muted uppercase text-[10px] font-semibold">Scene Image</span>
                    <div className="mt-1.5 rounded-lg overflow-hidden border border-border bg-bg-secondary aspect-video relative">
                      <img
                        src={selectedEvent.image_url}
                        alt="Event Scene"
                        className="w-full h-full object-cover"
                      />
                    </div>
                  </div>
                )}

                {selectedEvent.metadata && Object.keys(selectedEvent.metadata).length > 0 && (
                  <div>
                    <span className="text-text-muted uppercase text-[10px] font-semibold">Metadata</span>
                    <pre className="mt-1 p-2 rounded bg-bg-secondary border border-border text-[11px] font-mono text-accent-cyan overflow-x-auto">
                      {JSON.stringify(selectedEvent.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-xs text-text-muted">Select an event from the timeline to view details.</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
