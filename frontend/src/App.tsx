import React, { Suspense, lazy } from 'react';
import { HomePage } from './pages/HomePage';

// Globe is the default landing experience. Lazy-loaded so Cesium never enters
// the 2D-map bundle path.
const GlobePage = lazy(() => import('./pages/GlobePage'));

function GlobeLoadingFallback() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        height: '100vh',
        background: '#0a0e17',
        color: '#9ca3af',
        fontFamily: 'inherit',
        fontSize: '0.9rem',
      }}
    >
      Loading Garuda Globe…
    </div>
  );
}

export const App: React.FC = () => {
  const params = new URLSearchParams(window.location.search);
  // ?map=1 → 2D MapView  |  ?globe=1 → globe (legacy compat)  |  default → globe
  const show2DMap = params.get('map') === '1';
  const showGlobe = !show2DMap;

  if (showGlobe) {
    return (
      <Suspense fallback={<GlobeLoadingFallback />}>
        <GlobePage />
      </Suspense>
    );
  }

  return <HomePage />;
};

export default App;

