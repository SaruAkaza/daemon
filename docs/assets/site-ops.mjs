/**
 * Daemon Tools — Frontend Operational Client (ES Module)
 * Connects to Ops Controller via same-origin HttpOnly session cookie.
 * Zero token storage in browser JS, Web Storage, or query params.
 */

export class OpsClient {
  constructor({ baseUrl = '', fetchFn = null, EventSourceClass = null } = {}) {
    this.baseUrl = baseUrl.replace(/\/$/, '');
    this.fetch = fetchFn || (typeof window !== 'undefined' ? window.fetch.bind(window) : null);
    this.EventSource = EventSourceClass || (typeof window !== 'undefined' ? window.EventSource : null);
  }

  async fetchSnapshot() {
    const res = await this.fetch(`${this.baseUrl}/api/ops/snapshot`, {
      method: 'GET',
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json',
      },
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch ops snapshot: ${res.status}`);
    }
    return res.json();
  }

  async fetchCommands() {
    const res = await this.fetch(`${this.baseUrl}/api/ops/commands`, {
      method: 'GET',
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json',
      },
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch commands: ${res.status}`);
    }
    return res.json();
  }

  async fetchReviews() {
    const res = await this.fetch(`${this.baseUrl}/api/ops/reviews`, {
      method: 'GET',
      credentials: 'same-origin',
      headers: {
        'Accept': 'application/json',
      },
    });
    if (!res.ok) {
      throw new Error(`Failed to fetch reviews: ${res.status}`);
    }
    return res.json();
  }

  async submitCommand({
    commandId,
    commandType,
    bookId = null,
    reviewId = null,
    payload = {},
    reason = '',
    operatorId = '',
    confirmation = { confirmed: false },
  }) {
    const cid = commandId || `CMD-${Date.now()}-${Math.random().toString(36).substring(2, 10)}`;
    const body = {
      commandId: cid,
      commandType,
      payload,
      reason,
      operatorId,
      confirmation,
    };
    if (bookId) body.bookId = bookId;
    if (reviewId) body.reviewId = reviewId;

    const res = await this.fetch(`${this.baseUrl}/api/ops/commands`, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify(body),
    });

    const data = await res.json().catch(() => null);
    if (!res.ok) {
      const err = new Error(data?.error || `Command submission failed with code ${res.status}`);
      err.status = res.status;
      err.data = data;
      throw err;
    }
    return data;
  }

  connectEvents({ onEvent, onSnapshotRequired, onError }) {
    if (!this.EventSource) {
      return { close: () => {} };
    }

    const source = new this.EventSource(`${this.baseUrl}/api/ops/events`);

    const handleMessage = (e) => {
      try {
        const payload = JSON.parse(e.data);
        if (onEvent) onEvent(payload);
      } catch (err) {
        // ignore parse errors
      }
    };

    source.addEventListener('message', handleMessage);
    source.addEventListener('command_updated', handleMessage);
    source.addEventListener('review_updated', handleMessage);
    source.addEventListener('stage_invalidated', handleMessage);

    source.addEventListener('snapshot_required', () => {
      if (onSnapshotRequired) {
        onSnapshotRequired();
      }
    });

    if (onError) {
      source.onerror = onError;
    }

    return {
      source,
      close: () => source.close(),
    };
  }
}
