/**
 * API client for the Cognitive Scene Memory backend.
 *
 * All API calls go through the Vite proxy (/api → localhost:8000/api)
 * so no CORS issues in development.
 */

import type {
  DetectionResult,
  HealthResponse,
  SceneResponse,
  ObjectResponse,
  MemorySummary,
  MemoryObject,
  SceneGraphResponse,
  SceneComparison,
  ChangeEvent,
  TimelineResponse,
  SettingsData,
  SettingsUpdatePayload,
  ChatQueryRequest,
  ChatQueryResponse,
} from '../types';

const BASE_URL = '/api';

/**
 * Upload an image and run YOLO object detection.
 */
export async function processImage(file: File): Promise<DetectionResult> {
  const formData = new FormData();
  formData.append('file', file);

  const response = await fetch(`${BASE_URL}/process/image`, {
    method: 'POST',
    body: formData,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * Get the most recent detection result from any source (including robot).
 */
export async function getLatestDetection(): Promise<DetectionResult | null> {
  const response = await fetch(`${BASE_URL}/detection/latest`);
  if (!response.ok) return null;
  return response.json();
}


/**
 * Get system health status.
 */
export async function getHealth(): Promise<HealthResponse> {
  const response = await fetch(`${BASE_URL}/health`);
  if (!response.ok) throw new Error(`Health check failed: ${response.status}`);
  return response.json();
}

/**
 * List all captured scenes.
 */
export async function getScenes(limit = 50, offset = 0): Promise<SceneResponse[]> {
  const response = await fetch(`${BASE_URL}/scenes?limit=${limit}&offset=${offset}`);
  if (!response.ok) throw new Error(`Failed to fetch scenes: ${response.status}`);
  return response.json();
}

/**
 * Get a specific scene by ID.
 */
export async function getScene(sceneId: string): Promise<SceneResponse> {
  const response = await fetch(`${BASE_URL}/scenes/${sceneId}`);
  if (!response.ok) throw new Error(`Scene not found: ${sceneId}`);
  return response.json();
}

/**
 * List all persistent objects in memory.
 */
export async function getObjects(
  filters?: { status?: string; class_name?: string; limit?: number }
): Promise<ObjectResponse[]> {
  const params = new URLSearchParams();
  if (filters?.status) params.set('status', filters.status);
  if (filters?.class_name) params.set('class_name', filters.class_name);
  if (filters?.limit) params.set('limit', String(filters.limit));

  const response = await fetch(`${BASE_URL}/objects?${params}`);
  if (!response.ok) throw new Error(`Failed to fetch objects: ${response.status}`);
  return response.json();
}

/**
 * Get a specific object by persistent ID.
 */
export async function getObject(objectId: string): Promise<ObjectResponse> {
  const response = await fetch(`${BASE_URL}/objects/${objectId}`);
  if (!response.ok) throw new Error(`Object not found: ${objectId}`);
  return response.json();
}


// ── Phase 4-7: Memory, Scene Graph, Changes ──────────────────────

/**
 * Get cognitive memory summary (status counts, avg confidence).
 */
export async function getMemorySummary(): Promise<MemorySummary> {
  const response = await fetch(`${BASE_URL}/memory/summary`);
  if (!response.ok) throw new Error(`Failed to fetch memory summary: ${response.status}`);
  return response.json();
}

/**
 * Get all objects with confidence and lifecycle state.
 */
export async function getMemoryObjects(): Promise<MemoryObject[]> {
  const response = await fetch(`${BASE_URL}/memory/objects`);
  if (!response.ok) throw new Error(`Failed to fetch memory objects: ${response.status}`);
  return response.json();
}

/**
 * Manually trigger confidence decay cycle.
 */
export async function triggerDecay(): Promise<{ message: string; decayed: number; transitions: Record<string, number> }> {
  const response = await fetch(`${BASE_URL}/memory/decay`, { method: 'POST' });
  if (!response.ok) throw new Error(`Failed to trigger decay: ${response.status}`);
  return response.json();
}

/**
 * Clear all persistent cognitive memory and scene records.
 */
export async function clearMemory(): Promise<{ message: string; cleared: Record<string, number> }> {
  const response = await fetch(`${BASE_URL}/memory/clear`, { method: 'POST' });
  if (!response.ok) throw new Error(`Failed to clear memory: ${response.status}`);
  return response.json();
}

/**
 * Get the scene graph for a specific scene.
 */
export async function getSceneGraph(sceneId: string): Promise<SceneGraphResponse> {
  const response = await fetch(`${BASE_URL}/scene-graph/${sceneId}`);
  if (!response.ok) throw new Error(`Failed to fetch scene graph: ${response.status}`);
  return response.json();
}

/**
 * Rebuild the scene graph for a scene.
 */
export async function buildSceneGraph(sceneId: string): Promise<SceneGraphResponse> {
  const response = await fetch(`${BASE_URL}/scene-graph/${sceneId}/build`, { method: 'POST' });
  if (!response.ok) throw new Error(`Failed to build scene graph: ${response.status}`);
  return response.json();
}

/**
 * Compare two scenes for changes.
 */
export async function compareScenes(sceneBeforeId: string, sceneAfterId: string): Promise<SceneComparison> {
  const response = await fetch(`${BASE_URL}/changes/compare`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scene_before_id: sceneBeforeId, scene_after_id: sceneAfterId }),
  });
  if (!response.ok) throw new Error(`Failed to compare scenes: ${response.status}`);
  return response.json();
}

