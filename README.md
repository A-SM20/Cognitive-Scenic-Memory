# Cognitive Scene Memory

**Semantic World Modeling and Long-Term Environment Change Detection for Indoor Robots**

A persistent semantic world model that combines real object perception, object identity, spatial relationships, confidence-aware temporal memory, environmental change detection, and evidence-based natural-language interaction.

---

## Architecture

```
SENSE → DETECT → TRACK → IDENTIFY → LOCALIZE → UNDERSTAND → REMEMBER → COMPARE → REASON → EXPLAIN
```

### Perception Pipeline

```
Image/Video/Webcam
      ↓
  YOLO Detection (real inference)
      ↓
  Structured Detections
      ↓
  Database Persistence
      ↓
  Annotated Visualization
```

### System Architecture

```
React Frontend (Vite + TypeScript + Tailwind CSS)
      ↓
  FastAPI Backend (Python 3.11+)
      ↓
    Service Layer
      ↓
  Perception (YOLO) + Memory + Reasoning
      ↓
    SQLAlchemy (Async)
      ↓
      SQLite
```

## Implementation Status: All Core Phases Fully Operational ✅

### Phase 1 — Foundation & Neural Perception ✅
- ✅ Project skeleton and monorepo structure
- ✅ FastAPI backend with async SQLAlchemy & SQLite
- ✅ React + TypeScript + Vite frontend with Tailwind CSS dark robotics theme
- ✅ Centralized configuration system (`.env` / environment variables)
- ✅ Structured logging with timestamps
- ✅ Real-time YOLOv8 object detection (no mock data)
- ✅ Annotated image generation with color-coded bounding boxes and labels
- ✅ Camera/input source abstraction (Image, Video, Live Webcam)
- ✅ Detection API endpoints (`POST /api/process/image`, `GET /api/health`, `/api/detection/latest`)

### Phase 2 — Cognitive Scene Memory & Spatial Graphs ✅
- ✅ **Persistent Scene Snapshots** — multi-scene storage in SQLite database
- ✅ **Cognitive Confidence Model** — Bayesian decay and observation reinforcement
- ✅ **Object Lifecycle Management** — `ACTIVE` → `POSSIBLY_MISSING` → `MISSING` → `REMOVED`
- ✅ **Semantic Scene Graph** — NetworkX-based spatial relationship reasoning
- ✅ Spatial relationships: `ON`, `UNDER`, `LEFT_OF`, `RIGHT_OF`, `NEAR`, `CONTAINS`, `INSIDE`, `ABOVE`, `BELOW`, `ADJACENT`
- ✅ **Change Detection Engine** — detects `ADDED`, `REMOVED`, `MOVED`, `REPLACED`, `CONFIDENCE_CHANGED`
- ✅ Human-readable change descriptions with magnitude quantification
- ✅ Memory API endpoints (`/api/memory/summary`, `/api/memory/objects`, `/api/memory/decay`)
- ✅ Scene Graph API endpoints (`/api/scene-graph/{scene_id}`, `/api/scene-graph/{scene_id}/build`)
- ✅ Change Detection API endpoints (`/api/changes/compare`, `/api/changes/recent`)

### Phase 3 — Object Tracking & Persistent Identity ✅
- ✅ Spatial IoU matching and Hungarian assignment algorithm across frames
- ✅ Persistent object identity tracking across multiple room viewpoints
- ✅ Spatial center tracking and drift quantification

### Phase 4 — Temporal Reasoning & Timeline ✅
- ✅ Chronological event stream tracking object appearances, movements, and state changes
- ✅ Timeline API endpoints (`/api/timeline/events`, `/api/timeline/scene/{scene_id}`)
- ✅ Interactive visual timeline with category filters and event summaries

### Phase 5 — Natural Language Spatial Query Engine ✅
- ✅ Query engine answering spatial and semantic queries (e.g., *"Where is the bottle?"*, *"What changed?"*, *"What is near the chair?"*)
- ✅ Natural language query API endpoint (`POST /api/query`)
- ✅ Interactive Query console in the web dashboard

### Phase 6 — Visualization & Robot Control Dashboard ✅
- ✅ **Overview Dashboard**: Live system health, active objects count, live robot auto-sync, 10-stage perception pipeline
- ✅ **Perception Dashboard**: Drag-and-drop image upload, live annotated bounding boxes, detection metrics
- ✅ **Memory Dashboard**: Cognitive confidence bars, lifecycle filters, observation history
- ✅ **Scene Graph Visualizer**: Interactive canvas force-directed graph with spatial edges
- ✅ **Changes Dashboard**: Side-by-side scene comparison and classified change cards
- ✅ **Timeline View**: Chronological audit trail of environmental changes
- ✅ **Query Console**: Natural language spatial search
- ✅ **Settings View**: Detection thresholds, IoU overlap, model selection, memory decay rates

