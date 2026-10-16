import React, { useState, useEffect } from 'react';
import { getSettings, updateSettings, clearMemory } from '../services/api';
import type { SettingsData } from '../types';

export default function Settings() {
  const [settings, setSettings] = useState<SettingsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);

  // Form states
  const [confidenceThreshold, setConfidenceThreshold] = useState(0.4);
  const [iouThreshold, setIouThreshold] = useState(0.5);
  const [confidenceDecay, setConfidenceDecay] = useState(0.15);
  const [movementThreshold, setMovementThreshold] = useState(50.0);
  const [enableFeatureMatching, setEnableFeatureMatching] = useState(true);
  const [enableDepth, setEnableDepth] = useState(false);
  const [enableSegmentation, setEnableSegmentation] = useState(false);
  const [enableLlm, setEnableLlm] = useState(false);

  useEffect(() => {
    async function fetchSettings() {
      try {
        const data = await getSettings();
        setSettings(data);
        setConfidenceThreshold(data.confidence_threshold);
        setIouThreshold(data.iou_threshold);
        setConfidenceDecay(data.confidence_decay);
        setMovementThreshold(data.movement_threshold);
        setEnableFeatureMatching(data.enable_feature_matching);
        setEnableDepth(data.enable_depth);
        setEnableSegmentation(data.enable_segmentation);
        setEnableLlm(data.enable_llm);
      } catch (err) {
        console.error('Failed to load settings:', err);
      } finally {
        setLoading(false);
      }
    }
    fetchSettings();
  }, []);

  const handleSave = async () => {
    setSaving(true);
    try {
      const updated = await updateSettings({
        confidence_threshold: confidenceThreshold,
        iou_threshold: iouThreshold,
        confidence_decay: confidenceDecay,
        movement_threshold: movementThreshold,
        enable_feature_matching: enableFeatureMatching,
        enable_depth: enableDepth,
        enable_segmentation: enableSegmentation,
        enable_llm: enableLlm,
      });
      setSettings(updated);
      showToast('Settings saved and applied successfully!');
    } catch (err) {
      showToast('Error saving settings: ' + (err instanceof Error ? err.message : 'Unknown error'));
    } finally {
      setSaving(false);
    }
  };

  const handleClearMemory = async () => {
    if (!window.confirm('Are you sure you want to clear all persistent cognitive memory? Scenes and object tracks will be reset.')) {
      return;
    }
    try {
      await clearMemory();
      showToast('Cognitive scene memory successfully reset.');
    } catch (err) {
      showToast('Failed to reset memory.');
    }
  };

  const showToast = (msg: string) => {
    setToast(msg);
    setTimeout(() => setToast(null), 3500);
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="w-6 h-6 border-2 border-accent-cyan/30 border-t-accent-cyan rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-4xl animate-slide-up">
      {/* Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 right-6 z-50 px-4 py-3 rounded-xl bg-accent-cyan text-bg-primary font-semibold text-xs shadow-2xl flex items-center gap-2">
          <span>✓</span>
          <span>{toast}</span>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between border-b border-border pb-4">
        <div>
          <h2 className="text-xl font-bold text-text-primary">System & Algorithm Settings</h2>
          <p className="text-xs text-text-muted mt-1">
            Tune detection sensitivity, cognitive confidence decay, and runtime feature flags
          </p>
        </div>
        <button
          onClick={handleSave}
          disabled={saving}
          className="px-5 py-2 rounded-lg bg-accent-cyan hover:bg-accent-cyan/90 disabled:opacity-50 text-bg-primary font-semibold text-xs shadow transition flex items-center gap-1.5"
        >
          {saving ? 'Saving...' : 'Apply Changes'}
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Card 1: Perception & Detection */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="border-b border-border pb-2">
            <h3 className="text-sm font-bold text-text-primary">Perception & YOLO Engine</h3>
            <p className="text-[11px] text-text-muted">Inference thresholds for bounding box detection</p>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-text-secondary">Confidence Threshold</span>
                <span className="font-mono text-accent-cyan font-bold">{(confidenceThreshold * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.05"
                value={confidenceThreshold}
                onChange={(e) => setConfidenceThreshold(parseFloat(e.target.value))}
                className="w-full accent-accent-cyan"
              />
              <span className="text-[10px] text-text-muted">Lower values detect more objects; higher values reduce false positives.</span>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-text-secondary">NMS IOU Threshold</span>
                <span className="font-mono text-accent-cyan font-bold">{iouThreshold.toFixed(2)}</span>
              </div>
              <input
                type="range"
                min="0.1"
                max="0.9"
                step="0.05"
                value={iouThreshold}
                onChange={(e) => setIouThreshold(parseFloat(e.target.value))}
                className="w-full accent-accent-cyan"
              />
              <span className="text-[10px] text-text-muted">Overlap threshold for duplicate bounding box suppression.</span>
            </div>

            <div className="pt-2 text-xs">
              <span className="text-text-muted text-[11px]">Model Architecture:</span>
              <p className="font-mono text-text-primary text-xs mt-0.5">{settings?.model_name || 'yolov8n.pt'}</p>
            </div>
          </div>
        </div>

        {/* Card 2: Cognitive Memory & Change Detection */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="border-b border-border pb-2">
            <h3 className="text-sm font-bold text-text-primary">Cognitive Memory & Decay</h3>
            <p className="text-[11px] text-text-muted">Bayesian belief update and spatial movement thresholds</p>
          </div>

          <div className="space-y-3">
            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-text-secondary">Missed-Observation Decay (λ)</span>
                <span className="font-mono text-accent-cyan font-bold">{(confidenceDecay * 100).toFixed(0)}%</span>
              </div>
              <input
                type="range"
                min="0.02"
                max="0.40"
                step="0.01"
                value={confidenceDecay}
                onChange={(e) => setConfidenceDecay(parseFloat(e.target.value))}
                className="w-full accent-accent-cyan"
              />
              <span className="text-[10px] text-text-muted">Confidence reduction applied when an object is not observed in a scan.</span>
            </div>

            <div>
              <div className="flex justify-between text-xs mb-1">
                <span className="text-text-secondary">Movement Threshold (Pixels)</span>
                <span className="font-mono text-accent-cyan font-bold">{movementThreshold.toFixed(0)} px</span>
              </div>
              <input
                type="range"
                min="15"
                max="200"
                step="5"
                value={movementThreshold}
                onChange={(e) => setMovementThreshold(parseFloat(e.target.value))}
                className="w-full accent-accent-cyan"
              />
              <span className="text-[10px] text-text-muted">Minimum center-point displacement to classify an object as MOVED.</span>
            </div>
          </div>
        </div>

        {/* Card 3: Feature Flags */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="border-b border-border pb-2">
            <h3 className="text-sm font-bold text-text-primary">Feature Toggles</h3>
            <p className="text-[11px] text-text-muted">Enable or disable experimental processing modules</p>
          </div>

          <div className="space-y-3 text-xs">
            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-text-secondary">ORB / SIFT Feature Matching</span>
              <input
                type="checkbox"
                checked={enableFeatureMatching}
                onChange={(e) => setEnableFeatureMatching(e.target.checked)}
                className="accent-accent-cyan w-4 h-4 rounded cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-text-secondary">Depth / 3D Positioning</span>
              <input
                type="checkbox"
                checked={enableDepth}
                onChange={(e) => setEnableDepth(e.target.checked)}
                className="accent-accent-cyan w-4 h-4 rounded cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-text-secondary">Semantic Segmentation</span>
              <input
                type="checkbox"
                checked={enableSegmentation}
                onChange={(e) => setEnableSegmentation(e.target.checked)}
                className="accent-accent-cyan w-4 h-4 rounded cursor-pointer"
              />
            </label>

            <label className="flex items-center justify-between cursor-pointer">
              <span className="text-text-secondary">LLM Enhanced Responses</span>
              <input
                type="checkbox"
                checked={enableLlm}
                onChange={(e) => setEnableLlm(e.target.checked)}
                className="accent-accent-cyan w-4 h-4 rounded cursor-pointer"
              />
            </label>
          </div>
        </div>

        {/* Card 4: Database & Maintenance */}
        <div className="glass-panel p-5 rounded-xl space-y-4">
          <div className="border-b border-border pb-2">
            <h3 className="text-sm font-bold text-text-primary">Storage & Memory Reset</h3>
            <p className="text-[11px] text-text-muted">Data paths and memory management</p>
          </div>

          <div className="space-y-2 text-xs">
            <div>
              <span className="text-[10px] text-text-muted uppercase">SQLite Database</span>
              <p className="font-mono text-text-secondary text-[11px] truncate">{settings?.database_url}</p>
            </div>

            <div>
              <span className="text-[10px] text-text-muted uppercase">Uploads Directory</span>
              <p className="font-mono text-text-secondary text-[11px] truncate">{settings?.upload_dir}</p>
            </div>

            <div className="pt-2">
              <button
                onClick={handleClearMemory}
                className="w-full py-2 rounded-lg bg-status-danger/10 hover:bg-status-danger/20 text-status-danger border border-status-danger/30 text-xs font-semibold transition"
              >
                Clear Cognitive Memory & Scenes
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
