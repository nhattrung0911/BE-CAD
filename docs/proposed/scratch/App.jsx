/**
 * frontend-demo/src/App.jsx
 *
 * mecsu.vn Fastener 3D Viewer Demo
 * ─────────────────────────────────────────────────────────────────────
 * Features:
 *   • OrbitControls — kéo xoay, scroll zoom, right-click pan
 *   • LOD progressive loading — low ngay, upgrade medium khi stable
 *   • Dimension annotations — mũi tên + label d, L, s hiển thị trên canvas
 *   • Size selector — grouped by diameter, shows all lengths per diameter
 *   • Product tabs — hex_bolt | hex_nut | washer
 *   • Specs panel — hiển thị params kỹ thuật kèm đơn vị ISO
 *   • Polling — nếu status=queued, auto-poll job đến khi ready
 *   • Error boundary — không crash toàn trang khi model lỗi
 *   • Material PBR — metalness 0.9, roughness 0.2 (inox / carbon steel)
 *
 * Deps: three, @react-three/fiber, @react-three/drei
 * ─────────────────────────────────────────────────────────────────────
 */

import React, {
  Suspense, useCallback, useEffect, useMemo, useRef, useState,
} from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useThree } from '@react-three/fiber';
import {
  Bounds, Environment, Html, Line, OrbitControls,
  Text, useGLTF,
} from '@react-three/drei';
import * as THREE from 'three';
import './style.css';

/* ── Config ─────────────────────────────────────────────────────── */
const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
const POLL_INTERVAL_MS = 2000;
const LOD_UPGRADE_DELAY_MS = 600;

/* ── Helpers ─────────────────────────────────────────────────────── */
function flatVariants(grouped) {
  return Object.values(grouped || {}).flat();
}

function fmtParam(key, val) {
  const units = { d: 'mm', L: 'mm', P: 'mm', k: 'mm', s: 'mm', b: 'mm',
                  m: 'mm', OD: 'mm', ID: 'mm', h: 'mm' };
  return `${val}${units[key] || ''}`;
}

const PARAM_LABELS = {
  d: 'Đường kính (d)',
  L: 'Chiều dài (L)',
  P: 'Bước ren (P)',
  k: 'Cao đầu (k)',
  s: 'Rộng 2 cạnh (s)',
  b: 'Dài ren (b)',
  m: 'Cao đai ốc (m)',
  OD: 'Đường kính ngoài',
  ID: 'Đường kính trong',
  h: 'Chiều dày (h)',
};

/* ── PBR Material ─────────────────────────────────────────────────── */
const MATERIALS = {
  carbon_steel:   { color: '#6B6B6B', metalness: 0.85, roughness: 0.35 },
  stainless_304:  { color: '#C0C0C0', metalness: 0.92, roughness: 0.18 },
  stainless_316:  { color: '#D0D0D0', metalness: 0.92, roughness: 0.15 },
  alloy_steel:    { color: '#555555', metalness: 0.9,  roughness: 0.3  },
  default:        { color: '#AAAAAA', metalness: 0.88, roughness: 0.22 },
};

function applyMaterial(scene, materialKey) {
  const mat = MATERIALS[materialKey] || MATERIALS.default;
  const pbrMat = new THREE.MeshStandardMaterial(mat);
  scene.traverse((child) => {
    if (child.isMesh) {
      child.material = pbrMat;
      child.castShadow = true;
      child.receiveShadow = true;
    }
  });
}

/* ── Dimension Arrow Component ────────────────────────────────────── */
function DimArrow({ from, to, label, color = '#FFD700' }) {
  const mid = useMemo(() => {
    const v = new THREE.Vector3();
    v.lerpVectors(
      new THREE.Vector3(...from),
      new THREE.Vector3(...to),
      0.5,
    );
    return [v.x, v.y, v.z];
  }, [from, to]);

  return (
    <group>
      <Line
        points={[from, to]}
        color={color}
        lineWidth={1.5}
        dashed={false}
      />
      {/* Arrow heads — small cones */}
      <mesh position={from} rotation={[0, 0, Math.PI / 2]}>
        <coneGeometry args={[0.3, 0.8, 8]} />
        <meshBasicMaterial color={color} />
      </mesh>
      <mesh position={to} rotation={[0, 0, -Math.PI / 2]}>
        <coneGeometry args={[0.3, 0.8, 8]} />
        <meshBasicMaterial color={color} />
      </mesh>
      <Text
        position={mid}
        fontSize={1.4}
        color={color}
        anchorX="center"
        anchorY="middle"
        outlineWidth={0.05}
        outlineColor="#000"
      >
        {label}
      </Text>
    </group>
  );
}

