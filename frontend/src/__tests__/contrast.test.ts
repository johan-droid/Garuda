/**
 * Contrast regression guard for the shipped palette.
 *
 * jsdom cannot measure contrast: it returns the initial `canvastext` for any
 * element and does not apply stylesheet rules, so axe's color-contrast rule
 * throws (`_isIconLigature`) rather than reporting. That is why the axe run in
 * `a11y.test.tsx` disables that one rule, and why contrast is checked here
 * instead - against the values the stylesheet actually declares, computed with
 * the WCAG 2.1 relative-luminance formula.
 *
 * This is a characterisation test over existing values, not a new behaviour:
 * an audit of every `color:` declaration against every background token found
 * no WCAG AA failure. The value is that a future palette change that drops
 * below 4.5:1 now fails here instead of shipping.
 */
import { describe, expect, it } from 'vitest';

import indexCss from '../styles/index.css?raw';

/** WCAG 2.1 relative luminance, then the contrast ratio between two colours. */
function relativeLuminance([r, g, b]: [number, number, number]): number {
  const channel = (v: number) => {
    const s = v / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastRatio(a: [number, number, number], b: [number, number, number]): number {
  const [lighter, darker] = [relativeLuminance(a), relativeLuminance(b)].sort((x, y) => y - x);
  return (lighter + 0.05) / (darker + 0.05);
}

function hexToRgb(hex: string): [number, number, number] {
  const c = hex.replace('#', '');
  const full = c.length === 3 ? c.split('').map((x) => x + x).join('') : c;
  return [0, 2, 4].map((i) => parseInt(full.slice(i, i + 2), 16)) as [
    number,
    number,
    number,
  ];
}

/** The `:root` custom properties, resolved to concrete colours. */
function rootVariables(): Map<string, string> {
  const root = indexCss.match(/:root\s*\{([\s\S]*?)\}/);
  expect(root, 'index.css must declare a :root block').toBeTruthy();

  const vars = new Map<string, string>();
  for (const match of root![1].matchAll(/(--[\w-]+)\s*:\s*([^;]+);/g)) {
    vars.set(match[1], match[2].trim());
  }
  return vars;
}

/** Resolve `var(--x)` to its declared value, one level deep. */
function resolve(value: string, vars: Map<string, string>): string {
  const ref = value.match(/var\((--[\w-]+)\)/);
  return ref ? (vars.get(ref[1]) ?? value) : value;
}

/** Every `color:` declaration in the stylesheet, resolved to an rgb triple. */
function declaredTextColours(vars: Map<string, string>): [string, [number, number, number]][] {
  const colours: [string, [number, number, number]][] = [];
  const seen = new Set<string>();

  for (const match of indexCss.matchAll(/(?:^|\s)color\s*:\s*([^;}]+)[;}]/g)) {
    const raw = match[1].trim();
    const value = resolve(raw, vars);
    if (!value.startsWith('#')) continue;
    if (seen.has(value)) continue;
    seen.add(value);
    colours.push([raw, hexToRgb(value)]);
  }
  return colours;
}

describe('the palette meets WCAG AA contrast', () => {
  const vars = rootVariables();
  const backgrounds = {
    primary: vars.get('--bg-primary'),
    secondary: vars.get('--bg-secondary'),
  };

  it('declares both background tokens it is checked against', () => {
    expect(backgrounds.primary).toBeTruthy();
    expect(backgrounds.secondary).toBeTruthy();
  });

  it('every declared text colour reaches 4.5:1 on both background tokens', () => {
    const failures: string[] = [];

    for (const [raw, fg] of declaredTextColours(vars)) {
      for (const [name, bg] of Object.entries(backgrounds)) {
        const ratio = contrastRatio(fg, hexToRgb(bg!));
        if (ratio < 4.5) {
          failures.push(`${raw} on ${name}: ${ratio.toFixed(2)}:1`);
        }
      }
    }

    expect(failures).toEqual([]);
  });

  it('the muted text token specifically clears AA, as it is the closest call', () => {
    const muted = resolve(vars.get('--text-muted')!, vars);
    const ratio = contrastRatio(hexToRgb(muted), hexToRgb(backgrounds.primary!));
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });

  it('the card surface, composited over the page background, still clears AA', () => {
    // --bg-card is translucent, so a reader sees it over --bg-primary. The
    // composited value is the one that matters, not the raw rgba.
    const card = vars.get('--bg-card');
    expect(card).toContain('rgba(');
    const parts = card!.match(/rgba?\(([^)]+)\)/)![1].split(',').map((s) => parseFloat(s.trim()));
    const [r, g, b, alpha] = parts;
    const over = hexToRgb(backgrounds.primary!);
    const composited: [number, number, number] = [0, 1, 2].map((i) =>
      Math.round([r, g, b][i] * alpha + over[i] * (1 - alpha)),
    ) as [number, number, number];

    const muted = resolve(vars.get('--text-muted')!, vars);
    expect(contrastRatio(hexToRgb(muted), composited)).toBeGreaterThanOrEqual(4.5);
  });
});
