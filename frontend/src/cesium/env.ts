/**
 * Cesium resolves its workers/widgets/assets relative to CESIUM_BASE_URL.
 * This must be a separate module imported *before* `cesium` so that ES module
 * evaluation order sets the global first. Keeping it here (rather than in
 * main.tsx) means the POC can be deleted without touching the app entry point.
 */
declare global {
  interface Window {
    CESIUM_BASE_URL?: string;
  }
}

window.CESIUM_BASE_URL = '/cesium/';

export {};
