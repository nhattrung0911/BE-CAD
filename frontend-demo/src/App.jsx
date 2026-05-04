import React, { Suspense, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useThree } from '@react-three/fiber';
import { Bounds, Environment, Html, OrbitControls, useGLTF } from '@react-three/drei';
import './style.css';

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

const PRODUCT_NOTES = {
  'hex-bolt-iso4014': {
    reference: 'Global Fastener category: Bolts & Studs / Hex Bolts & Screws',
    demoSource: 'Backend generated CadQuery GLB',
  },
  'washer-iso7089': {
    reference: 'Global Fastener category: Washers & Retaining Rings / Plain Washers',
    demoSource: 'Backend generated CadQuery GLB',
  },
  'retaining-ring-gb891': {
    reference: 'Global Fastener category: Washers & Retaining Rings / Retaining Rings',
    demoSource: 'Backend generated CadQuery GLB',
  },
  'hex-bolt-din931': {
    reference: 'Global Fastener category: Bolts & Studs / Hex Bolts & Screws',
    demoSource: 'Backend generated CadQuery GLB',
  },
  'washer-din125': {
    reference: 'Global Fastener category: Washers & Retaining Rings / Plain Washers',
    demoSource: 'Backend generated CadQuery GLB',
  },
};

function flattenVariantGroups(groups) {
  return Object.values(groups || {}).flat();
}

function FastenerModel({ url }) {
  const gltf = useGLTF(url);
  return <primitive object={gltf.scene} />;
}

function Scene({ modelUrl }) {
  const { camera } = useThree();

  useEffect(() => {
    camera.position.set(34, 26, 36);
  }, [camera]);

  return (
    <>
      <ambientLight intensity={0.8} />
      <directionalLight position={[18, 22, 16]} intensity={2} />
      <directionalLight position={[-10, -8, -12]} intensity={0.6} />
      <Environment preset="studio" />
      <Bounds fit clip observe margin={1.22}>
        <Suspense fallback={<Html center>Loading 3D model</Html>}>
          {modelUrl ? <FastenerModel key={modelUrl} url={modelUrl} /> : null}
        </Suspense>
      </Bounds>
      <OrbitControls makeDefault enableDamping dampingFactor={0.08} />
    </>
  );
}

