import { useState, useEffect, useRef, useCallback, useMemo } from 'react';
import { getScenes, getSceneGraph, buildSceneGraph } from '../services/api';
import type { SceneResponse, SceneGraphResponse, SceneGraphNode, SpatialRelationship } from '../types';

// Class colors for graph nodes
const CLASS_COLORS: Record<string, string> = {
  person: '#22d3ee',
  chair: '#a78bfa',
  laptop: '#60a5fa',
  cup: '#fbbf24',
  bottle: '#f87171',
  book: '#34d399',
  keyboard: '#818cf8',
  mouse: '#fb923c',
  cell_phone: '#e879f9',
  tv: '#2dd4bf',
  dining_table: '#94a3b8',
  couch: '#c084fc',
  bed: '#fda4af',
  potted_plant: '#86efac',
  clock: '#fdba74',
};

function getClassColor(className: string): string {
  return CLASS_COLORS[className] || '#38bdf8';
}

// Relationship label colors
const REL_COLORS: Record<string, string> = {
  ON: '#34d399',
  UNDER: '#a78bfa',
  LEFT_OF: '#60a5fa',
  RIGHT_OF: '#fbbf24',
  NEAR: '#22d3ee',
  CONTAINS: '#f87171',
  INSIDE: '#e879f9',
  ABOVE: '#2dd4bf',
  BELOW: '#fb923c',
  ADJACENT: '#94a3b8',
};

const STRUCTURAL_TYPES = new Set(['ON', 'CONTAINS', 'INSIDE', 'UNDER', 'NEAR', 'ADJACENT']);
const DIRECTIONAL_TYPES = new Set(['LEFT_OF', 'RIGHT_OF', 'ABOVE', 'BELOW']);

interface NodePosition {
  x: number;
  y: number;
  vx: number;
  vy: number;
  pinned?: boolean;
}

interface ForceGraphProps {
  nodes: SceneGraphNode[];
  edges: SpatialRelationship[];
  selectedNode: string | null;
  onSelectNode: (id: string | null) => void;
  labelMode: 'smart' | 'all' | 'none';
  spacingMultiplier: number;
}