/* ── Dimension Annotations (computed from params) ─────────────────── */
function DimensionAnnotations({ params, visible }) {
  if (!visible || !params) return null;

  const dims = [];

  // Diameter annotation (horizontal line across shank)
  if (params.d) {
    const r = params.d / 2;
    const z = params.k ? params.k + (params.L - params.k) / 2 : 10;
    dims.push(
      <DimArrow
        key="d"
        from={[-r - 3, 0, z]}
        to={[r + 3, 0, z]}
        label={`d = ${params.d}mm`}
        color="#4FC3F7"
      />,
    );
  }

  // Total length annotation (vertical line beside bolt)
  if (params.L && params.k) {
    const x = (params.s || params.d * 2) / 2 + 4;
    dims.push(
      <DimArrow
        key="L"
        from={[x, 0, 0]}
        to={[x, 0, params.k + params.L]}
        label={`L = ${params.L}mm`}
        color="#A5D6A7"
      />,
    );
  }

  // Head across-flats (for hex bolt / nut)
  if (params.s) {
    const z = params.k ? params.k / 2 : params.m / 2;
    dims.push(
      <DimArrow
        key="s"
        from={[-params.s / 2 - 2, 4, z]}
        to={[params.s / 2 + 2, 4, z]}
        label={`s = ${params.s}mm`}
        color="#FFB74D"
      />,
    );
  }

  // Nut height
  if (params.m && !params.L) {
    dims.push(
      <DimArrow
        key="m"
        from={[params.s / 2 + 4, 0, 0]}
        to={[params.s / 2 + 4, 0, params.m]}
        label={`m = ${params.m}mm`}
        color="#CE93D8"
      />,
    );
  }

  return <group>{dims}</group>;
}

/* ── 3D Model ─────────────────────────────────────────────────────── */
function FastenerModel({ url, material }) {
  const gltf = useGLTF(url);
  const sceneRef = useRef();

  useEffect(() => {
    if (gltf.scene) {
      const clone = gltf.scene.clone(true);
      applyMaterial(clone, material);
      if (sceneRef.current) {
        sceneRef.current.clear();
        sceneRef.current.add(clone);
      }
    }
  }, [gltf.scene, material]);

  return <group ref={sceneRef} />;
}

/* ── Scene ────────────────────────────────────────────────────────── */
function Scene({ modelUrl, params, showDimensions, material }) {
  const { camera, invalidate } = useThree();

  useEffect(() => {
    camera.position.set(50, 38, 55);
    invalidate();
  }, [camera, invalidate]);

  return (
    <>
      <ambientLight intensity={0.6} />
      <directionalLight
        position={[20, 30, 20]}
        intensity={2.5}
        castShadow
        shadow-mapSize-width={1024}
        shadow-mapSize-height={1024}
      />
      <directionalLight position={[-15, -10, -20]} intensity={0.8} />
      <pointLight position={[0, 60, 0]} intensity={0.4} />
      <Environment preset="studio" />

      <Bounds fit clip observe margin={1.4}>
        <Suspense fallback={<Html center><div className="loading-3d">Đang tải 3D...</div></Html>}>
          {modelUrl && (
            <FastenerModel url={modelUrl} material={material} />
          )}
        </Suspense>
      </Bounds>

      {showDimensions && (
        <DimensionAnnotations params={params} visible={showDimensions} />
      )}

      <OrbitControls
        makeDefault
        enableDamping
        dampingFactor={0.07}
        minDistance={5}
        maxDistance={500}
        enablePan
        panSpeed={0.8}
      />
    </>
  );
}

/* ── Error Boundary ──────────────────────────────────────────────── */
class ModelErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(err) {
    return { error: err };
  }

  render() {
    if (this.state.error) {
      return (
        <div className="model-error">
          <span>⚠ Không thể tải model 3D</span>
          <button onClick={() => this.setState({ error: null })}>Thử lại</button>
        </div>
      );
    }
    return this.props.children;
  }
}

