/**
 * Saved-places client functions.
 *
 * The behaviour that matters is not "fetch was called" but what the caller
 * gets back: a real backend list, an empty list when nothing is saved, and an
 * empty list when the backend is unreachable. The last one is the honesty
 * contract - a bookmark the server does not know about must not be shown as
 * though it were saved, and a failed save must not be reported as saved.
 *
 * `client.ts` requests relative URLs (`/api/v1/...`), which is correct in a
 * browser but unparseable by Node's fetch under jsdom, so the mock resolves
 * them against the document base before deciding.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const fetchMock = vi.fn();

vi.stubGlobal(
  'fetch',
  vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    // `client.ts` asks for relative URLs, which is correct in a browser. jsdom
    // hands those to Node's fetch as-is, and Node refuses them, so resolve
    // only the relative ones against the document base.
    let url = typeof input === 'string' ? input : input.toString();
    if (url.startsWith('/')) {
      url = new URL(url, 'http://localhost:5173/').toString();
    }
    return fetchMock(url, init);
  }),
);

import { getClientId, getSavedPlaces, removeSavedPlace, savePlace } from './client';

function jsonResponse(body: unknown, status = 200): Response {
  return { ok: status >= 200 && status < 300, status, json: async () => body } as Response;
}

const CLIENT_ID_HEADER = 'X-Client-Id';

function lastCall(): { url: string; init: RequestInit | undefined } {
  const calls = fetchMock.mock.calls as unknown as [string, RequestInit | undefined][];
  const last = calls[calls.length - 1];
  if (!last) throw new Error('no fetch call recorded');
  const [url, init] = last;
  return { url, init };
}

beforeEach(() => {
  fetchMock.mockReset();
  window.localStorage.clear();
});

describe('getSavedPlaces', () => {
  it('returns the places the backend has saved for this client', async () => {
    const saved = [{ id: 'IN-OD-29', canonical_name: 'Khordha' }];
    fetchMock.mockResolvedValue(jsonResponse(saved));

    await expect(getSavedPlaces()).resolves.toEqual(saved);
  });

  it('returns an empty list when nothing is saved yet', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await expect(getSavedPlaces()).resolves.toEqual([]);
  });

  it('returns an empty list when the backend is unreachable', async () => {
    // An offline reader must not be shown bookmarks the server does not have,
    // so a failed fetch resolves to "nothing saved" rather than throwing into
    // the page's error path.
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(getSavedPlaces()).resolves.toEqual([]);
  });

  it('scopes the request to this browser id', async () => {
    fetchMock.mockResolvedValue(jsonResponse([]));

    await getSavedPlaces();

    const { url, init } = lastCall();
    expect(url).toContain('/saved-places');
    expect((init?.headers as Record<string, string>)[CLIENT_ID_HEADER]).toBe(getClientId());
  });
});

describe('savePlace', () => {
  const place = { id: 'IN-OD-29', canonical_name: 'Khordha' } as never;

  it('sends the whole place and the browser id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(place, 201));

    await savePlace(place);

    const { url, init } = lastCall();
    expect(url).toContain('/saved-places');
    expect(init?.method).toBe('POST');
    expect(JSON.parse(init?.body as string)).toEqual(place);
    expect((init?.headers as Record<string, string>)[CLIENT_ID_HEADER]).toBe(getClientId());
  });

  it('resolves when the backend already had the place', async () => {
    // Saving twice is idempotent server-side: a 200 means "it is saved", and
    // the caller treats that exactly like a 201.
    fetchMock.mockResolvedValue(jsonResponse(place, 200));

    await expect(savePlace(place)).resolves.toBeUndefined();
  });

  it('rejects when the backend refuses the save', async () => {
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'nope' }, 500));

    await expect(savePlace(place)).rejects.toBeDefined();
  });

  it('rejects when the backend is unreachable', async () => {
    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'));

    await expect(savePlace(place)).rejects.toBeDefined();
  });
});

describe('removeSavedPlace', () => {
  it('sends a DELETE scoped to the browser id', async () => {
    fetchMock.mockResolvedValue(jsonResponse(null, 204));

    await removeSavedPlace('IN-OD-29');

    const { url, init } = lastCall();
    expect(url).toContain('/saved-places/IN-OD-29');
    expect(init?.method).toBe('DELETE');
    expect((init?.headers as Record<string, string>)[CLIENT_ID_HEADER]).toBe(getClientId());
  });

  it('rejects when the place was not saved', async () => {
    // A 404 means the bookmark was already gone. Surfacing it lets the caller
    // decide; swallowing it would report a removal that never happened.
    fetchMock.mockResolvedValue(jsonResponse({ detail: 'not saved' }, 404));

    await expect(removeSavedPlace('IN-OD-29')).rejects.toBeDefined();
  });

  it('encodes the place id into the path', async () => {
    fetchMock.mockResolvedValue(jsonResponse(null, 204));

    await removeSavedPlace('IN/OD 29');

    expect(lastCall().url).toContain('/saved-places/IN%2FOD%2029');
  });
});

describe('getClientId', () => {
  it('issues the same id on every call', () => {
    expect(getClientId()).toBe(getClientId());
  });

  it('keeps one id per browser profile', () => {
    const first = getClientId();
    // A second profile (separate storage) gets its own namespace, so one
    // visitor's bookmarks are not another's.
    window.localStorage.clear();

    expect(getClientId()).not.toBe(first);
    expect(getClientId()).toBe(getClientId());
  });

  it('does not collide across many ids', () => {
    const ids = new Set<string>();
    for (let i = 0; i < 50; i += 1) {
      window.localStorage.clear();
      ids.add(getClientId());
    }
    expect(ids.size).toBe(50);
  });
});
