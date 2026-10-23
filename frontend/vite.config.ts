import { cpSync, existsSync, mkdirSync, rmSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { defineConfig, type Plugin } from 'vite';
import react from '@vitejs/plugin-react';

const CESIUM_BUILD = fileURLToPath(new URL('./node_modules/cesium/Build/Cesium', import.meta.url));
const CESIUM_PUBLIC = fileURLToPath(new URL('./public/cesium', import.meta.url));
const CESIUM_ASSET_DIRS = ['Workers', 'ThirdParty', 'Assets', 'Widgets'];

// Copies Cesium's runtime assets into public/cesium (gitignored) so the lazy
// globe chunk can load workers/widgets from /cesium/ without a bundler plugin.
// Runs in `config` (before the dev server builds its public-dir middleware) so a
// fresh clone works on the first start.
// ponytail: full copy on every start; swap for a hashed CDN build if startup latency matters.
function cesiumAssets(): Plugin {
  return {
    name: 'garuda-cesium-assets',
    config() {
      if (!existsSync(CESIUM_BUILD)) return;
      rmSync(CESIUM_PUBLIC, { recursive: true, force: true });
      mkdirSync(CESIUM_PUBLIC, { recursive: true });
      for (const dir of CESIUM_ASSET_DIRS) {
        cpSync(path.join(CESIUM_BUILD, dir), path.join(CESIUM_PUBLIC, dir), { recursive: true });
      }
    },
  };
}

export default defineConfig({
  plugins: [react(), cesiumAssets()],
  server: {
    port: 5173,
    // The proxy below only exists on this server, so a silent move to 5174
    // would leave /api unreachable. Fail loudly instead; `make dev` frees the
    // port before starting.
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  preview: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/health': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
});
