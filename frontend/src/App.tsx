import React, { Suspense, lazy } from 'react';
import { HomePage } from './pages/HomePage';

// Opt-in 3D-terrain POC. Lazy so Cesium never enters the default MapLibre bundle.
const GlobePage = lazy(() => import('./pages/GlobePage'));

export const App: React.FC = () => {
  const showGlobe = new URLSearchParams(window.location.search).get('globe') === '1';

  if (showGlobe) {
    return (
      <Suspense
        fallback={
          <div style={{ padding: 24, fontFamily: 'inherit', color: '#f3f4f6' }}>Loading 3D globe…</div>
        }
      >
        <GlobePage />
      </Suspense>
    );
  }

  return <HomePage />;
};

export default App;
