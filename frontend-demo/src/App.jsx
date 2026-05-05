import React, { Suspense, useEffect, useMemo, useRef, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas } from '@react-three/fiber';
import { Bounds, Html, Line, OrbitControls, useGLTF } from '@react-three/drei';
import * as THREE from 'three';
import './style.css';

const DEFAULT_API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
const LOD_OPTIONS = ['low', 'medium', 'high'];
const TABS = ['artifact', 'request', 'response', 'job', 'platform', 'ingest'];
const DIM_KEYS = ['d', 'L', 'P', 'k', 's', 'b', 'm', 'OD', 'ID', 'h', 'thickness'];

function FastenerModel({ url, onBBoxReady, expectedParams, hasResolvedAnnotations }) {
  const gltf = useGLTF(url);
  useEffect(() => {
    // Override material so the model is readable without an environment HDR.
    // CadQuery's GLB exporter writes PBR materials with high metalness; without
    // an env map they render almost black. Force a non-reflective steel look.
    gltf.scene.traverse((obj) => {
      if (!obj.isMesh) return;
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      mats.forEach((m) => {
        if (!m) return;
        if ('metalness' in m) m.metalness = 0.25;
        if ('roughness' in m) m.roughness = 0.55;
        if (m.color && typeof m.color.setRGB === 'function') {
          m.color.setRGB(0.72, 0.72, 0.7);
        }
        if ('envMapIntensity' in m) m.envMapIntensity = 0;
        m.needsUpdate = true;
      });
      obj.castShadow = false;
      obj.receiveShadow = false;
    });
    if (!onBBoxReady) return;
    const box = new THREE.Box3().setFromObject(gltf.scene);
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);
    const sizeArr = size.toArray();
    onBBoxReady({
      min: box.min.toArray(),
      max: box.max.toArray(),
      size: sizeArr,
      center: center.toArray(),
    });
    // Auto-verify rendered geometry matches the dimension the user picked.
    if (expectedParams && !hasResolvedAnnotations) {
      const longest = Math.max(...sizeArr);
      const expected =
        expectedParams.L !== undefined
          ? Number(expectedParams.L) + Number(expectedParams.k || 0)
          : expectedParams.m !== undefined
          ? Number(expectedParams.m)
          : expectedParams.h !== undefined
          ? Number(expectedParams.h)
          : null;
      if (expected !== null && expected > 0) {
        const drift = Math.abs(longest - expected);
        if (drift > Math.max(1.0, expected * 0.06)) {
          console.warn(
            `[viewer] geometry drift: longest=${longest.toFixed(2)}mm, expected\u2248${expected.toFixed(2)}mm`,
          );
        }
      }
    }
  }, [gltf.scene, hasResolvedAnnotations, onBBoxReady, expectedParams]);
  return <primitive object={gltf.scene} />;
}

const _UP = new THREE.Vector3(0, 1, 0);

function ArrowHead({ position, direction, size, color }) {
  const rot = useMemo(() => {
    const dir = new THREE.Vector3(...direction).normalize();
    const q = new THREE.Quaternion().setFromUnitVectors(_UP, dir);
    return new THREE.Euler().setFromQuaternion(q);
  }, [direction[0], direction[1], direction[2]]);
  return (
    <mesh position={position} rotation={[rot.x, rot.y, rot.z]}>
      <coneGeometry args={[size * 0.32, size * 1.4, 10]} />
      <meshBasicMaterial color={color} />
    </mesh>
  );
}

function DimMeasure({ a, b, offset, label, color = '#5b6573' }) {
  // a, b: feature endpoints in world coords
  // offset: vector from feature line to dimension line (perpendicular)
  const ax = [a[0] + offset[0], a[1] + offset[1], a[2] + offset[2]];
  const bx = [b[0] + offset[0], b[1] + offset[1], b[2] + offset[2]];
  const dim = Math.hypot(b[0] - a[0], b[1] - a[1], b[2] - a[2]);
  const arrowSize = Math.max(dim * 0.04, 0.6);
  // Arrow direction: at ax → from bx to ax (outward); at bx → from ax to bx
  const dirAtA = [ax[0] - bx[0], ax[1] - bx[1], ax[2] - bx[2]];
  const dirAtB = [bx[0] - ax[0], bx[1] - ax[1], bx[2] - ax[2]];
  // Slightly extend extension lines past the dim line for CAD look
  const extPad = arrowSize * 0.6;
  const aExt = [
    a[0] + offset[0] * (1 + extPad / Math.hypot(...offset.map((v) => v || 0.0001))),
    a[1] + offset[1] * (1 + extPad / Math.hypot(...offset.map((v) => v || 0.0001))),
    a[2] + offset[2] * (1 + extPad / Math.hypot(...offset.map((v) => v || 0.0001))),
  ];
  const bExt = [
    b[0] + offset[0] * (1 + extPad / Math.hypot(...offset.map((v) => v || 0.0001))),
    b[1] + offset[1] * (1 + extPad / Math.hypot(...offset.map((v) => v || 0.0001))),
    b[2] + offset[2] * (1 + extPad / Math.hypot(...offset.map((v) => v || 0.0001))),
  ];
  return (
    <group>
      {/* Extension lines from feature, going past dim line slightly */}
      <Line points={[a, aExt]} color={color} lineWidth={0.8} />
      <Line points={[b, bExt]} color={color} lineWidth={0.8} />
      {/* Dimension line */}
      <Line points={[ax, bx]} color={color} lineWidth={1.2} />
      <ArrowHead position={ax} direction={dirAtA} size={arrowSize} color={color} />
      <ArrowHead position={bx} direction={dirAtB} size={arrowSize} color={color} />
      <Html
        position={[(ax[0] + bx[0]) / 2, (ax[1] + bx[1]) / 2, (ax[2] + bx[2]) / 2]}
        center
        zIndexRange={[100, 0]}
        style={{ pointerEvents: 'none' }}
      >
        <div className="dim-label-cad">{label}</div>
      </Html>
    </group>
  );
}

