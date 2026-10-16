/**
 * TypeScript interfaces for the Cognitive Scene Memory API.
 *
 * These mirror the backend Pydantic schemas and define
 * the contract between frontend and backend.
 */

export interface BoundingBox {
  x: number;
  y: number;
  w: number;
  h: number;
}

export interface Detection {
  class_name: string;
  confidence: number;
  bbox: BoundingBox;
  center_x: number;
  center_y: number;
  width: number;
  height: number;
  timestamp: string;
  frame_id: number;
  track_id?: number;
}

export interface DetectionResult {
  scene_id: string;
  image_path: string;
  annotated_image_path: string;
  annotated_image_url: string;
  detections: Detection[];
  total_objects: number;
  processing_time_ms: number;
  model_name: string;
  image_width: number;
  image_height: number;
  timestamp: string;
}

export interface SceneResponse {
  scene_id: string;
  timestamp: string;
  environment_id: string;
  image_path: string | null;
  annotated_image_path: string | null;
  object_count: number;
  processing_time_ms: number | null;
  created_at: string;
}

export interface ObjectResponse {
  object_id: string;
  class_name: string;
  display_name: string | null;
  first_seen: string;
  last_seen: string;
  last_position_x: number | null;
  last_position_y: number | null;
  observation_count: number;
  current_confidence: number;
  identity_confidence: number;
  status: string;
}

export interface HealthResponse {
  status: string;
  project_name: string;
  version: string;
  model_name: string;
  model_loaded: boolean;
  database_connected: boolean;
  features: Record<string, boolean>;
  timestamp: string;
}

export interface QueryRequest {
  query: string;
}

export interface QueryResponse {
  query: string;
  answer: string;
  confidence: number;
  supporting_evidence: string[];
  timestamp: string;
}

/** Navigation page identifiers */
export type PageId =
  | 'overview'
  | 'perception'
  | 'memory'
  | 'scene-graph'
  | 'changes'
  | 'timeline'
  | 'query'
  | 'settings';


// ── Phase 4-7 Types ──────────────────────────────────────────────

export interface SpatialRelationship {
  source_object_id: string;
  target_object_id: string;
  source_class: string | null;
  target_class: string | null;
  relationship_type: string;
  confidence: number;
  distance_px: number | null;
}

export interface SceneGraphNode {
  object_id: string;
  class_name: string;
  display_name: string | null;
  center_x: number;
  center_y: number;
  bbox_x: number;
  bbox_y: number;
  bbox_w: number;
  bbox_h: number;
  confidence: number;
  status: string;
}

export interface SceneGraphResponse {
  scene_id: string;
  node_count: number;
  edge_count: number;
  nodes: SceneGraphNode[];
  edges: SpatialRelationship[];
  timestamp: string;
}

export interface ChangeEvent {
  id: number;
  scene_before_id: string;
  scene_after_id: string;
  object_id: string | null;
  change_type: string;
  description: string;
  magnitude: number | null;
  old_value_json: string | null;
  new_value_json: string | null;
  created_at: string;
}

export interface SceneComparison {
  scene_before_id: string;
  scene_after_id: string;
  total_changes: number;
  changes: ChangeEvent[];
  summary: Record<string, number>;
  timestamp: string;
}

export interface MemoryObject {
  object_id: string;
  class_name: string;
  display_name: string | null;
  first_seen: string;
  last_seen: string;
  last_position_x: number | null;
  last_position_y: number | null;
  observation_count: number;
  current_confidence: number;
  identity_confidence: number;
  status: string;
  scenes_since_last_seen: number;
}

export interface MemorySummary {
  total_objects: number;
  active: number;
  possibly_missing: number;
  missing: number;
  removed: number;
  unknown: number;
  total_scenes: number;
  average_confidence: number;
  timestamp: string;
}

// ── Timeline Types ────────────────────────────────────────────────

export interface TimelineEvent {
  id: string;
  event_type: string;
  title: string;
  description: string;
  timestamp: string;
  scene_id?: string | null;
  object_id?: string | null;
  image_url?: string | null;
  metadata?: Record<string, any> | null;
}

export interface TimelineResponse {
  total_events: number;
  events: TimelineEvent[];
}

// ── Settings Types ────────────────────────────────────────────────

export interface SettingsData {
  project_name: string;
  project_version: string;
  model_name: string;
  confidence_threshold: number;
  iou_threshold: number;
  process_every_n_frames: number;
  confidence_decay: number;
  movement_threshold: number;
  enable_segmentation: boolean;
  enable_feature_matching: boolean;
  enable_depth: boolean;
  enable_llm: boolean;
  database_url: string;
  upload_dir: string;
}

export interface SettingsUpdatePayload {
  confidence_threshold?: number;
  iou_threshold?: number;
  confidence_decay?: number;
  movement_threshold?: number;
  enable_segmentation?: boolean;
  enable_feature_matching?: boolean;
  enable_depth?: boolean;
  enable_llm?: boolean;
}

// ── Chatbot / Query Types ─────────────────────────────────────────

export interface ChatQueryRequest {
  query: string;
  scene_id?: string | null;
  scene_before_id?: string | null;
  scene_after_id?: string | null;
}

export interface ChatQueryResponse {
  query: string;
  answer: string;
  confidence: number;
  supporting_evidence: string[];
  context?: Record<string, any> | null;
  timestamp: string;
}


