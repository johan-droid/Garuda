import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './styles/index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

// A caching worker fights the dev server over hot reload, so it is registered
// only outside development. Failing to install one is not a boot failure: the
// app works without it, so a rejection is swallowed rather than surfaced.
if (import.meta.env.MODE !== 'development' && 'serviceWorker' in navigator) {
  navigator.serviceWorker.register('/sw.js').catch(() => {
    // Offline install is a bonus, never a prerequisite.
  });
}