function InteractiveForceGraph({
  nodes,
  edges,
  selectedNode,
  onSelectNode,
  labelMode,
  spacingMultiplier,
}: ForceGraphProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const positionsRef = useRef<Map<string, NodePosition>>(new Map());
  const animFrameRef = useRef<number>(0);
  const [hoveredNode, setHoveredNode] = useState<string | null>(null);

  // Pan & Zoom state
  const [zoom, setZoom] = useState(1.0);
  const [pan, setPan] = useState<{ x: number; y: number }>({ x: 0, y: 0 });
  const isDraggingRef = useRef(false);
  const dragTargetRef = useRef<'node' | 'canvas' | null>(null);
  const draggedNodeIdRef = useRef<string | null>(null);
  const lastMousePosRef = useRef<{ x: number; y: number }>({ x: 0, y: 0 });

  // Container dimensions
  const [dimensions, setDimensions] = useState<{ width: number; height: number }>({
    width: 900,
    height: 520,
  });

  useEffect(() => {
    const updateSize = () => {
      if (containerRef.current) {
        const rect = containerRef.current.getBoundingClientRect();
        setDimensions({
          width: Math.max(600, Math.floor(rect.width)),
          height: 520,
        });
      }
    };
    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
  }, []);

  const { width, height } = dimensions;

  // Pre-calculate node degrees for spring normalization
  const nodeDegrees = useMemo(() => {
    const degs: Record<string, number> = {};
    for (const edge of edges) {
      degs[edge.source_object_id] = (degs[edge.source_object_id] || 0) + 1;
      degs[edge.target_object_id] = (degs[edge.target_object_id] || 0) + 1;
    }
    return degs;
  }, [edges]);

  // Initialize or update node positions
  useEffect(() => {
    const positions = new Map<string, NodePosition>();
    const cx = width / 2;
    const cy = height / 2;
    const radius = Math.min(width, height) * 0.35 * spacingMultiplier;

    nodes.forEach((node, i) => {
      const existing = positionsRef.current.get(node.object_id);
      if (existing) {
        positions.set(node.object_id, existing);
      } else {
        const angle = (2 * Math.PI * i) / Math.max(1, nodes.length);
        positions.set(node.object_id, {
          x: cx + radius * Math.cos(angle) + (Math.random() - 0.5) * 60,
          y: cy + radius * Math.sin(angle) + (Math.random() - 0.5) * 60,
          vx: 0,
          vy: 0,
        });
      }
    });

    positionsRef.current = positions;
  }, [nodes, width, height, spacingMultiplier]);

  // Reset View
  const handleResetView = useCallback(() => {
    setZoom(1.0);
    setPan({ x: 0, y: 0 });
  }, []);

  // Physics simulation + rendering loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || nodes.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;

    let iteration = 0;
    const maxIterations = 300;

    function simulate() {
      const positions = positionsRef.current;
      const cooling = Math.max(0.015, 1 - iteration / maxIterations);
      const cx = width / 2;
      const cy = height / 2;

      const nodeList = Array.from(positions.entries());

      // 1. Repulsion between all nodes (Coulomb force) + Hard collision avoidance
      for (let i = 0; i < nodeList.length; i++) {
        for (let j = i + 1; j < nodeList.length; j++) {
          const [, a] = nodeList[i];
          const [, b] = nodeList[j];
          const dx = b.x - a.x;
          const dy = b.y - a.y;
          const dist = Math.max(0.1, Math.hypot(dx, dy));

          // Base repulsion
          const repConst = 3200 * spacingMultiplier;
          const force = (repConst * cooling) / (dist * Math.sqrt(dist));
          let fx = (dx / dist) * force;
          let fy = (dy / dist) * force;

          // Collision buffer (radius ~ 25px each)
          const minDist = 60 * spacingMultiplier;
          if (dist < minDist) {
            const push = ((minDist - dist) / minDist) * 1.5 * cooling;
            fx += (dx / dist) * push * 8;
            fy += (dy / dist) * push * 8;
          }

          if (!a.pinned) {
            a.vx -= fx;
            a.vy -= fy;
          }
          if (!b.pinned) {
            b.vx += fx;
            b.vy += fy;
          }
        }
      }

      // 2. Attraction along edges (degree-normalized springs)
      const restLength = 170 * spacingMultiplier;
      for (const edge of edges) {
        const a = positions.get(edge.source_object_id);
        const b = positions.get(edge.target_object_id);
        if (!a || !b) continue;

        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.max(0.1, Math.hypot(dx, dy));

        const degA = nodeDegrees[edge.source_object_id] || 1;
        const degB = nodeDegrees[edge.target_object_id] || 1;
        const degFactor = 1.0 / Math.sqrt(Math.max(1, degA * degB));

        const force = (dist - restLength) * 0.012 * degFactor * cooling;
        const fx = (dx / dist) * force;
        const fy = (dy / dist) * force;

        if (!a.pinned) {
          a.vx += fx;
          a.vy += fy;
        }
        if (!b.pinned) {
          b.vx -= fx;
          b.vy -= fy;
        }
      }

      // 3. Gentle center gravity
      for (const [, pos] of positions) {
        if (!pos.pinned) {
          pos.vx += (cx - pos.x) * 0.003 * cooling;
          pos.vy += (cy - pos.y) * 0.003 * cooling;
        }
      }

      // 4. Velocity integration with damping & soft boundaries
      for (const [, pos] of positions) {
        if (!pos.pinned) {
          pos.vx *= 0.82;
          pos.vy *= 0.82;
          pos.x += pos.vx;
          pos.y += pos.vy;

          // Soft boundary padding
          pos.x = Math.max(50, Math.min(width - 50, pos.x));
          pos.y = Math.max(50, Math.min(height - 50, pos.y));
        }
      }

      // ────────────────── RENDER PHASE ──────────────────
      ctx!.save();
      ctx!.scale(dpr, dpr);
      ctx!.clearRect(0, 0, width, height);

      // Apply Pan & Zoom
      ctx!.translate(pan.x, pan.y);
      ctx!.translate(width / 2, height / 2);
      ctx!.scale(zoom, zoom);
      ctx!.translate(-width / 2, -height / 2);

      // Draw subtle background grid
      ctx!.strokeStyle = 'rgba(30, 45, 69, 0.4)';
      ctx!.lineWidth = 0.5;
      const gridSize = 40;
      const startX = Math.floor((-pan.x) / gridSize) * gridSize - gridSize * 2;
      const endX = startX + width + gridSize * 4;
      const startY = Math.floor((-pan.y) / gridSize) * gridSize - gridSize * 2;
      const endY = startY + height + gridSize * 4;

      ctx!.beginPath();
      for (let gx = startX; gx < endX; gx += gridSize) {
        ctx!.moveTo(gx, startY);
        ctx!.lineTo(gx, endY);
      }
      for (let gy = startY; gy < endY; gy += gridSize) {
        ctx!.moveTo(startX, gy);
        ctx!.lineTo(endX, gy);
      }
      ctx!.stroke();

      const activeFocus = selectedNode || hoveredNode;

      // Draw Edges
      for (const edge of edges) {
        const a = positions.get(edge.source_object_id);
        const b = positions.get(edge.target_object_id);
        if (!a || !b) continue;

        const isSourceFocus = activeFocus === edge.source_object_id;
        const isTargetFocus = activeFocus === edge.target_object_id;
        const isConnected = isSourceFocus || isTargetFocus;

        const relColor = REL_COLORS[edge.relationship_type] || '#64748b';

        // Opacity styling
        let edgeOpacity = 0.35;
        let lineWidth = 1.2;

        if (activeFocus) {
          if (isConnected) {
            edgeOpacity = 1.0;
            lineWidth = 2.4;
          } else {
            edgeOpacity = 0.08;
            lineWidth = 0.6;
          }
        }

        // Draw Line with Arrow
        ctx!.beginPath();
        ctx!.moveTo(a.x, a.y);
        ctx!.lineTo(b.x, b.y);
        ctx!.strokeStyle = isConnected
          ? relColor
          : `${relColor}${Math.floor(edgeOpacity * 255).toString(16).padStart(2, '0')}`;
        ctx!.lineWidth = lineWidth;
        ctx!.stroke();

        // Directional Arrow Head
        const angle = Math.atan2(b.y - a.y, b.x - a.x);
        const arrowDist = 24; // offset from target center
        const arrowX = b.x - Math.cos(angle) * arrowDist;
        const arrowY = b.y - Math.sin(angle) * arrowDist;

        ctx!.beginPath();
        ctx!.moveTo(arrowX, arrowY);
        ctx!.lineTo(
          arrowX - 7 * Math.cos(angle - Math.PI / 6),
          arrowY - 7 * Math.sin(angle - Math.PI / 6),
        );
        ctx!.lineTo(
          arrowX - 7 * Math.cos(angle + Math.PI / 6),
          arrowY - 7 * Math.sin(angle + Math.PI / 6),
        );
        ctx!.closePath();
        ctx!.fillStyle = isConnected ? relColor : `${relColor}80`;
        ctx!.fill();

        // Draw Edge Label
        const showLabel =
          labelMode === 'all' ||
          (labelMode === 'smart' && isConnected);

        if (showLabel) {
          const mx = (a.x + b.x) / 2;
          const my = (a.y + b.y) / 2;

          ctx!.font = isConnected ? 'bold 10px Inter, sans-serif' : '9px Inter, sans-serif';
          const textWidth = ctx!.measureText(edge.relationship_type).width;

          // Label Pill Background
          ctx!.fillStyle = 'rgba(15, 23, 42, 0.9)';
          ctx!.strokeStyle = isConnected ? relColor : 'rgba(30, 45, 69, 0.8)';
          ctx!.lineWidth = isConnected ? 1.5 : 0.8;
          ctx!.beginPath();
          ctx!.roundRect(mx - textWidth / 2 - 4, my - 8, textWidth + 8, 16, 4);
          ctx!.fill();
          ctx!.stroke();

          // Label Text
          ctx!.fillStyle = isConnected ? relColor : '#cbd5e1';
          ctx!.textAlign = 'center';
          ctx!.textBaseline = 'middle';
          ctx!.fillText(edge.relationship_type, mx, my);
        }
      }

      // Draw Nodes
      const nodeMap = new Map(nodes.map(n => [n.object_id, n]));
      for (const [id, pos] of positions) {
        const node = nodeMap.get(id);
        if (!node) continue;

        const isSelected = selectedNode === id;
        const isHovered = hoveredNode === id;
        const isNeighbor =
          activeFocus &&
          edges.some(
            e =>
              (e.source_object_id === activeFocus && e.target_object_id === id) ||
              (e.target_object_id === activeFocus && e.source_object_id === id),
          );
        const isDimmed = activeFocus && !isSelected && !isHovered && !isNeighbor;

        const radius = 16 + Math.min(node.confidence * 8, 8);
        const color = getClassColor(node.class_name);

        // Node Glow Halo
        if (isSelected || isHovered) {
          ctx!.beginPath();
          ctx!.arc(pos.x, pos.y, radius + 8, 0, Math.PI * 2);
          ctx!.fillStyle = `${color}25`;
          ctx!.fill();
          ctx!.strokeStyle = `${color}80`;
          ctx!.lineWidth = 1;
          ctx!.stroke();
        }

        // Main Node Body
        ctx!.beginPath();
        ctx!.arc(pos.x, pos.y, radius, 0, Math.PI * 2);
        ctx!.fillStyle = isDimmed ? 'rgba(26, 34, 54, 0.4)' : `${color}28`;
        ctx!.fill();
        ctx!.strokeStyle = isDimmed ? 'rgba(100, 116, 139, 0.3)' : color;
        ctx!.lineWidth = isSelected ? 3 : isHovered ? 2.5 : 1.8;
        ctx!.stroke();

        // Node Inner Icon / Initial
        ctx!.font = 'bold 11px Inter, sans-serif';
        ctx!.fillStyle = isDimmed ? 'rgba(148, 163, 184, 0.4)' : '#ffffff';
        ctx!.textAlign = 'center';
        ctx!.textBaseline = 'middle';
        const symbol = node.class_name.slice(0, 2).toUpperCase();
        ctx!.fillText(symbol, pos.x, pos.y - 1);

        // Degree Badge (connections count)
        const degree = nodeDegrees[id] || 0;
        if (degree > 0) {
          const badgeX = pos.x + radius * 0.7;
          const badgeY = pos.y - radius * 0.7;
          ctx!.beginPath();
          ctx!.arc(badgeX, badgeY, 7, 0, Math.PI * 2);
          ctx!.fillStyle = '#1e293b';
          ctx!.fill();
          ctx!.strokeStyle = color;
          ctx!.lineWidth = 1;
          ctx!.stroke();

          ctx!.font = '9px JetBrains Mono, monospace';
          ctx!.fillStyle = '#e2e8f0';
          ctx!.textAlign = 'center';
          ctx!.textBaseline = 'middle';
          ctx!.fillText(`${degree}`, badgeX, badgeY);
        }

        // Label Under Node (Pill background for maximum readability)
        const labelText = node.display_name || node.class_name;
        ctx!.font = isSelected || isHovered ? 'bold 11px Inter, sans-serif' : '10px Inter, sans-serif';
        const labelWidth = ctx!.measureText(labelText).width;
        const pillY = pos.y + radius + 10;

        ctx!.fillStyle = isDimmed ? 'rgba(15, 23, 42, 0.5)' : 'rgba(15, 23, 42, 0.85)';
        ctx!.beginPath();
        ctx!.roundRect(pos.x - labelWidth / 2 - 4, pillY - 7, labelWidth + 8, 15, 3);
        ctx!.fill();

        ctx!.fillStyle = isDimmed ? 'rgba(148, 163, 184, 0.4)' : '#e2e8f0';
        ctx!.textAlign = 'center';
        ctx!.textBaseline = 'middle';
        ctx!.fillText(labelText, pos.x, pillY);
      }

      ctx!.restore();

      iteration++;
      if (iteration < maxIterations + 120) {
        animFrameRef.current = requestAnimationFrame(simulate);
      }
    }

    simulate();
    return () => cancelAnimationFrame(animFrameRef.current);
  }, [nodes, edges, width, height, selectedNode, hoveredNode, zoom, pan, labelMode, spacingMultiplier, nodeDegrees]);

  // Coordinate conversion from viewport to canvas graph world
  const getGraphCoords = useCallback(
    (clientX: number, clientY: number) => {
      const canvas = canvasRef.current;
      if (!canvas) return { x: 0, y: 0 };
      const rect = canvas.getBoundingClientRect();
      const canvasX = clientX - rect.left;
      const canvasY = clientY - rect.top;

      // Invert translate & scale
      const worldX = (canvasX - pan.x - width / 2) / zoom + width / 2;
      const worldY = (canvasY - pan.y - height / 2) / zoom + height / 2;
      return { x: worldX, y: worldY };
    },
    [pan, zoom, width, height],
  );

  // Mouse Handlers (Pan, Zoom, Drag Node)
  const handleMouseDown = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const { x, y } = getGraphCoords(e.clientX, e.clientY);
      lastMousePosRef.current = { x: e.clientX, y: e.clientY };
      isDraggingRef.current = true;

      // Check if clicking a node
      for (const [id, pos] of positionsRef.current) {
        if (Math.hypot(pos.x - x, pos.y - y) < 24) {
          dragTargetRef.current = 'node';
          draggedNodeIdRef.current = id;
          pos.pinned = true;
          return;
        }
      }

      // Otherwise panning canvas
      dragTargetRef.current = 'canvas';
    },
    [getGraphCoords],
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      const { x, y } = getGraphCoords(e.clientX, e.clientY);

      if (isDraggingRef.current) {
        const dx = e.clientX - lastMousePosRef.current.x;
        const dy = e.clientY - lastMousePosRef.current.y;
        lastMousePosRef.current = { x: e.clientX, y: e.clientY };

        if (dragTargetRef.current === 'canvas') {
          setPan(p => ({ x: p.x + dx, y: p.y + dy }));
        } else if (dragTargetRef.current === 'node' && draggedNodeIdRef.current) {
          const nodePos = positionsRef.current.get(draggedNodeIdRef.current);
          if (nodePos) {
            nodePos.x = x;
            nodePos.y = y;
            nodePos.vx = 0;
            nodePos.vy = 0;
          }
        }
        return;
      }

      // Hover check
      for (const [id, pos] of positionsRef.current) {
        if (Math.hypot(pos.x - x, pos.y - y) < 24) {
          setHoveredNode(id);
          if (canvasRef.current) canvasRef.current.style.cursor = 'pointer';
          return;
        }
      }

      setHoveredNode(null);
      if (canvasRef.current) canvasRef.current.style.cursor = 'grab';
    },
    [getGraphCoords],
  );

  const handleMouseUp = useCallback(
    (e: React.MouseEvent<HTMLCanvasElement>) => {
      if (isDraggingRef.current && dragTargetRef.current === 'node' && draggedNodeIdRef.current) {
        const nodePos = positionsRef.current.get(draggedNodeIdRef.current);
        if (nodePos) nodePos.pinned = false; // release pin
      }

      // If it was a clean click without significant drag
      const dx = Math.abs(e.clientX - lastMousePosRef.current.x);
      const dy = Math.abs(e.clientY - lastMousePosRef.current.y);
      if (dx < 5 && dy < 5) {
        const { x, y } = getGraphCoords(e.clientX, e.clientY);
        let clickedId: string | null = null;
        for (const [id, pos] of positionsRef.current) {
          if (Math.hypot(pos.x - x, pos.y - y) < 24) {
            clickedId = id;
            break;
          }
        }
        onSelectNode(clickedId === selectedNode ? null : clickedId);
      }

      isDraggingRef.current = false;
      dragTargetRef.current = null;
      draggedNodeIdRef.current = null;
      if (canvasRef.current) canvasRef.current.style.cursor = 'default';
    },
    [getGraphCoords, onSelectNode, selectedNode],
  );

  const handleWheel = useCallback((e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomFactor = e.deltaY < 0 ? 1.12 : 0.89;
    setZoom(z => Math.min(2.8, Math.max(0.45, z * zoomFactor)));
  }, []);

  return (
    <div ref={containerRef} className="relative w-full overflow-hidden rounded-xl bg-bg-primary/80 select-none">
      <canvas
        ref={canvasRef}
        style={{ width, height }}
        onMouseDown={handleMouseDown}
        onMouseMove={handleMouseMove}
        onMouseUp={handleMouseUp}
        onWheel={handleWheel}
        className="block cursor-grab active:cursor-grabbing"
      />

      {/* Floating Canvas Controls Overlay */}
      <div className="absolute top-3 right-3 flex items-center gap-1.5 glass-panel p-1.5 shadow-lg">
        <button
          onClick={() => setZoom(z => Math.min(2.8, z * 1.2))}
          title="Zoom In"
          className="w-7 h-7 rounded bg-bg-card hover:bg-bg-card-hover text-text-primary flex items-center justify-center text-sm font-bold transition-all"
        >
          +
        </button>
        <button
          onClick={() => setZoom(z => Math.max(0.45, z / 1.2))}
          title="Zoom Out"
          className="w-7 h-7 rounded bg-bg-card hover:bg-bg-card-hover text-text-primary flex items-center justify-center text-sm font-bold transition-all"
        >
          −
        </button>
        <button
          onClick={handleResetView}
          title="Reset Zoom & Center View"
          className="px-2 h-7 rounded bg-bg-card hover:bg-bg-card-hover text-text-secondary text-xs font-medium flex items-center gap-1 transition-all"
        >
          <span>⤢</span> Reset
        </button>
      </div>

      {/* Helper Tip */}
      <div className="absolute bottom-3 left-3 px-2.5 py-1 rounded bg-bg-secondary/90 border border-border text-[11px] text-text-muted flex items-center gap-3">
        <span>Scroll to Zoom</span>
        <span>·</span>
        <span>Drag Canvas to Pan</span>
        <span>·</span>
        <span>Drag Node to Reposition</span>
      </div>
    </div>
  );
}

