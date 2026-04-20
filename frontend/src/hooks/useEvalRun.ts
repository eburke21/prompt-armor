/**
 * useEvalRun — React Query wrapper for an eval run's lifecycle state.
 *
 * Encapsulates the invariant: "poll while pending/running UNTIL an SSE stream
 * has begun delivering events, then treat SSE as the source of truth and stop
 * polling." Prior to this extraction the logic lived inline in RunResults.tsx
 * with a redundant poll racing against SSE (I9) and a scattered stale-closure
 * risk (I11).
 */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { getEvalRun } from "../api";
import type { EvalRun, Scorecard } from "../api/types";

export const evalRunKey = (runId: string | undefined) => ["eval-run", runId];

interface UseEvalRunResult {
  run: EvalRun | undefined;
  isLoading: boolean;
  error: unknown;
  refetch: () => void;
  /** Call when the SSE stream emits its first event to suppress the poll. */
  markStreamActive: () => void;
  /** Manually apply a scorecard locally (e.g. when SSE emits `complete`
   *  before the poll catches up) and invalidate the cached run so the next
   *  query re-fetches terminal state. */
  applyScorecard: (sc: Scorecard) => void;
}

export function useEvalRun(
  runId: string | undefined,
  streamActive: boolean,
): UseEvalRunResult {
  const queryClient = useQueryClient();

  const query = useQuery({
    queryKey: evalRunKey(runId),
    queryFn: () => getEvalRun(runId as string),
    enabled: !!runId,
    refetchInterval: (q) => {
      // Stop polling once the SSE stream is live — it delivers more granular
      // updates and removes the need for the 3s catch-up poll (I9).
      if (streamActive) return false;
      const status = q.state.data?.status;
      return status === "running" || status === "pending" ? 3000 : false;
    },
  });

  const markStreamActive = useCallback(() => {
    // One-shot: invalidate so a single fetch pulls terminal state on complete.
    queryClient.invalidateQueries({ queryKey: evalRunKey(runId) });
  }, [queryClient, runId]);

  const applyScorecard = useCallback(
    (sc: Scorecard) => {
      queryClient.setQueryData<EvalRun | undefined>(
        evalRunKey(runId),
        (prev) =>
          prev
            ? { ...prev, status: "completed", summary_stats: sc }
            : prev,
      );
    },
    [queryClient, runId],
  );

  return {
    run: query.data,
    isLoading: query.isLoading,
    error: query.error,
    refetch: query.refetch,
    markStreamActive,
    applyScorecard,
  };
}