/* ── Size Selector ────────────────────────────────────────────────── */
function SizeSelector({ variants, selectedId, onChange }) {
  const grouped = useMemo(() => {
    const g = {};
    for (const v of variants) {
      const key = v.diameter_label || 'Other';
      if (!g[key]) g[key] = [];
      g[key].push(v);
    }
    return g;
  }, [variants]);

  const diameterKeys = Object.keys(grouped).sort((a, b) => {
    const numA = parseFloat(a.replace('M', ''));
    const numB = parseFloat(b.replace('M', ''));
    return numA - numB;
  });

  const [selectedDiam, setSelectedDiam] = useState(
    variants.find((v) => v.variant_id === selectedId)?.diameter_label || diameterKeys[0],
  );

  // Sync selectedDiam when selectedId changes externally
  useEffect(() => {
    const v = variants.find((v) => v.variant_id === selectedId);
    if (v) setSelectedDiam(v.diameter_label);
  }, [selectedId, variants]);

  const currentOptions = grouped[selectedDiam] || [];

  function handleDiamChange(newDiam) {
    setSelectedDiam(newDiam);
    const first = grouped[newDiam]?.[0];
    if (first) onChange(first.variant_id);
  }

  return (
    <div className="size-selector">
      <div className="size-row">
        <label className="size-label">Đường kính</label>
        <div className="diam-pills">
          {diameterKeys.map((k) => (
            <button
              key={k}
              className={`pill ${k === selectedDiam ? 'active' : ''}`}
              onClick={() => handleDiamChange(k)}
            >
              {k}
            </button>
          ))}
        </div>
      </div>

      <div className="size-row">
        <label className="size-label">Kích thước</label>
        <select
          className="size-select"
          value={selectedId}
          onChange={(e) => onChange(e.target.value)}
        >
          {currentOptions.map((v) => (
            <option key={v.variant_id} value={v.variant_id}>
              {v.label} — SKU: {v.sku}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

/* ── Specs Panel ─────────────────────────────────────────────────── */
function SpecsPanel({ variant, geometry }) {
  if (!variant) return null;
  return (
    <div className="specs-panel">
      <h3>{variant.sku}</h3>
      <table className="specs-table">
        <tbody>
          {Object.entries(variant.params || {}).map(([k, v]) => (
            k !== 'lod' && (
              <tr key={k}>
                <td className="spec-key">{PARAM_LABELS[k] || k}</td>
                <td className="spec-val">{fmtParam(k, v)}</td>
              </tr>
            )
          ))}
          <tr>
            <td className="spec-key">Vật liệu</td>
            <td className="spec-val">{variant.material || '—'}</td>
          </tr>
          {geometry && (
            <>
              <tr>
                <td className="spec-key">Nguồn 3D</td>
                <td className="spec-val spec-source">{geometry.source || '—'}</td>
              </tr>
              <tr>
                <td className="spec-key">Cache</td>
                <td className={`spec-val ${geometry.cache === 'hit' ? 'cache-hit' : 'cache-miss'}`}>
                  {geometry.cache === 'hit' ? '✓ HIT' : '● MISS'}
                </td>
              </tr>
            </>
          )}
        </tbody>
      </table>
      {geometry?.artifact && (
        <a
          className="dl-link"
          href={`${API}${geometry.hash_url}`}
          download
        >
          ⬇ Tải file GLB
        </a>
      )}
    </div>
  );
}

/* ── Status Badge ────────────────────────────────────────────────── */
function StatusBadge({ status, lod }) {
  const map = {
    ready: { cls: 'badge-ready', text: `✓ Ready (${lod})` },
    queued: { cls: 'badge-queued', text: '⏳ Đang tạo...' },
    generating: { cls: 'badge-queued', text: '⚙ Generating...' },
    failed: { cls: 'badge-error', text: '✗ Lỗi' },
    loading: { cls: 'badge-loading', text: 'Đang tải...' },
  };
  const { cls, text } = map[status] || { cls: '', text: status };
  return <span className={`badge ${cls}`}>{text}</span>;
}

/* ── Main App ─────────────────────────────────────────────────────── */
function App() {
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [variants, setVariants] = useState([]);
  const [selectedVariantId, setSelectedVariantId] = useState('');
  const [geometry, setGeometry] = useState(null);
  const [status, setStatus] = useState('loading');
  const [lod, setLod] = useState('low');
  const [showDimensions, setShowDimensions] = useState(true);
  const [error, setError] = useState('');
  const pollRef = useRef(null);

  /* Load product list */
  useEffect(() => {
    fetch(`${API}/api/v1/products`)
      .then((r) => r.json())
      .then((data) => {
        setProducts(data);
        if (data[0]) setSelectedProductId(data[0].product_id);
      })
      .catch((e) => setError(e.message));
  }, []);

  /* Load variants when product changes */
  useEffect(() => {
    if (!selectedProductId) return;
    setVariants([]);
    setSelectedVariantId('');
    setGeometry(null);
    setStatus('loading');
    setLod('low');

    fetch(`${API}/api/v1/products/${selectedProductId}/variants`)
      .then((r) => r.json())
      .then((data) => {
        const all = flatVariants(data.grouped_by_diameter);
        setVariants(all);
        if (all[0]) setSelectedVariantId(all[0].variant_id);
      })
      .catch((e) => setError(e.message));
  }, [selectedProductId]);

  /* Fetch geometry and manage LOD upgrade */
  const fetchGeometry = useCallback(async (variantId, lodLevel) => {
    if (!variantId) return;
    setStatus(lodLevel === 'low' ? 'loading' : 'loading');
    setError('');
    try {
      const res = await fetch(
        `${API}/api/v1/geometry/variant/${variantId}?lod=${lodLevel}`,
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      setGeometry(data);
      setStatus(data.status);

      if (data.status === 'queued' && data.job_id) {
        // Poll for completion
        clearInterval(pollRef.current);
        pollRef.current = setInterval(async () => {
          const poll = await fetch(
            `${API}/api/v1/geometry/variant/${variantId}?lod=${lodLevel}`,
          );
          if (poll.ok) {
            const pollData = await poll.json();
            if (pollData.status === 'ready') {
              clearInterval(pollRef.current);
              setGeometry(pollData);
              setStatus('ready');
            }
          }
        }, POLL_INTERVAL_MS);
      }
    } catch (e) {
      setError(e.message);
      setStatus('failed');
    }
  }, []);

  /* Initial load: LOD low, then upgrade to medium */
  useEffect(() => {
    if (!selectedVariantId) return;
    clearInterval(pollRef.current);
    setLod('low');
    fetchGeometry(selectedVariantId, 'low').then(() => {
      // Upgrade to medium after delay (user has orientation, now wants detail)
      const t = setTimeout(() => {
        setLod('medium');
        fetchGeometry(selectedVariantId, 'medium');
      }, LOD_UPGRADE_DELAY_MS);
      return () => clearTimeout(t);
    });
    return () => clearInterval(pollRef.current);
  }, [selectedVariantId, fetchGeometry]);

  const modelUrl = useMemo(() => {
    if (!geometry?.hash_url) return '';
    return `${API}${geometry.hash_url}`;
  }, [geometry]);

  const selectedVariant = useMemo(
    () => variants.find((v) => v.variant_id === selectedVariantId),
    [variants, selectedVariantId],
  );

  const productTabs = products.map((p) => (
    <button
      key={p.product_id}
      className={`tab-btn ${p.product_id === selectedProductId ? 'active' : ''}`}
      onClick={() => setSelectedProductId(p.product_id)}
    >
      {p.name}
    </button>
  ));

  return (
    <div className="app-shell">

      {/* ── Header ──────────────────────────────────────────── */}
      <header className="app-header">
        <div className="brand">mecsu.vn — 3D Viewer Demo</div>
        <div className="header-controls">
          <StatusBadge status={status} lod={lod} />
          {error && <span className="err-badge">⚠ {error}</span>}
        </div>
      </header>

      {/* ── Product Tabs ─────────────────────────────────────── */}
      <div className="tabs-bar">{productTabs}</div>

      {/* ── Main Content ─────────────────────────────────────── */}
      <div className="main-layout">

        {/* ── Left: Controls ─────────────────────────────────── */}
        <aside className="sidebar">
          {variants.length > 0 && (
            <SizeSelector
              variants={variants}
              selectedId={selectedVariantId}
              onChange={setSelectedVariantId}
            />
          )}

          <div className="view-controls">
            <label className="toggle-label">
              <input
                type="checkbox"
                checked={showDimensions}
                onChange={(e) => setShowDimensions(e.target.checked)}
              />
              Hiển thị kích thước
            </label>
            <div className="lod-control">
              <span>Chi tiết (LOD):</span>
              {['low', 'medium', 'high'].map((l) => (
                <button
                  key={l}
                  className={`lod-btn ${lod === l ? 'active' : ''}`}
                  onClick={() => {
                    setLod(l);
                    fetchGeometry(selectedVariantId, l);
                  }}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>

          <SpecsPanel variant={selectedVariant} geometry={geometry} />
        </aside>

        {/* ── Centre: 3D Canvas ───────────────────────────────── */}
        <div className="canvas-wrap">
          <ModelErrorBoundary>
            <Canvas
              shadows
              camera={{ position: [50, 38, 55], fov: 40 }}
              gl={{ antialias: true, alpha: false }}
            >
              <color attach="background" args={['#1a1a2e']} />
              <Scene
                modelUrl={modelUrl}
                params={selectedVariant?.params}
                showDimensions={showDimensions}
                material={selectedVariant?.material || 'default'}
              />
            </Canvas>
          </ModelErrorBoundary>

          <div className="canvas-hint">
            🖱 Kéo: xoay  •  Scroll: zoom  •  Chuột phải: di chuyển
          </div>
        </div>
      </div>
    </div>
  );
}

createRoot(document.getElementById('root')).render(<App />);