export default function SceneGraph() {
  const [scenes, setScenes] = useState<SceneResponse[]>([]);
  const [selectedScene, setSelectedScene] = useState<string>('');
  const [graph, setGraph] = useState<SceneGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [building, setBuilding] = useState(false);

  // Filter & View Controls
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState<'all' | 'structural' | 'directional'>('all');
  const [disabledTypes, setDisabledTypes] = useState<Set<string>>(new Set());
  const [minConfidence, setMinConfidence] = useState<number>(0.3);
  const [labelMode, setLabelMode] = useState<'smart' | 'all' | 'none'>('smart');
  const [spacingMultiplier, setSpacingMultiplier] = useState<number>(1.3);
  const [classFilter, setClassFilter] = useState<string>('ALL');

  useEffect(() => {
    getScenes(25)
      .then(s => {
        setScenes(s);
        if (s.length > 0) setSelectedScene(s[0].scene_id);
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    if (!selectedScene) return;
    setLoading(true);
    setSelectedNode(null);
    getSceneGraph(selectedScene)
      .then(setGraph)
      .catch(() => setGraph(null))
      .finally(() => setLoading(false));
  }, [selectedScene]);

  const handleBuild = async () => {
    if (!selectedScene) return;
    setBuilding(true);
    try {
      const g = await buildSceneGraph(selectedScene);
      setGraph(g);
      setSelectedNode(null);
    } catch (err) {
      console.error('Failed to rebuild graph:', err);
    } finally {
      setBuilding(false);
    }
  };

  // Toggle individual relationship types
  const toggleRelationshipType = (type: string) => {
    setDisabledTypes(prev => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  // Set category preset
  const handleCategoryPreset = (category: 'all' | 'structural' | 'directional') => {
    setSelectedCategory(category);
    if (category === 'all') {
      setDisabledTypes(new Set());
    } else if (category === 'structural') {
      // Disable directional types
      setDisabledTypes(new Set(Array.from(DIRECTIONAL_TYPES)));
    } else if (category === 'directional') {
      // Disable structural types
      setDisabledTypes(new Set(Array.from(STRUCTURAL_TYPES)));
    }
  };

  // Extract all available node classes
  const availableClasses = useMemo(() => {
    if (!graph) return [];
    return Array.from(new Set(graph.nodes.map(n => n.class_name))).sort();
  }, [graph]);

  // Filter nodes & edges according to current active controls
  const filteredNodes = useMemo(() => {
    if (!graph) return [];
    if (classFilter === 'ALL') return graph.nodes;
    return graph.nodes.filter(n => n.class_name === classFilter);
  }, [graph, classFilter]);

  const activeNodeIds = useMemo(() => new Set(filteredNodes.map(n => n.object_id)), [filteredNodes]);

  const filteredEdges = useMemo(() => {
    if (!graph) return [];
    return graph.edges.filter(edge => {
      // Must connect visible nodes
      if (!activeNodeIds.has(edge.source_object_id) || !activeNodeIds.has(edge.target_object_id)) {
        return false;
      }
      // Confidence threshold
      if (edge.confidence < minConfidence) {
        return false;
      }
      // Category filter check
      if (selectedCategory === 'structural' && !STRUCTURAL_TYPES.has(edge.relationship_type)) {
        return false;
      }
      if (selectedCategory === 'directional' && !DIRECTIONAL_TYPES.has(edge.relationship_type)) {
        return false;
      }
      // Explicitly disabled
      if (disabledTypes.has(edge.relationship_type)) {
        return false;
      }
      return true;
    });
  }, [graph, activeNodeIds, minConfidence, selectedCategory, disabledTypes]);

  // Overall relationship counts in raw graph
  const rawTypeCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    graph?.edges.forEach(e => {
      counts[e.relationship_type] = (counts[e.relationship_type] || 0) + 1;
    });
    return counts;
  }, [graph]);

  // Node Inspector Data
  const selectedNodeObj = useMemo(
    () => graph?.nodes.find(n => n.object_id === selectedNode) || null,
    [graph, selectedNode],
  );

  const selectedNodeOutgoing = useMemo(
    () => filteredEdges.filter(e => e.source_object_id === selectedNode),
    [filteredEdges, selectedNode],
  );

  const selectedNodeIncoming = useMemo(
    () => filteredEdges.filter(e => e.target_object_id === selectedNode),
    [filteredEdges, selectedNode],
  );

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-text-primary">Semantic Scene Graph</h2>
          <p className="text-sm text-text-muted mt-0.5">
            Real-time topological relationship mapping & interactive spatial graph
          </p>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={selectedScene}
            onChange={e => setSelectedScene(e.target.value)}
            className="px-3 py-2 rounded-lg bg-bg-input border border-border text-text-primary text-sm focus:border-accent-cyan outline-none"
          >
            {scenes.map(s => (
              <option key={s.scene_id} value={s.scene_id}>
                {s.scene_id} ({s.object_count} objects)
              </option>
            ))}
          </select>
          <button
            onClick={handleBuild}
            disabled={building || !selectedScene}
            className="px-4 py-2 rounded-lg bg-accent-cyan/15 text-accent-cyan border border-accent-cyan/25 hover:bg-accent-cyan/25 transition-all text-sm font-medium disabled:opacity-50 flex items-center gap-1.5"
          >
            <span>{building ? '⟳' : '⚡'}</span>
            <span>{building ? 'Rebuilding…' : 'Rebuild Graph'}</span>
          </button>
        </div>
      </div>

      {/* Metrics Row */}
      {graph && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <div className="glass-panel p-3">
            <div className="text-xs text-text-muted">Total Objects</div>
            <div className="text-2xl font-bold text-accent-cyan tabular-nums mt-0.5">
              {filteredNodes.length}
              {filteredNodes.length !== graph.node_count && (
                <span className="text-xs text-text-muted font-normal ml-1.5">/ {graph.node_count}</span>
              )}
            </div>
          </div>
          <div className="glass-panel p-3">
            <div className="text-xs text-text-muted">Visible Relationships</div>
            <div className="text-2xl font-bold text-accent-emerald tabular-nums mt-0.5">
              {filteredEdges.length}
              <span className="text-xs text-text-muted font-normal ml-1.5">/ {graph.edge_count}</span>
            </div>
          </div>
          <div className="glass-panel p-3">
            <div className="text-xs text-text-muted">Active Rel Types</div>
            <div className="text-2xl font-bold text-accent-purple tabular-nums mt-0.5">
              {Object.keys(rawTypeCounts).length - disabledTypes.size}
              <span className="text-xs text-text-muted font-normal ml-1.5">/ {Object.keys(rawTypeCounts).length}</span>
            </div>
          </div>
          <div className="glass-panel p-3">
            <div className="text-xs text-text-muted">Congestion Filter</div>
            <div className="text-2xl font-bold text-accent-amber tabular-nums mt-0.5">
              {graph.edge_count > 0 ? Math.round(((graph.edge_count - filteredEdges.length) / graph.edge_count) * 100) : 0}%
              <span className="text-xs text-text-muted font-normal ml-1.5">reduced</span>
            </div>
          </div>
        </div>
      )}

      {/* Interactive Toolbar & Filters */}
      <div className="glass-panel p-4 space-y-3">
        {/* Presets & View Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border/50 pb-3">
          {/* Category Presets */}
          <div className="flex items-center gap-2">
            <span className="text-xs text-text-muted font-semibold uppercase tracking-wider">Preset:</span>
            <div className="flex rounded-lg bg-bg-input p-1 border border-border">
              <button
                onClick={() => handleCategoryPreset('all')}
                className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                  selectedCategory === 'all'
                    ? 'bg-accent-cyan text-bg-primary font-semibold shadow-sm'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                All Relations
              </button>
              <button
                onClick={() => handleCategoryPreset('structural')}
                className={`px-3 py-1 rounded text-xs font-medium transition-all flex items-center gap-1 ${
                  selectedCategory === 'structural'
                    ? 'bg-accent-emerald text-bg-primary font-semibold shadow-sm'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                <span>✦</span> Physical Only
              </button>
              <button
                onClick={() => handleCategoryPreset('directional')}
                className={`px-3 py-1 rounded text-xs font-medium transition-all ${
                  selectedCategory === 'directional'
                    ? 'bg-accent-purple text-bg-primary font-semibold shadow-sm'
                    : 'text-text-secondary hover:text-text-primary'
                }`}
              >
                Directional Only
              </button>
            </div>
          </div>

          {/* Label Mode & Spread Toggles */}
          <div className="flex flex-wrap items-center gap-4 text-xs">
            {/* Label Display Mode */}
            <div className="flex items-center gap-2">
              <span className="text-text-muted font-medium">Edge Labels:</span>
              <select
                value={labelMode}
                onChange={e => setLabelMode(e.target.value as any)}
                className="px-2.5 py-1 rounded bg-bg-input border border-border text-text-primary text-xs focus:border-accent-cyan outline-none"
              >
                <option value="smart">Smart (Hover / Select)</option>
                <option value="all">Always Show All</option>
                <option value="none">Hidden</option>
              </select>
            </div>

            {/* Spread Factor */}
            <div className="flex items-center gap-2">
              <span className="text-text-muted font-medium">Spacing:</span>
              <button
                onClick={() => setSpacingMultiplier(s => (s === 1.0 ? 1.4 : s === 1.4 ? 1.8 : 1.0))}
                className="px-2.5 py-1 rounded bg-bg-input border border-border text-text-secondary hover:text-text-primary transition-all"
              >
                {spacingMultiplier === 1.0 ? 'Compact' : spacingMultiplier === 1.4 ? 'Spacious' : 'Extra Wide'}
              </button>
            </div>

            {/* Filter by class */}
            {availableClasses.length > 0 && (
              <div className="flex items-center gap-2">
                <span className="text-text-muted font-medium">Class:</span>
                <select
                  value={classFilter}
                  onChange={e => setClassFilter(e.target.value)}
                  className="px-2.5 py-1 rounded bg-bg-input border border-border text-text-primary text-xs focus:border-accent-cyan outline-none"
                >
                  <option value="ALL">All Objects ({graph?.nodes.length})</option>
                  {availableClasses.map(cls => (
                    <option key={cls} value={cls}>
                      {cls}
                    </option>
                  ))}
                </select>
              </div>
            )}
          </div>
        </div>

        {/* Individual Relationship Type Pill Toggles */}
        {graph && Object.keys(rawTypeCounts).length > 0 && (
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-text-muted font-medium">
                Click pill to toggle relationship types on/off:
              </span>
              <div className="flex items-center gap-2">
                <span className="text-[11px] text-text-muted">Min Conf:</span>
                <input
                  type="range"
                  min="0.1"
                  max="0.8"
                  step="0.05"
                  value={minConfidence}
                  onChange={e => setMinConfidence(parseFloat(e.target.value))}
                  className="w-20 accent-accent-cyan cursor-pointer"
                />
                <span className="text-xs font-mono text-accent-cyan w-9 text-right">
                  {Math.round(minConfidence * 100)}%
                </span>
              </div>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {Object.entries(rawTypeCounts)
                .sort((a, b) => b[1] - a[1])
                .map(([type, count]) => {
                  const isDisabled = disabledTypes.has(type);
                  const color = REL_COLORS[type] || '#64748b';
                  return (
                    <button
                      key={type}
                      onClick={() => toggleRelationshipType(type)}
                      style={{
                        borderColor: isDisabled ? 'rgba(30, 45, 69, 0.7)' : `${color}60`,
                        backgroundColor: isDisabled ? 'rgba(15, 23, 42, 0.4)' : `${color}18`,
                      }}
                      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs transition-all ${
                        isDisabled ? 'opacity-40 line-through text-text-muted' : 'text-text-primary'
                      }`}
                    >
                      <span
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: isDisabled ? '#64748b' : color }}
                      />
                      <span className="font-medium">{type}</span>
                      <span className="text-[11px] text-text-muted font-mono">×{count}</span>
                    </button>
                  );
                })}
            </div>
          </div>
        )}
      </div>

      {/* Main Graph Canvas Area */}
      <div className="glass-panel p-3 relative">
        {loading ? (
          <div className="flex items-center justify-center h-[520px] text-text-muted animate-pulse">
            Loading scene graph...
          </div>
        ) : graph && graph.nodes.length > 0 ? (
          <div className="relative">
            <InteractiveForceGraph
              nodes={filteredNodes}
              edges={filteredEdges}
              selectedNode={selectedNode}
              onSelectNode={setSelectedNode}
              labelMode={labelMode}
              spacingMultiplier={spacingMultiplier}
            />

            {/* Selected Node Details Drawer / Inspector */}
            {selectedNodeObj && (
              <div className="absolute top-4 left-4 w-72 glass-panel p-4 shadow-2xl border-accent-cyan/40 animate-slide-up backdrop-blur-xl z-20">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <div className="text-xs text-accent-cyan font-mono">{selectedNodeObj.object_id}</div>
                    <div className="text-base font-bold text-text-primary capitalize">
                      {selectedNodeObj.class_name}
                    </div>
                  </div>
                  <button
                    onClick={() => setSelectedNode(null)}
                    className="text-text-muted hover:text-text-primary text-sm p-1"
                  >
                    ✕
                  </button>
                </div>

                <div className="text-xs space-y-1 text-text-muted mb-3 pb-2 border-b border-border">
                  <div className="flex justify-between">
                    <span>Detection Confidence:</span>
                    <span className="font-mono text-text-primary">
                      {Math.round(selectedNodeObj.confidence * 100)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Position:</span>
                    <span className="font-mono text-text-primary">
                      ({Math.round(selectedNodeObj.center_x)}, {Math.round(selectedNodeObj.center_y)})
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span>Lifecycle:</span>
                    <span className="font-mono text-accent-emerald">{selectedNodeObj.status}</span>
                  </div>
                </div>

                {/* Connected Relationships list */}
                <div className="space-y-2 max-h-48 overflow-y-auto pr-1">
                  {selectedNodeOutgoing.length > 0 && (
                    <div>
                      <div className="text-[10px] uppercase font-semibold text-text-muted mb-1">
                        Outgoing ({selectedNodeOutgoing.length})
                      </div>
                      {selectedNodeOutgoing.map((e, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between text-xs py-1 border-b border-border/30"
                        >
                          <span className="text-text-primary font-medium">
                            <span
                              className="px-1.5 py-0.5 rounded text-[10px] mr-1.5"
                              style={{
                                color: REL_COLORS[e.relationship_type] || '#fff',
                                backgroundColor: `${REL_COLORS[e.relationship_type] || '#fff'}20`,
                              }}
                            >
                              {e.relationship_type}
                            </span>
                            → {e.target_class || e.target_object_id}
                          </span>
                          <span className="font-mono text-[10px] text-text-muted">
                            {Math.round(e.confidence * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {selectedNodeIncoming.length > 0 && (
                    <div>
                      <div className="text-[10px] uppercase font-semibold text-text-muted mb-1 mt-2">
                        Incoming ({selectedNodeIncoming.length})
                      </div>
                      {selectedNodeIncoming.map((e, idx) => (
                        <div
                          key={idx}
                          className="flex items-center justify-between text-xs py-1 border-b border-border/30"
                        >
                          <span className="text-text-primary font-medium">
                            {e.source_class || e.source_object_id} →
                            <span
                              className="px-1.5 py-0.5 rounded text-[10px] ml-1.5"
                              style={{
                                color: REL_COLORS[e.relationship_type] || '#fff',
                                backgroundColor: `${REL_COLORS[e.relationship_type] || '#fff'}20`,
                              }}
                            >
                              {e.relationship_type}
                            </span>
                          </span>
                          <span className="font-mono text-[10px] text-text-muted">
                            {Math.round(e.confidence * 100)}%
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                  {selectedNodeOutgoing.length === 0 && selectedNodeIncoming.length === 0 && (
                    <div className="text-xs text-text-muted italic text-center py-2">
                      No relationships matching current filters.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-[520px] text-text-muted">
            <div className="text-center">
              <div className="text-3xl mb-2 opacity-30">◇</div>
              <p>No graph data available for this scene.</p>
              <p className="text-xs mt-1">Upload images with multiple objects to generate spatial relationships.</p>
            </div>
          </div>
        )}
      </div>

      {/* Relationship Table (Filtered View) */}
      {filteredEdges.length > 0 && (
        <div className="glass-panel overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center justify-between">
            <h3 className="text-sm font-semibold text-text-primary">
              Filtered Spatial Relationships ({filteredEdges.length})
            </h3>
            <span className="text-xs text-text-muted">
              Sorted by source object
            </span>
          </div>
          <div className="overflow-x-auto max-h-72 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-bg-secondary z-10">
                <tr className="border-b border-border text-xs text-text-muted">
                  <th className="text-left px-4 py-2 font-medium">Source</th>
                  <th className="text-left px-4 py-2 font-medium">Relationship</th>
                  <th className="text-left px-4 py-2 font-medium">Target</th>
                  <th className="text-left px-4 py-2 font-medium">Confidence</th>
                  <th className="text-left px-4 py-2 font-medium">Distance</th>
                </tr>
              </thead>
              <tbody>
                {filteredEdges.slice(0, 150).map((edge, i) => (
                  <tr
                    key={i}
                    onClick={() => setSelectedNode(edge.source_object_id)}
                    className="border-b border-border/30 hover:bg-bg-card-hover transition-colors cursor-pointer"
                  >
                    <td className="px-4 py-2 text-text-primary font-medium">
                      {edge.source_class || edge.source_object_id}
                    </td>
                    <td className="px-4 py-2">
                      <span
                        className="px-2 py-0.5 rounded text-xs font-medium"
                        style={{
                          color: REL_COLORS[edge.relationship_type] || '#64748b',
                          backgroundColor: `${REL_COLORS[edge.relationship_type] || '#64748b'}20`,
                        }}
                      >
                        {edge.relationship_type}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-text-primary">
                      {edge.target_class || edge.target_object_id}
                    </td>
                    <td className="px-4 py-2 text-text-muted font-mono text-xs">
                      {(edge.confidence * 100).toFixed(0)}%
                    </td>
                    <td className="px-4 py-2 text-text-muted font-mono text-xs">
                      {edge.distance_px ? `${edge.distance_px.toFixed(0)}px` : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
