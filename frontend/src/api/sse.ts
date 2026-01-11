/**
 * SSE helper for subscribing to eval run event streams.
 *
 * Wraps the browser's EventSource API with typed callbacks for each event type.
 */

import type {
  AllCompleteEvent,
  ComparisonResultEvent,
  CompleteEvent,
  ConfigCompleteEvent,
  ErrorEvent,
  ProgressEvent,
  ResultEvent,
} from "./types";

export interface EvalStreamCallbacks {
  onProgress?: (data: ProgressEvent) => void;
  onResult?: (data: ResultEvent) => void;
  onComplete?: (data: CompleteEvent) => void;
  onError?: (data: ErrorEvent) => void;
  onDisconnect?: () => void;
}

/**
 * Subscribe to the SSE stream for an eval run.
 *
 * Returns a cleanup function that closes the EventSource connection.
 */
export function subscribeToEvalStream(
  runId: string,
  callbacks: EvalStreamCallbacks
): () => void {
  const url = `/api/v1/eval/run/${runId}/stream`;
  const source = new EventSource(url);

  source.addEventListener("progress", (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as ProgressEvent;
      callbacks.onProgress?.(data);
    } catch {
      console.error("Failed to parse progress event", e.data);
    }
  });

  source.addEventListener("result", (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as ResultEvent;
      callbacks.onResult?.(data);
    } catch {
      console.error("Failed to parse result event", e.data);
    }
  });

  source.addEventListener("complete", (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as CompleteEvent;
      callbacks.onComplete?.(data);
      source.close();
    } catch {
      console.error("Failed to parse complete event", e.data);
    }
  });

  source.addEventListener("error", (e: MessageEvent) => {
    // EventSource error can be a real event with data or a connection error
    if (e.data) {
      try {
        const data = JSON.parse(e.data) as ErrorEvent;
        callbacks.onError?.(data);
      } catch {
        callbacks.onError?.({ message: e.data });
      }
    } else {
      // Connection error — EventSource will auto-reconnect
      callbacks.onDisconnect?.();
    }
  });

  // Handle connection error (source.onerror fires on disconnect)
  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) {
      callbacks.onDisconnect?.();
    }
  };

  return () => {
    source.close();
  };
}

// ---------------------------------------------------------------------------
// Comparison stream subscriber
// ---------------------------------------------------------------------------

export interface ComparisonStreamCallbacks {
  onResult?: (data: ComparisonResultEvent) => void;
  onConfigComplete?: (data: ConfigCompleteEvent) => void;
  onAllComplete?: (data: AllCompleteEvent) => void;
  onError?: (data: ErrorEvent) => void;
  onDisconnect?: () => void;
}

/**
 * Subscribe to the SSE stream for a comparison eval.
 *
 * Returns a cleanup function that closes the EventSource connection.
 */
export function subscribeToComparisonStream(
  comparisonId: string,
  callbacks: ComparisonStreamCallbacks
): () => void {
  const url = `/api/v1/eval/compare/${comparisonId}/stream`;
  const source = new EventSource(url);

  source.addEventListener("result", (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as ComparisonResultEvent;
      callbacks.onResult?.(data);
    } catch {
      console.error("Failed to parse comparison result event", e.data);
    }
  });

  source.addEventListener("config_complete", (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as ConfigCompleteEvent;
      callbacks.onConfigComplete?.(data);
    } catch {
      console.error("Failed to parse config_complete event", e.data);
    }
  });

  source.addEventListener("all_complete", (e: MessageEvent) => {
    try {
      const data = JSON.parse(e.data) as AllCompleteEvent;
      callbacks.onAllComplete?.(data);
      source.close();
    } catch {
      console.error("Failed to parse all_complete event", e.data);
    }
  });

  source.addEventListener("error", (e: MessageEvent) => {
    if (e.data) {
      try {
        const data = JSON.parse(e.data) as ErrorEvent;
        callbacks.onError?.(data);
      } catch {
        callbacks.onError?.({ message: e.data });
      }
    } else {
      callbacks.onDisconnect?.();
    }
  });

  source.onerror = () => {
    if (source.readyState === EventSource.CLOSED) {
      callbacks.onDisconnect?.();
    }
  };

  return () => {
    source.close();
  };
}
