import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Kept separate from vite.config.ts on purpose: that config copies Cesium's
// runtime assets into public/ on every start, which tests do not need.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    restoreMocks: true,
    // `?raw` on a stylesheet otherwise resolves to an empty string: Vite's CSS
    // pipeline claims the import before the raw loader sees it. Enabling CSS
    // processing lets `index.css?raw` carry the real source, which
    // `contrast.test.ts` and `a11y.test.tsx` read to audit the palette.
    css: true,
  },
});