/**
 * Get recent change events.
 */
export async function getRecentChanges(limit = 50): Promise<ChangeEvent[]> {
  const response = await fetch(`${BASE_URL}/changes/recent?limit=${limit}`);
  if (!response.ok) throw new Error(`Failed to fetch changes: ${response.status}`);
  return response.json();
}

/**
 * Get changes involving a specific scene.
 */
export async function getChangesForScene(sceneId: string): Promise<ChangeEvent[]> {
  const response = await fetch(`${BASE_URL}/changes/scene/${sceneId}`);
  if (!response.ok) throw new Error(`Failed to fetch scene changes: ${response.status}`);
  return response.json();
}

/**
 * Get change history for a specific object.
 */
export async function getChangesForObject(objectId: string): Promise<ChangeEvent[]> {
  const response = await fetch(`${BASE_URL}/changes/object/${objectId}`);
  if (!response.ok) throw new Error(`Failed to fetch object changes: ${response.status}`);
  return response.json();
}

/**
 * Get unified chronological event timeline.
 */
export async function getTimeline(limit = 50, offset = 0, eventType?: string): Promise<TimelineResponse> {
  const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (eventType) params.set('event_type', eventType);

  const response = await fetch(`${BASE_URL}/timeline?${params}`);
  if (!response.ok) throw new Error(`Failed to fetch timeline: ${response.status}`);
  return response.json();
}

/**
 * Get current system settings and thresholds.
 */
export async function getSettings(): Promise<SettingsData> {
  const response = await fetch(`${BASE_URL}/settings`);
  if (!response.ok) throw new Error(`Failed to fetch settings: ${response.status}`);
  return response.json();
}

/**
 * Update runtime system settings.
 */
export async function updateSettings(payload: SettingsUpdatePayload): Promise<SettingsData> {
  const response = await fetch(`${BASE_URL}/settings`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!response.ok) throw new Error(`Failed to update settings: ${response.status}`);
  return response.json();
}

/**
 * Ask the Cognitive Scene Memory Chatbot a question.
 */
export async function askChatbot(request: ChatQueryRequest): Promise<ChatQueryResponse> {
  const response = await fetch(`${BASE_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  });
  if (!response.ok) throw new Error(`Chatbot query failed: ${response.status}`);
  return response.json();
}