### Phase 7 — Raspberry Pi 5 Hardware & Robotics Integration ✅
- ✅ Raspberry Pi 5 (RP1 GPIO & CSI camera architecture)
- ✅ Pi Camera Module with auto 90° rotation and warm-up capture
- ✅ L298N Dual H-Bridge 4WD motor controller (4-pin and 6-pin PWM modes)
- ✅ MG90S metal-gear servo camera mount with auto-detaching PWM anti-jitter
- ✅ JHD162A 16×2 Character LCD in 4-bit write-only safe mode
- ✅ Interactive teleoperation & scanner (`teleop_drive.py` with WASD + camera pan + live snapshot)
- ✅ Automated 4-direction room mapping (`robot_cognitive_agent.py`)

## Quick Start

### Prerequisites

- Python 3.11+ 
- Node.js 18+
- Internet connection (for first YOLO model download)

### Backend Setup

```bash
cd cognitive_scenic_memory

# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\activate      # Windows
# source venv/bin/activate   # Linux/Mac

# Install dependencies
pip install -r backend/requirements.txt

# Copy environment config
copy .env.example .env       # Windows
# cp .env.example .env       # Linux/Mac

# Start backend
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The YOLO model (`yolov8n.pt`, ~6MB) downloads automatically on first detection.

### Frontend Setup

```bash
cd frontend
npm install
npm install -D tailwindcss @tailwindcss/vite
npm run dev
```

### Access

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/api/health

## API Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/process/image` | Upload image for YOLO detection |
| `GET` | `/api/health` | System health and status |
| `GET` | `/api/scenes` | List all captured scenes |
| `GET` | `/api/scenes/{scene_id}` | Get specific scene |
| `GET` | `/api/objects` | List all detected objects |
| `GET` | `/api/objects/{object_id}` | Get specific object |
| `GET` | `/api/memory/summary` | Memory status breakdown |
| `GET` | `/api/memory/objects` | Objects with confidence/lifecycle |
| `POST` | `/api/memory/decay` | Trigger confidence decay |
| `GET` | `/api/scene-graph/{scene_id}` | Get scene graph |
| `POST` | `/api/scene-graph/{scene_id}/build` | Rebuild scene graph |
| `GET` | `/api/scene-graph/{scene_id}/relationships` | List spatial relationships |
| `POST` | `/api/changes/compare` | Compare two scenes |
| `GET` | `/api/changes/scene/{scene_id}` | Changes for a scene |
| `GET` | `/api/changes/object/{object_id}` | Change history for object |
| `GET` | `/api/changes/recent` | Recent change events |

## Configuration

All parameters are configurable via `.env` file or environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `MODEL_NAME` | `yolov8n.pt` | YOLO model file |
| `CONFIDENCE_THRESHOLD` | `0.40` | Minimum detection confidence |
| `IOU_THRESHOLD` | `0.50` | NMS IOU threshold |
| `PROCESS_EVERY_N_FRAMES` | `10` | Frame skip for video |
| `ENABLE_SEGMENTATION` | `false` | Semantic segmentation |
| `ENABLE_FEATURE_MATCHING` | `true` | ORB/SIFT features |
| `ENABLE_DEPTH` | `false` | 3D depth estimation |
| `ENABLE_LLM` | `false` | LLM query responses |
| `CONFIDENCE_DECAY` | `0.15` | Memory confidence decay |
| `MOVEMENT_THRESHOLD` | `50.0` | Pixel movement threshold |
| `DATABASE_URL` | `sqlite:///./data/scene_memory.db` | Database connection |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Project Structure

```
cognitive_scenic_memory/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── config.py         # Centralized configuration
│   │   ├── database.py       # Async SQLAlchemy
│   │   ├── logging_config.py # Structured logging
│   │   ├── api/              # API route modules
│   │   ├── models/           # ORM + Pydantic schemas
│   │   ├── perception/       # Detection + camera input
│   │   └── services/         # Business logic layer
│   ├── tests/                # Automated tests
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx           # Root component
│   │   ├── components/       # Reusable UI components
│   │   ├── pages/            # Page views
│   │   ├── services/         # API client
│   │   └── types/            # TypeScript interfaces
│   └── package.json
├── data/                     # Runtime data (gitignored)
├── .env.example              # Configuration template
└── README.md
```

## Testing

```bash
cd backend
..\venv\Scripts\python.exe -m pytest tests/ -v
```

## Limitations (Phase 1)

- **2D only**: Object positions are image-plane coordinates, not metric 3D.
- **No tracking**: Objects are detected per-frame without temporal tracking.
- **No identity persistence**: Each detection creates a new object ID (persistent identity comes in Phase 3).
- **No change detection**: Scene comparison requires Phase 7.
- **Pretrained model**: YOLO is pretrained on COCO; custom classes require fine-tuning.

## Technology Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, SQLAlchemy (async), Pydantic |
| Database | SQLite + aiosqlite |
| Detection | Ultralytics YOLO (YOLOv8) |
| Computer Vision | OpenCV |
| Frontend | React, TypeScript, Vite, Tailwind CSS v4 |
| Future | NetworkX, ByteTrack, ROS2 Jazzy, Open3D |

## License

Research prototype — see project documentation.
