import React, { Suspense, useEffect, useMemo, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { Canvas, useThree } from '@react-three/fiber';
import { Bounds, Environment, Html, OrbitControls, useGLTF } from '@react-three/drei';
import './style.css';

const API = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';

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
      <Bounds fit clip observe margin={1.25}>
        <Suspense fallback={<Html center>Loading 3D...</Html>}>
          {modelUrl ? <FastenerModel url={modelUrl} /> : null}
        </Suspense>
      </Bounds>
      <OrbitControls makeDefault enableDamping dampingFactor={0.08} />
    </>
  );
}

function App() {
  const [variants, setVariants] = useState([]);
  const [products, setProducts] = useState([]);
  const [selectedProductId, setSelectedProductId] = useState('');
  const [selectedVariantId, setSelectedVariantId] = useState('');
  const [geometry, setGeometry] = useState(null);
  const [status, setStatus] = useState('loading variants');
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

  useEffect(() => {
    if (!selectedVariantId) return;
    let active = true;
    setStatus('generating geometry');
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

  const selectedVariant = variants.find((variant) => variant.variant_id === selectedVariantId);

  return (
    <main className="app-shell">
      <section className="toolbar">
        <div>
          <h1>Fastener CAD Demo</h1>
          <p>Backend contract viewer for generated GLB output.</p>
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

      <section className="viewer-grid">
        <div className="viewer">
          <Canvas camera={{ position: [34, 26, 36], fov: 42 }}>
            <Scene modelUrl={modelUrl} />
          </Canvas>
        </div>
        <aside className="details">
          <h2>{selectedVariant?.sku || 'No variant'}</h2>
          <dl>
            <div>
              <dt>Status</dt>
              <dd>{status}</dd>
            </div>
            <div>
              <dt>Source</dt>
              <dd>{geometry?.source || '-'}</dd>
            </div>
            <div>
              <dt>Hash URL</dt>
              <dd>{geometry?.hash_url || '-'}</dd>
            </div>
          </dl>
          <pre>{JSON.stringify(selectedVariant?.params || {}, null, 2)}</pre>
          {modelUrl ? (
            <a className="asset-link" href={modelUrl} target="_blank" rel="noreferrer">
              Open GLB
            </a>
          ) : null}
          {error ? <p className="error">{error}</p> : null}
        </aside>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')).render(<App />);