function numberFromInput(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function App() {
  const [variants, setVariants] = useState([]);
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [selectedVariantId, setSelectedVariantId] = useState('');
  const [geometry, setGeometry] = useState(null);
  const [customParams, setCustomParams] = useState({});
  const [status, setStatus] = useState('loading products');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    fetch(`${API}/api/v1/products`)
      .then((response) => {
        if (!response.ok) throw new Error(`Products request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (!active) return;
        setProducts(payload);
        setSelectedProductId(payload[0]?.product_id || '');
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message);
        setStatus('error');
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!selectedProductId) return;
    let active = true;
    setStatus('loading variants');
    setVariants([]);
    setSelectedVariantId('');
    setGeometry(null);
    setCustomParams({});
    fetch(`${API}/api/v1/products/${selectedProductId}/variants`)
      .then((response) => {
        if (!response.ok) throw new Error(`Variants request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (!active) return;
        const nextVariants = flattenVariantGroups(payload.grouped_by_diameter);
        setVariants(nextVariants);
        setSelectedVariantId(nextVariants[0]?.variant_id || '');
        setStatus('ready');
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message);
        setStatus('error');
      });
    return () => {
      active = false;
    };
  }, [selectedProductId]);

  const selectedProduct = products.find((product) => product.product_id === selectedProductId);
  const selectedVariant = variants.find((variant) => variant.variant_id === selectedVariantId);

  useEffect(() => {
    if (!selectedVariant) return;
    setCustomParams(selectedVariant.params || {});
  }, [selectedVariant]);

  useEffect(() => {
    if (!selectedVariantId) return;
    let active = true;
    setStatus('generating selected size');
    setError('');
    setGeometry(null);
    fetch(`${API}/api/v1/geometry/variant/${selectedVariantId}?lod=medium`)
      .then((response) => {
        if (!response.ok) throw new Error(`Geometry request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        if (!active) return;
        setGeometry(payload);
        setStatus(payload.status);
      })
      .catch((err) => {
        if (!active) return;
        setError(err.message);
        setStatus('error');
      });
    return () => {
      active = false;
    };
  }, [selectedVariantId]);

  const modelUrl = useMemo(() => {
    if (!geometry?.hash_url) return '';
    return `${API}${geometry.hash_url}`;
  }, [geometry]);

  const parameterSpecs = selectedProduct?.parameters || [];
  const note = PRODUCT_NOTES[selectedProductId];

  function updateCustomParam(name, value) {
    setCustomParams((current) => ({ ...current, [name]: numberFromInput(value) }));
  }

  function generateCustomGeometry(event) {
    event?.preventDefault();
    if (!selectedProductId) return;
    setStatus('generating custom dimensions');
    setError('');
    setGeometry(null);
    fetch(`${API}/api/v1/geometry/generate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        product_id: selectedProductId,
        params: customParams,
        lod: 'medium',
        format: 'glb',
      }),
    })
      .then((response) => {
        if (!response.ok) throw new Error(`Custom geometry request failed: ${response.status}`);
        return response.json();
      })
      .then((payload) => {
        setGeometry(payload);
        setStatus(payload.status);
      })
      .catch((err) => {
        setError(err.message);
        setStatus('error');
      });
  }

  return (
    <main className="app-shell">
      <section className="toolbar">
        <div>
          <h1>Fastener CAD BE Demo</h1>
          <p>Five backend-generated GLB examples with OrbitControls, dimensions, and custom size generation.</p>
        </div>
        <div className="controls">
          <label>
            Product
            <select value={selectedProductId} onChange={(event) => setSelectedProductId(event.target.value)}>
              {products.map((product) => (
                <option key={product.product_id} value={product.product_id}>
                  {product.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Size
            <select value={selectedVariantId} onChange={(event) => setSelectedVariantId(event.target.value)}>
              {variants.map((variant) => (
                <option key={variant.variant_id} value={variant.variant_id}>
                  {variant.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </section>

      <section className="product-strip">
        {products.map((product) => (
          <button
            className={product.product_id === selectedProductId ? 'product-tab active' : 'product-tab'}
            key={product.product_id}
            onClick={() => setSelectedProductId(product.product_id)}
            type="button"
          >
            <span>{product.standard}</span>
            {product.name}
          </button>
        ))}
      </section>

      <section className="viewer-grid">
        <div className="viewer">
          <Canvas camera={{ position: [34, 26, 36], fov: 42 }}>
            <Scene modelUrl={modelUrl} />
          </Canvas>
        </div>
        <aside className="details">
          <h2>{selectedVariant?.sku || selectedProduct?.name || 'No product'}</h2>
          <dl className="summary">
            <div>
              <dt>Status</dt>
              <dd>{status}</dd>
            </div>
            <div>
              <dt>Geometry source</dt>
              <dd>{geometry?.source || '-'}</dd>
            </div>
            <div>
              <dt>Reference</dt>
              <dd>{note?.reference || '-'}</dd>
            </div>
          </dl>

          <h3>Dimensions</h3>
          <table className="dimension-table">
            <tbody>
              {parameterSpecs.map((spec) => (
                <tr key={spec.name}>
                  <th>{spec.name}</th>
                  <td>{spec.label}</td>
                  <td>{customParams[spec.name] ?? '-'}</td>
                  <td>{spec.unit}</td>
                </tr>
              ))}
            </tbody>
          </table>

          <form className="dimension-form" onSubmit={generateCustomGeometry}>
            <h3>Custom size</h3>
            <div className="field-grid">
              {parameterSpecs.map((spec) => (
                <label key={spec.name}>
                  {spec.name}
                  <input
                    min="0"
                    step="0.1"
                    type="number"
                    value={customParams[spec.name] ?? ''}
                    onChange={(event) => updateCustomParam(spec.name, event.target.value)}
                  />
                </label>
              ))}
            </div>
            <button className="primary-action" onClick={generateCustomGeometry} type="button">
              Generate custom GLB
            </button>
          </form>

          <dl className="summary">
            <div>
              <dt>Hash URL</dt>
              <dd>{geometry?.hash_url || '-'}</dd>
            </div>
            <div>
              <dt>Demo source</dt>
              <dd>{note?.demoSource || '-'}</dd>
            </div>
          </dl>
          {modelUrl ? (
            <a className="asset-link" href={modelUrl} target="_blank" rel="noreferrer">
              Open generated GLB
            </a>
          ) : null}
          {error ? <p className="error">{error}</p> : null}
        </aside>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