function DimLeader({ point, label, leaderEnd, color = '#5b6573' }) {
  // Leader-style annotation: point on feature → bent line out → label
  const arrowSize = 0.5;
  const dir = [point[0] - leaderEnd[0], point[1] - leaderEnd[1], point[2] - leaderEnd[2]];
  return (
    <group>
      <Line points={[point, leaderEnd]} color={color} lineWidth={0.8} />
      <ArrowHead position={point} direction={dir} size={arrowSize} color={color} />
      <Html position={leaderEnd} center style={{ pointerEvents: 'none' }}>
        <div className="dim-label-cad">{label}</div>
      </Html>
    </group>
  );
}

function fmtNumber(v) {
  const n = Number(v);
  if (!Number.isFinite(n)) return '';
  if (Number.isInteger(n)) return `${n}`;
  return n.toFixed(2).replace(/\.?0+$/, '');
}

const DimAnnotations = React.memo(function DimAnnotations({ bbox, params, annotations }) {
  const dims = useMemo(() => {
    if (Array.isArray(annotations) && annotations.length > 0) {
      return {
        measures: annotations.map((annotation) => ({
          key: annotation.key,
          a: annotation.from_point,
          b: annotation.to_point,
          offset: [0, 0, 0],
          label: `${annotation.key} = ${fmtNumber(annotation.value_mm)}`,
          color: annotation.color_hex,
        })),
        leaders: [],
      };
    }
    if (!bbox || !params) return { measures: [], leaders: [] };
    const { min, max, size } = bbox;
    // CadQuery templates extrude along +Z. Length params (L/m/h/k) are along Z;
    // diameter and across-flats are in the XY plane. Bbox-longest heuristic
    // is wrong for nuts/washers where XY > Z.
    const lateral = Math.max(size[0], size[1]);
    // Offset is proportional to part size, capped so dim arrows stay close
    // to the model on tiny parts (M1.6) and don't blow out the framing.
    const partScale = Math.max(lateral, size[2]);
    const off = Math.min(Math.max(partScale * 0.45, 1.5), partScale * 1.2);
    const measures = [];
    const leaders = [];

    const lenKey =
      params.L !== undefined ? 'L'
      : params.m !== undefined ? 'm'
      : params.h !== undefined ? 'h'
      : null;
      // Length dim along Z, dim line offset to -X side
      if (lenKey) {
      const a = [min[0], 0, min[2]];
      const b = [min[0], 0, max[2]];
      measures.push({
          key: 'len',
          a, b,
          offset: [-off, 0, 0],
          label: `${lenKey} = ${fmtNumber(params[lenKey])}`,
        });
      }

    // Head height k (bolts) — along Z near the head
    if (params.k !== undefined && lenKey === 'L') {
      const k = Number(params.k);
      const a = [min[0], 0, min[2]];
      const b = [min[0], 0, min[2] + k];
      measures.push({
          key: 'k',
          a, b,
          offset: [-off * 0.45, 0, 0],
          label: `k = ${fmtNumber(k)}`,
        });
      }

    // Across-flats s — measured on +Y face, dim line offset further +Y
    if (params.s !== undefined) {
      const a = [min[0], max[1], min[2]];
      const b = [max[0], max[1], min[2]];
      measures.push({
          key: 's',
          a, b,
          offset: [0, off * 0.55, 0],
          label: `s = ${fmtNumber(params.s)}`,
        });
      }

    // Diameter — leader at mid-Z, points at cylinder body (+X side)
    const diaKey =
      params.OD !== undefined ? 'OD'
      : params.d !== undefined ? 'd'
      : params.dk !== undefined ? 'dk'
      : null;
    if (diaKey) {
      const dia = Number(params[diaKey]);
      const cz = (min[2] + max[2]) / 2;
      const point = [dia / 2, 0, cz];
      const leaderEnd = [dia / 2 + off * 0.55, off * 0.4, cz];
        leaders.push({
          key: diaKey,
          point,
          leaderEnd,
          label: `\u00d8${diaKey} = ${fmtNumber(dia)}`,
        });
      }

      return { measures, leaders };
  }, [annotations, bbox, params]);

  return (
    <>
      {dims.measures.map((d) => (
        <DimMeasure key={d.key} {...d} />
      ))}
      {dims.leaders.map((l) => (
        <DimLeader key={l.key} {...l} />
      ))}
    </>
  );
});

