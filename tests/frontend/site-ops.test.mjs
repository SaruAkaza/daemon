import test from 'node:test';
import assert from 'node:assert/strict';
import { OpsClient } from '../../docs/assets/site-ops.mjs';

test('OpsClient initializes without saving tokens to storage or window', () => {
  const fakeWindow = {};
  const fakeStorage = {
    store: {},
    setItem(k, v) { this.store[k] = v; },
    getItem(k) { return this.store[k] || null; },
  };

  const client = new OpsClient({ baseUrl: '', storage: fakeStorage, windowObj: fakeWindow });
  assert.equal(Object.keys(fakeStorage.store).length, 0, 'No tokens stored in storage');
  assert.equal(fakeWindow.token, undefined, 'No token leaked onto window object');
});

test('OpsClient fetchSnapshot calls fetch with credentials: same-origin', async () => {
  let requestedUrl = null;
  let requestedOptions = null;

  const mockFetch = async (url, options) => {
    requestedUrl = url;
    requestedOptions = options;
    return {
      ok: true,
      status: 200,
      async json() {
        return {
          controlState: { pausedBooks: [] },
          commands: [],
          reviews: [],
        };
      },
    };
  };

  const client = new OpsClient({ baseUrl: 'http://127.0.0.1:8080', fetchFn: mockFetch });
  const snapshot = await client.fetchSnapshot();

  assert.equal(requestedUrl, 'http://127.0.0.1:8080/api/ops/snapshot');
  assert.equal(requestedOptions.credentials, 'same-origin');
  assert.deepEqual(snapshot.controlState, { pausedBooks: [] });
});

test('OpsClient submitCommand posts JSON with credentials: same-origin', async () => {
  let requestedUrl = null;
  let requestedOptions = null;

  const mockFetch = async (url, options) => {
    requestedUrl = url;
    requestedOptions = options;
    return {
      ok: true,
      status: 202,
      async json() {
        return {
          commandId: 'CMD-TEST-12345678',
          status: 'ACCEPTED',
        };
      },
    };
  };

  const client = new OpsClient({ baseUrl: '', fetchFn: mockFetch });
  const res = await client.submitCommand({
    commandId: 'CMD-TEST-12345678',
    commandType: 'PAUSE_BOOK',
    bookId: 'trevas-3ed',
    reason: 'Testing client submission',
    operatorId: 'alice',
    confirmation: { confirmed: true },
  });

  assert.equal(requestedUrl, '/api/ops/commands');
  assert.equal(requestedOptions.method, 'POST');
  assert.equal(requestedOptions.credentials, 'same-origin');
  assert.equal(requestedOptions.headers['Content-Type'], 'application/json');
  assert.equal(res.status, 'ACCEPTED');
});

test('OpsClient handles snapshot_required SSE event by invoking onSnapshotRequired', () => {
  let snapshotRequested = false;
  let eventReceived = null;

  // Mock EventSource
  class MockEventSource {
    constructor(url) {
      this.url = url;
      this.listeners = {};
    }
    addEventListener(type, cb) {
      this.listeners[type] = cb;
    }
    simulate(type, data) {
      if (this.listeners[type]) {
        this.listeners[type]({ data: JSON.stringify(data) });
      }
    }
    close() {}
  }

  const client = new OpsClient({ baseUrl: '', EventSourceClass: MockEventSource });
  const connection = client.connectEvents({
    onEvent(ev) {
      eventReceived = ev;
    },
    onSnapshotRequired() {
      snapshotRequested = true;
    },
  });

  // Simulate normal event
  connection.source.simulate('command_updated', { commandId: 'CMD-1' });
  assert.equal(eventReceived.commandId, 'CMD-1');

  // Simulate snapshot_required event
  connection.source.simulate('snapshot_required', { needsSnapshot: true });
  assert.equal(snapshotRequested, true);

  connection.close();
});