function DrawingIngestForm({ apiBase, defaultProductId }) {
  const [productId, setProductId] = useState(defaultProductId || '');
  const [adminKey, setAdminKey] = useState('');
  const [file, setFile] = useState(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');

  useEffect(() => {
    if (defaultProductId) setProductId(defaultProductId);
  }, [defaultProductId]);

  async function submit(event) {
    event.preventDefault();
    setError('');
    setResult(null);
    if (!file) {
      setError('Pick an SVG/TXT file first');
      return;
    }
    if (!productId) {
      setError('Choose a product_id (e.g. hex-bolt-iso4014)');
      return;
    }
    const form = new FormData();
    form.append('product_id', productId);
    form.append('file', file);
    setBusy(true);
    try {
      const headers = adminKey ? { 'X-Admin-API-Key': adminKey } : {};
      const response = await fetch(`${apiBase}/api/v1/ingest/2d/upload`, {
        method: 'POST',
        body: form,
        headers,
      });
      const text = await response.text();
      let payload = null;
      try {
        payload = text ? JSON.parse(text) : null;
      } catch {
        payload = text;
      }
      if (!response.ok) {
        const detail = typeof payload === 'string'
          ? payload
          : (payload && typeof payload.detail === 'string'
            ? payload.detail
            : (payload ? JSON.stringify(payload) : response.statusText));
        throw new Error(`${response.status} ${response.statusText}: ${detail}`);
      }
      setResult(payload);
    } catch (err) {
      setError(err.message || String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="ingest-form" onSubmit={submit}>
      <p className="ingest-help">
        Drag-drop an SVG/TXT drawing. The backend extracts dimensions and metadata, stores a
        parsed-drawing record, and returns the SHA256.
      </p>
      <label className="field">
        <span>Product ID</span>
        <input
          value={productId}
          onChange={(event) => setProductId(event.target.value)}
          placeholder="hex-bolt-iso4014"
        />
      </label>
      <label className="field">
        <span>Admin API Key (X-Admin-API-Key)</span>
        <input
          type="password"
          value={adminKey}
          onChange={(event) => setAdminKey(event.target.value)}
          placeholder="leave blank if backend has no admin key"
        />
      </label>
      <label className="field">
        <span>Drawing file (.svg or .txt)</span>
        <input
          type="file"
          accept=".svg,.txt,image/svg+xml,text/plain"
          onChange={(event) => setFile(event.target.files?.[0] || null)}
        />
      </label>
      <div className="action-row">
        <button className="primary-button" type="submit" disabled={busy}>
          {busy ? 'Uploading\u2026' : 'Upload Drawing'}
        </button>
      </div>
      {error ? <div className="error-strip">{error}</div> : null}
      {result ? <pre className="json-block">{JSON.stringify(result, null, 2)}</pre> : null}
    </form>
  );
}

class ViewerErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  componentDidUpdate(prevProps) {
    if (prevProps.resetKey !== this.props.resetKey && this.state.error) {
      this.setState({ error: null });
    }
  }
  render() {
    if (this.state.error) {
      return (
        <div className="viewer-fallback">
          Viewer error: {String(this.state.error.message || this.state.error)}
        </div>
      );
    }
    return this.props.children;
  }
}

function DimensionPanel({ params, onParamChange, dirty, onApply, onReset, busy }) {
  const entries = DIM_KEYS.filter(
    (key) => params && params[key] !== undefined && params[key] !== null && params[key] !== '',
  );
  if (entries.length === 0) return null;
  return (
    <div className="dim-overlay">
      {entries.map((key) => (
        <label key={key} className="dim-chip">
          <span>{key}</span>
          <input
            type="number"
            step="0.1"
            value={params[key] ?? ''}
            onChange={(event) => onParamChange(key, event.target.value)}
          />
        </label>
      ))}
      <div className="dim-actions">
        <button type="button" className="primary-button" onClick={onApply} disabled={!dirty || busy}>
          {busy ? '\u2026' : 'Apply'}
        </button>
        <button type="button" className="ghost-button" onClick={onReset} disabled={!dirty || busy}>
          Reset
        </button>
      </div>
    </div>
  );
}

const ViewerStage = React.memo(function ViewerStage({ modelUrl, viewerMessage, params, annotations }) {
  const [bbox, setBBox] = useState(null);
  return (
    <div className="viewer-stage">
      <ViewerErrorBoundary resetKey={modelUrl}>
        <Canvas
          camera={{ position: [60, 40, 60], fov: 35 }}
          dpr={[1, 1.5]}
          gl={{ antialias: true, powerPreference: 'high-performance' }}
        >
          <color attach="background" args={['#eef1f5']} />
          <hemisphereLight args={['#ffffff', '#5a6573', 1.1]} />
          <ambientLight intensity={0.85} />
          <directionalLight position={[14, 24, 14]} intensity={1.6} />
          <directionalLight position={[-12, 6, -10]} intensity={0.6} />
          <directionalLight position={[0, -10, 5]} intensity={0.3} />
          {modelUrl ? (
            <>
              <Bounds fit clip observe margin={2.2}>
                <Suspense fallback={null}>
                  <FastenerModel
                    key={modelUrl}
                    url={modelUrl}
                    onBBoxReady={setBBox}
                    expectedParams={params}
                    hasResolvedAnnotations={Array.isArray(annotations) && annotations.length > 0}
                  />
                </Suspense>
              </Bounds>
              {(annotations?.length || (bbox && params)) ? <DimAnnotations bbox={bbox} params={params} annotations={annotations} /> : null}
            </>
          ) : null}
          <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
        </Canvas>
      </ViewerErrorBoundary>
      {!modelUrl ? <div className="viewer-html-static">{viewerMessage}</div> : null}
    </div>
  );
});

function toJson(value) {
  return JSON.stringify(value ?? null, null, 2);
}

function statusTone(value) {
  if (value === 'ok' || value === 'ready' || value === 'done') return 'good';
  if (value === 'queued' || value === 'pending' || value === 'running') return 'warn';
  if (value === 'failed' || value === 'error' || value === 'missing' || value === 'empty') return 'bad';
  return 'neutral';
}

function metricValue(payload, name) {
  const line = String(payload || '')
    .split('\n')
    .find((item) => item.startsWith(`${name} `));
  return line ? line.split(' ')[1] : '-';
}

function sanitizeParams(params) {
  const next = { ...params };
  delete next.lod;
  return next;
}

function flattenVariantGroups(groups) {
  return Object.values(groups || {}).flat();
}

function groupOrder(groups) {
  return Object.entries(groups || {}).sort(([left], [right]) => left.localeCompare(right, undefined, { numeric: true }));
}

function numberLike(value) {
  if (typeof value === 'number') return value;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : value;
}

function App() {
  const [apiBaseInput, setApiBaseInput] = useState(DEFAULT_API_BASE);
  const [apiBase, setApiBase] = useState(DEFAULT_API_BASE);
  const [health, setHealth] = useState(null);
  const [ready, setReady] = useState(null);
  const [metrics, setMetrics] = useState('');
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [variantGroups, setVariantGroups] = useState({});
  const [selectedVariantId, setSelectedVariantId] = useState('');
  const [selectedLod, setSelectedLod] = useState('medium');
  const [requestMode, setRequestMode] = useState('variant');
  const [productParameters, setProductParameters] = useState([]);
  const [paramDraft, setParamDraft] = useState({});
  const [geometryResponse, setGeometryResponse] = useState(null);
  const [jobResponse, setJobResponse] = useState(null);
  const [requestPayload, setRequestPayload] = useState(null);
  const [activeTab, setActiveTab] = useState('artifact');
  const [busy, setBusy] = useState(false);
  const [statusText, setStatusText] = useState('Connecting to backend');
  const [errorText, setErrorText] = useState('');
  const [lastUpdatedAt, setLastUpdatedAt] = useState('');
  const [lastProductRequest, setLastProductRequest] = useState('');
  const pollTimerRef = useRef(null);

  const productMap = useMemo(
    () => Object.fromEntries(products.map((product) => [product.product_id, product])),
    [products],
  );

  const currentProduct = productMap[selectedProductId] || null;
  const flatVariants = useMemo(() => flattenVariantGroups(variantGroups), [variantGroups]);
  const selectedVariant = useMemo(
    () => flatVariants.find((variant) => variant.variant_id === selectedVariantId) || null,
    [flatVariants, selectedVariantId],
  );

  const customLabel = useMemo(() => {
    if (!paramDraft) return '';
    const d = paramDraft.d ?? paramDraft.OD;
    const len = paramDraft.L ?? paramDraft.m ?? paramDraft.h;
    if (d === undefined && len === undefined) return '';
    const dStr = d !== undefined ? `M${d}` : '';
    const lStr = len !== undefined ? ` \u00d7 ${len} mm` : '';
    return (dStr + lStr).trim();
  }, [paramDraft]);

  const paramDirty = useMemo(() => {
    if (!selectedVariant) return false;
    return DIM_KEYS.some((key) => {
      const a = paramDraft?.[key];
      const b = selectedVariant.params?.[key];
      if (a === undefined && b === undefined) return false;
      return Number(a) !== Number(b);
    });
  }, [paramDraft, selectedVariant]);

  const modelUrl = useMemo(() => {
    if (!geometryResponse?.artifact?.url) return '';
    return geometryResponse.artifact.url.startsWith('http')
      ? geometryResponse.artifact.url
      : `${apiBase}${geometryResponse.artifact.url}`;
  }, [apiBase, geometryResponse]);

  const viewerMessage = useMemo(() => {
    if (busy) return 'Loading response\u2026';
    if (errorText) return 'Request failed';
    if (!geometryResponse) return 'Choose a variant or generate geometry';
    if (geometryResponse.status === 'queued') return `Job queued${geometryResponse.job_id ? `: ${geometryResponse.job_id}` : ''}`;
    if (geometryResponse.status === 'failed') return geometryResponse.message || 'Generation failed';
    if (!geometryResponse.artifact) return 'No artifact returned';
    return '';
  }, [busy, errorText, geometryResponse]);

  const backendModeWarning = useMemo(() => {
    if (health?.cad_backend !== 'mock') return '';
    return 'Backend is running in mock CAD mode. Restart with CAD_BACKEND=cadquery for real GLB preview rendering.';
  }, [health]);

  useEffect(() => () => {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
    }
  }, []);

  function ensureRenderableBackend() {
    if (health?.cad_backend !== 'mock') return true;
    const message = 'Preview rendering is disabled while backend CAD mode is mock. Restart backend with CAD_BACKEND=cadquery.';
    setErrorText(message);
    setStatusText('Backend connected, mock CAD mode');
    setActiveTab('platform');
    return false;
  }

  async function fetchJson(path, init) {
    const response = await fetch(`${apiBase}${path}`, init);
    const text = await response.text();
    let payload = null;
    try {
      payload = text ? JSON.parse(text) : null;
    } catch {
      payload = text;
    }
    if (!response.ok) {
      const detail = typeof payload === 'object' && payload?.detail ? payload.detail : payload;
      throw new Error(`${response.status} ${response.statusText}${detail ? `: ${typeof detail === 'string' ? detail : JSON.stringify(detail)}` : ''}`);
    }
    return payload;
  }

  async function safeReadJson(response) {
    const text = await response.text();
    try {
      return text ? JSON.parse(text) : null;
    } catch {
      return text || null;
    }
  }

  async function refreshPlatform(targetBase = apiBase) {
    // /ready may legitimately return 503 (catalog empty / Redis down). Capture
    // each endpoint's success independently; do NOT throw because /ready=503.
    const [healthResponse, readyResponse, metricsResponse] = await Promise.all([
      fetch(`${targetBase}/health`).catch((err) => ({ ok: false, status: 0, _err: err })),
      fetch(`${targetBase}/ready`).catch((err) => ({ ok: false, status: 0, _err: err })),
      fetch(`${targetBase}/metrics`).catch((err) => ({ ok: false, status: 0, _err: err })),
    ]);

    let healthBody = null;
    let readyBody = null;
    let metricsBody = '';
    if (healthResponse.ok) {
      healthBody = await safeReadJson(healthResponse);
    } else if (typeof healthResponse.text === 'function') {
      healthBody = { status: 'down', http: healthResponse.status };
    }
    if (typeof readyResponse.text === 'function') {
      // 200 → ready, 503 → unready but body is parseable; both are valid contract states
      readyBody = await safeReadJson(readyResponse);
      if (readyBody && typeof readyBody === 'object' && readyResponse.status >= 500) {
        readyBody = { ...readyBody, http: readyResponse.status };
      }
    }
    if (metricsResponse.ok && typeof metricsResponse.text === 'function') {
      metricsBody = await metricsResponse.text();
    }
    setHealth(healthBody);
    setReady(readyBody);
    setMetrics(metricsBody);
    return {
      health_ok: !!(healthResponse && healthResponse.ok),
      ready_ok: !!(readyResponse && readyResponse.status === 200),
      metrics_ok: !!(metricsResponse && metricsResponse.ok),
    };
  }

  async function refreshProducts(targetBase = apiBase) {
    const response = await fetch(`${targetBase}/api/v1/products`);
    const payload = await safeReadJson(response);
    if (!response.ok) {
      const detail = typeof payload === 'string' ? payload : payload?.detail ?? '';
      throw new Error(`GET /api/v1/products failed: ${response.status} ${response.statusText}${detail ? ` - ${typeof detail === 'string' ? detail : JSON.stringify(detail)}` : ''}`);
    }
    if (!Array.isArray(payload)) {
      throw new Error('GET /api/v1/products: expected JSON array, got ' + (typeof payload));
    }
    setProducts(payload);
    if (!selectedProductId || !payload.some((product) => product.product_id === selectedProductId)) {
      setSelectedProductId(payload[0]?.product_id || '');
    }
  }

  async function loadBootstrap(targetBase = apiBase) {
    setBusy(true);
    setErrorText('');
    setStatusText('Loading platform state');
    try {
      const [platformOk] = await Promise.all([
        refreshPlatform(targetBase),
        refreshProducts(targetBase),
      ]);
      // Distinguish: connected-but-not-ready (503) vs fully ready
      if (!platformOk.health_ok) {
        setStatusText('Backend health check failed');
      } else if (!platformOk.ready_ok) {
        setStatusText('Backend connected, not ready (catalog/Redis)');
      } else {
        setStatusText('Backend ready');
      }
      setLastUpdatedAt(new Date().toLocaleTimeString());
    } catch (error) {
      setErrorText(error.message);
      setStatusText('Backend unavailable');
    } finally {
      setBusy(false);
    }
  }

  useEffect(() => {
    loadBootstrap(apiBase);
  }, [apiBase]);

  useEffect(() => {
    if (!selectedProductId) {
      setVariantGroups({});
      setSelectedVariantId('');
      setProductParameters([]);
      setParamDraft({});
      return;
    }

    let active = true;

    async function loadProductContext() {
      setBusy(true);
      setErrorText('');
      setStatusText(`Loading ${selectedProductId}`);
      try {
        const [productResponse, variantResponse] = await Promise.all([
          fetchJson(`/api/v1/products/${selectedProductId}`),
          fetchJson(`/api/v1/products/${selectedProductId}/variants`),
        ]);

        if (!active) return;
        const grouped = variantResponse.grouped_by_diameter || {};
        const variants = flattenVariantGroups(grouped);
        const nextVariant = variants.find((item) => item.variant_id === selectedVariantId) || variants[0] || null;

        setProductParameters(productResponse.parameters || []);
        setVariantGroups(grouped);
        setSelectedVariantId(nextVariant?.variant_id || '');
        setParamDraft(nextVariant ? { ...nextVariant.params } : {});
        setLastProductRequest(selectedProductId);
        setStatusText(`Loaded ${productResponse.name}`);
      } catch (error) {
        if (!active) return;
        setErrorText(error.message);
        setStatusText('Product load failed');
      } finally {
        if (active) {
          setBusy(false);
        }
      }
    }

    loadProductContext();
    return () => {
      active = false;
    };
  }, [selectedProductId]);

  useEffect(() => {
    if (!selectedVariant) return;
    setParamDraft({ ...selectedVariant.params });
  }, [selectedVariantId]);

  useEffect(() => {
    if (requestMode !== 'variant') return;
    if (!selectedVariantId) return;
    runVariantFlow();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedVariantId, selectedLod, requestMode]);

  function stopPolling() {
    if (pollTimerRef.current) {
      clearTimeout(pollTimerRef.current);
      pollTimerRef.current = null;
    }
  }

  function scheduleJobPoll(jobId) {
    stopPolling();
    pollTimerRef.current = setTimeout(() => {
      pollJob(jobId);
    }, 1500);
  }

  async function pollJob(jobId) {
    if (!jobId) return;
    try {
      const payload = await fetchJson(`/api/v1/model-jobs/${jobId}`);
      setJobResponse(payload);
      if (payload.status === 'pending' || payload.status === 'running') {
        setStatusText(`Job ${payload.status}`);
        scheduleJobPoll(jobId);
        return;
      }
      // job done, no need to refresh metrics on each tick
      if (payload.status === 'done' && payload.artifact) {
        setGeometryResponse((current) => ({
          ...(current || {}),
          status: 'ready',
          source: current?.source || 'queued_parametric',
          artifact: payload.artifact,
          job_id: jobId,
          message: null,
        }));
        setStatusText('Queued job completed');
      } else if (payload.status === 'failed') {
        setGeometryResponse((current) => ({
          ...(current || {}),
          status: 'failed',
          job_id: jobId,
          message: payload.error_message || 'Job failed',
        }));
        setStatusText('Queued job failed');
      }
    } catch (error) {
      setErrorText(error.message);
      setStatusText('Job polling failed');
    }
  }

  async function runVariantFlow() {
    if (!selectedVariantId) return;
    if (!ensureRenderableBackend()) return;
    stopPolling();
    setBusy(true);
    setErrorText('');
    setActiveTab('response');
    setJobResponse(null);
    const payload = {
      mode: 'variant',
      product_id: selectedProductId,
      variant_id: selectedVariantId,
      lod: selectedLod,
    };
    setRequestPayload(payload);
    try {
      const response = await fetchJson(`/api/v1/geometry/variant/${selectedVariantId}?lod=${selectedLod}`);
      setGeometryResponse(response);
      setStatusText(`Geometry ${response.status}`);
      setLastUpdatedAt(new Date().toLocaleTimeString());
      if (response.status === 'queued' && response.job_id) {
        setJobResponse({ job_id: response.job_id, status: 'pending' });
        setActiveTab('job');
        scheduleJobPoll(response.job_id);
      } else {
        setActiveTab('artifact');
      }
    } catch (error) {
      setGeometryResponse(null);
      setErrorText(error.message);
      setStatusText('Variant request failed');
    } finally {
      setBusy(false);
    }
  }

  async function runGenerateFlow() {
    if (!selectedProductId) return;
    if (!ensureRenderableBackend()) return;
    stopPolling();
    setBusy(true);
    setErrorText('');
    setActiveTab('response');
    setJobResponse(null);
    const payload = {
      product_id: selectedProductId,
      params: sanitizeParams(paramDraft),
      lod: selectedLod,
      format: 'glb',
    };
    setRequestPayload(payload);
    try {
      const response = await fetchJson('/api/v1/geometry/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setGeometryResponse(response);
      setStatusText(`Generate ${response.status}`);
      setLastUpdatedAt(new Date().toLocaleTimeString());
      if (response.status === 'queued' && response.job_id) {
        setJobResponse({ job_id: response.job_id, status: 'pending' });
        setActiveTab('job');
        scheduleJobPoll(response.job_id);
      } else {
        setActiveTab('artifact');
      }
    } catch (error) {
      setGeometryResponse(null);
      setErrorText(error.message);
      setStatusText('Generate request failed');
    } finally {
      setBusy(false);
    }
  }

  function applyApiBase() {
    const next = apiBaseInput.trim().replace(/\/+$/, '');
    if (!next || next === apiBase) return;
    stopPolling();
    setGeometryResponse(null);
    setJobResponse(null);
    setApiBase(next);
  }

  function resetParamDraft() {
    if (selectedVariant) {
      setParamDraft({ ...selectedVariant.params });
    }
  }

  return (
    <main className="workbench">
      <section className="topbar">
        <div className="headline">
          <div>
            <h1>Fastener CAD Workbench</h1>
            <p>Production-style demo shell for catalog, geometry, queue, and diagnostics.</p>
          </div>
          <div className="topbar-meta">
            <span className={`status-pill ${statusTone(health?.status)}`}>{health?.status || 'offline'}</span>
            <span className={`status-pill ${statusTone(ready?.status)}`}>{ready?.status || 'unready'}</span>
            <span className="status-text">{statusText}</span>
          </div>
        </div>
        <div className="connection-strip">
          <label className="field api-field">
            <span>API Base URL</span>
            <input value={apiBaseInput} onChange={(event) => setApiBaseInput(event.target.value)} />
          </label>
          <button className="primary-button" onClick={applyApiBase} type="button">
            Connect
          </button>
          <button className="ghost-button" onClick={() => loadBootstrap(apiBase)} type="button">
            Refresh
          </button>
        </div>
        {backendModeWarning ? <p className="warning-banner">{backendModeWarning}</p> : null}
      </section>

      <section className="split-layout">
        <aside className="sidebar">
          <section className="panel">
            <div className="panel-heading">
              <h2>Catalog</h2>
              <span>{products.length} products</span>
            </div>
            <div className="product-list">
              {products.map((product) => (
                <button
                  key={product.product_id}
                  type="button"
                  className={`product-button ${selectedProductId === product.product_id ? 'active' : ''}`}
                  onClick={() => {
                    setRequestMode('variant');
                    setSelectedProductId(product.product_id);
                  }}
                >
                  <strong>{product.name}</strong>
                  <span>{product.standard}</span>
                </button>
              ))}
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <h2>Selection</h2>
              <span>{currentProduct?.family || '-'}</span>
            </div>
            <div className="field-grid">
              <label className="field">
                <span>Mode</span>
                <div className="segmented">
                  <button
                    type="button"
                    className={requestMode === 'variant' ? 'active' : ''}
                    onClick={() => setRequestMode('variant')}
                  >
                    Variant
                  </button>
                  <button
                    type="button"
                    className={requestMode === 'direct' ? 'active' : ''}
                    onClick={() => setRequestMode('direct')}
                  >
                    Direct
                  </button>
                </div>
              </label>
              <label className="field">
                <span>LOD</span>
                <div className="segmented">
                  {LOD_OPTIONS.map((lod) => (
                    <button
                      key={lod}
                      type="button"
                      className={selectedLod === lod ? 'active' : ''}
                      onClick={() => setSelectedLod(lod)}
                    >
                      {lod}
                    </button>
                  ))}
                </div>
              </label>
            </div>
          </section>

          <section className="panel">
            <div className="panel-heading">
              <h2>Variants</h2>
              <span>{flatVariants.length} items</span>
            </div>
            <div className="variant-groups">
              {groupOrder(variantGroups).map(([diameter, items]) => (
                <div key={diameter} className="variant-group">
                  <div className="variant-group-label">{diameter}</div>
                  <div className="variant-group-items">
                    {items.map((variant) => (
                      <button
                        key={variant.variant_id}
                        type="button"
                        className={`variant-chip ${selectedVariantId === variant.variant_id ? 'active' : ''}`}
                        onClick={() => {
                          setRequestMode('variant');
                          setSelectedVariantId(variant.variant_id);
                        }}
                      >
                        {variant.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </section>

          {paramDirty && customLabel ? (
            <section className="panel custom-panel">
              <div className="panel-heading">
                <h2>Custom Size</h2>
                <span>unsaved</span>
              </div>
              <div className="custom-row">
                <span className="variant-chip custom active">{customLabel}</span>
                <span className="custom-hint">Click Apply to render</span>
              </div>
            </section>
          ) : null}

          <section className="panel">
            <div className="panel-heading">
              <h2>Generate</h2>
              <span>{lastProductRequest || '-'}</span>
            </div>
            <div className="param-grid">
              {productParameters.map((parameter) => (
                <label key={parameter.name} className="field">
                  <span>{parameter.name}</span>
                  <input
                    value={paramDraft[parameter.name] ?? ''}
                    onChange={(event) =>
                      setParamDraft((current) => ({
                        ...current,
                        [parameter.name]: numberLike(event.target.value),
                      }))
                    }
                  />
                </label>
              ))}
            </div>
            <div className="action-row">
              <button className="primary-button" type="button" onClick={runVariantFlow} disabled={!selectedVariantId || busy}>
                Resolve Variant
              </button>
              <button className="primary-button secondary" type="button" onClick={runGenerateFlow} disabled={!selectedProductId || busy}>
                Generate
              </button>
              <button className="ghost-button" type="button" onClick={resetParamDraft}>
                Reset Params
              </button>
            </div>
          </section>
        </aside>

        <section className="main-stage">
          <section className="viewer-panel">
            <div className="viewer-header">
              <div>
                <h2>{selectedVariant?.sku || currentProduct?.name || '3D Preview'}</h2>
                <p>{geometryResponse?.source || 'No geometry response yet'}</p>
              </div>
              <div className="viewer-badges">
                <span className={`status-pill ${statusTone(geometryResponse?.status)}`}>{geometryResponse?.status || 'idle'}</span>
                <span className={`status-pill ${statusTone(geometryResponse?.cache)}`}>{geometryResponse?.cache || 'n/a'}</span>
              </div>
            </div>
            <div className="viewer-wrap">
                <ViewerStage modelUrl={modelUrl} viewerMessage={viewerMessage} params={paramDraft} annotations={geometryResponse?.annotations || []} />
              {modelUrl ? (
                <DimensionPanel
                  params={paramDraft}
                  onParamChange={(key, value) =>
                    setParamDraft((current) => ({ ...current, [key]: numberLike(value) }))
                  }
                  dirty={paramDirty}
                  onApply={runGenerateFlow}
                  onReset={resetParamDraft}
                  busy={busy}
                />
              ) : null}
              {busy && modelUrl ? <div className="viewer-spinner">Loading\u2026</div> : null}
            </div>
            <div className="viewer-footer">
              <span>Last updated: {lastUpdatedAt || '-'}</span>
              {geometryResponse?.artifact?.url ? (
                <a href={modelUrl} target="_blank" rel="noreferrer">
                  Open GLB
                </a>
              ) : null}
            </div>
          </section>

          <section className="diagnostics-panel">
            <div className="tab-row">
              {TABS.map((tab) => (
                <button
                  key={tab}
                  type="button"
                  className={`tab-button ${activeTab === tab ? 'active' : ''}`}
                  onClick={() => setActiveTab(tab)}
                >
                  {tab}
                </button>
              ))}
            </div>

            <div className="diagnostic-content">
              {activeTab === 'artifact' ? (
                <div className="artifact-grid">
                  <div className="metric-card">
                    <span>Artifact URL</span>
                    <strong>{geometryResponse?.artifact?.url || '-'}</strong>
                  </div>
                  <div className="metric-card">
                    <span>Hash URL</span>
                    <strong>{geometryResponse?.hash_url || '-'}</strong>
                  </div>
                  <div className="metric-card">
                    <span>File Size</span>
                    <strong>{geometryResponse?.artifact?.file_size || '-'}</strong>
                  </div>
                  <div className="metric-card">
                    <span>Job ID</span>
                    <strong>{geometryResponse?.job_id || '-'}</strong>
                  </div>
                </div>
              ) : null}

              {activeTab === 'request' ? <pre className="json-block">{toJson(requestPayload)}</pre> : null}
              {activeTab === 'response' ? <pre className="json-block">{toJson(geometryResponse)}</pre> : null}
              {activeTab === 'job' ? <pre className="json-block">{toJson(jobResponse)}</pre> : null}

              {activeTab === 'platform' ? (
                <div className="platform-grid">
                  <div className="platform-column">
                    <h3>Health</h3>
                    <pre className="json-block compact">{toJson(health)}</pre>
                    <h3>Ready</h3>
                    <pre className="json-block compact">{toJson(ready)}</pre>
                  </div>
                  <div className="platform-column">
                    <h3>Metrics Snapshot</h3>
                    <div className="metric-summary">
                      <div className="metric-card">
                        <span>Requests</span>
                        <strong>{metricValue(metrics, 'cad_platform_requests_total')}</strong>
                      </div>
                      <div className="metric-card">
                        <span>Cache Hits</span>
                        <strong>{metricValue(metrics, 'cad_platform_cache_hits_total')}</strong>
                      </div>
                      <div className="metric-card">
                        <span>Cache Misses</span>
                        <strong>{metricValue(metrics, 'cad_platform_cache_misses_total')}</strong>
                      </div>
                      <div className="metric-card">
                        <span>Jobs Queued</span>
                        <strong>{metricValue(metrics, 'cad_platform_jobs_queued_total')}</strong>
                      </div>
                    </div>
                    <pre className="json-block compact metrics-block">{metrics || ''}</pre>
                  </div>
                </div>
              ) : null}

              {activeTab === 'ingest' ? (
                <DrawingIngestForm apiBase={apiBase} defaultProductId={selectedProductId} />
              ) : null}
            </div>
          </section>

          {errorText ? <section className="error-strip">{errorText}</section> : null}
        </section>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
