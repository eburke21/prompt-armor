/**
 * RunResults — page for viewing an eval run's progress or final scorecard.
 *
 * Route: /sandbox/:runId
 *
 * States:
 * - Loading: fetching run status
 * - Running: shows LiveResultsStream with real-time SSE events
 * - Complete: shows ScorecardView with charts
 * - Failed: shows error message with retry option
 */

import {
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Heading,
  Skeleton,
  Text,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";

import { getEvalResults, getEvalRun } from "../api";
import type { EvalResultItem, Scorecard } from "../api/types";
import { LiveResultsStream } from "../components/LiveResultsStream";
import { ScorecardView } from "../components/ScorecardView";

export function RunResults() {
  const { runId } = useParams<{ runId: string }>();
  const [liveScorecard, setLiveScorecard] = useState<Scorecard | null>(null);
  const [showDetails, setShowDetails] = useState(false);

  // Fetch run metadata
  const {
    data: run,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["eval-run", runId],
    queryFn: () => getEvalRun(runId!),
    enabled: !!runId,
    // Poll every 3s while running to get updated status
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      return status === "running" || status === "pending" ? 3000 : false;
    },
  });

  // Fetch detailed results (only when scorecard is visible and details toggled)
  const scorecard = liveScorecard ?? run?.summary_stats ?? null;
  const isComplete = run?.status === "completed" || liveScorecard != null;

  const { data: detailedResults } = useQuery({
    queryKey: ["eval-results", runId],
    queryFn: () => getEvalResults(runId!, { limit: 200 }),
    enabled: !!runId && isComplete && showDetails,
  });

  const handleStreamComplete = useCallback((sc: Scorecard) => {
    setLiveScorecard(sc);
  }, []);

  if (!runId) {
    return (
      <Box>
        <Text color="red.400">No run ID provided.</Text>
      </Box>
    );
  }

  // --- Loading state ---
  if (isLoading) {
    return (
      <Box>
        <Skeleton height="40px" mb={4} />
        <Skeleton height="200px" mb={4} />
        <Skeleton height="300px" />
      </Box>
    );
  }

  // --- Error state ---
  if (error) {
    return (
      <Box>
        <Heading size="lg" mb={4}>
          Run Not Found
        </Heading>
        <Text color="fg.muted" mb={4}>
          Could not load eval run {runId}:{" "}
          {error instanceof Error ? error.message : String(error)}
        </Text>
        <Flex gap={3}>
          <Button onClick={() => refetch()} colorPalette="blue">
            Retry
          </Button>
          <Button asChild variant="outline">
            <RouterLink to="/sandbox">Back to Sandbox</RouterLink>
          </Button>
        </Flex>
      </Box>
    );
  }

  // --- Failed run ---
  if (run?.status === "failed") {
    return (
      <Box>
        <Heading size="lg" mb={2}>
          Run Failed
        </Heading>
        <Text color="fg.muted" mb={4}>
          Eval run {runId} encountered an error and could not complete.
        </Text>
        <Button asChild colorPalette="blue">
          <RouterLink to="/sandbox">Try Again</RouterLink>
        </Button>
      </Box>
    );
  }

  // --- Running state: show live stream ---
  if (!isComplete) {
    return (
      <Box>
        <Flex align="center" gap={3} mb={4}>
          <Heading size="lg">Eval Run</Heading>
          <Badge colorPalette="blue" size="sm">
            {run?.status ?? "running"}
          </Badge>
        </Flex>
        <Text color="fg.muted" mb={4}>
          Testing your defense configuration against{" "}
          {run?.total_prompts ?? "..."} prompts. Results appear in real-time.
        </Text>
        <LiveResultsStream
          runId={runId}
          onComplete={handleStreamComplete}
        />
      </Box>
    );
  }

  // --- Complete state: show scorecard ---
  return (
    <Box>
      <Flex align="center" gap={3} mb={2}>
        <Heading size="lg">Eval Results</Heading>
        <Badge colorPalette="green" size="sm">
          completed
        </Badge>
      </Flex>
      <Text color="fg.muted" mb={6}>
        Run {runId?.slice(0, 8)}... • {run?.total_prompts ?? scorecard?.total_attacks} prompts •{" "}
        {run?.created_at
          ? new Date(run.created_at).toLocaleString()
          : "just now"}
      </Text>

      {scorecard && <ScorecardView scorecard={scorecard} />}

      {/* Toggle detailed results */}
      <Card.Root>
        <Card.Body>
          <Flex justify="space-between" align="center" mb={showDetails ? 4 : 0}>
            <Heading size="sm">Detailed Results</Heading>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setShowDetails((v) => !v)}
            >
              {showDetails ? "Hide Details" : "View Details"}
            </Button>
          </Flex>

          {showDetails && detailedResults && (
            <Box overflowX="auto">
              <Box as="table" w="full" fontSize="sm">
                <Box as="thead">
                  <Box as="tr" borderBottomWidth="1px" borderColor="border">
                    <Box as="th" textAlign="left" p={2} fontSize="xs">
                      #
                    </Box>
                    <Box as="th" textAlign="left" p={2} fontSize="xs">
                      Prompt
                    </Box>
                    <Box as="th" textAlign="left" p={2} fontSize="xs">
                      Type
                    </Box>
                    <Box as="th" textAlign="left" p={2} fontSize="xs">
                      Result
                    </Box>
                    <Box as="th" textAlign="left" p={2} fontSize="xs">
                      Blocked By
                    </Box>
                    <Box as="th" textAlign="right" p={2} fontSize="xs">
                      Latency
                    </Box>
                  </Box>
                </Box>
                <Box as="tbody">
                  {detailedResults.results.map(
                    (r: EvalResultItem, i: number) => (
                      <Box
                        as="tr"
                        key={r.id}
                        borderBottomWidth="1px"
                        borderColor="border"
                        bg={resultRowBg(r)}
                      >
                        <Box as="td" p={2} color="fg.muted">
                          {i + 1}
                        </Box>
                        <Box as="td" p={2} maxW="300px">
                          <Text
                            fontFamily="mono"
                            fontSize="xs"
                            truncate
                            title={r.prompt_text}
                          >
                            {r.prompt_text}
                          </Text>
                        </Box>
                        <Box as="td" p={2}>
                          <Badge
                            size="sm"
                            colorPalette={r.is_injection ? "red" : "gray"}
                          >
                            {r.is_injection ? "injection" : "benign"}
                          </Badge>
                        </Box>
                        <Box as="td" p={2}>
                          {detailedResultBadge(r)}
                        </Box>
                        <Box as="td" p={2}>
                          <Text fontSize="xs">
                            {detailedBlockedBy(r)}
                          </Text>
                        </Box>
                        <Box as="td" p={2} textAlign="right">
                          <Text fontSize="xs" color="fg.muted">
                            {r.llm_latency_ms != null
                              ? `${r.llm_latency_ms}ms`
                              : "—"}
                          </Text>
                        </Box>
                      </Box>
                    ),
                  )}
                </Box>
              </Box>
            </Box>
          )}

          {showDetails && !detailedResults && (
            <Skeleton height="200px" />
          )}
        </Card.Body>
      </Card.Root>

      {/* Actions */}
      <Flex gap={3} mt={6}>
        <Button asChild colorPalette="blue">
          <RouterLink to="/sandbox">Run Another Test</RouterLink>
        </Button>
      </Flex>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Helpers for the detailed results table
// ---------------------------------------------------------------------------

function resultRowBg(r: EvalResultItem): string {
  const blocked = r.input_filter_blocked || r.output_filter_blocked || r.blocked_by === "llm_refused";
  if (!r.is_injection && blocked) return "yellow.900/20";
  if (r.is_injection && blocked) return "green.900/20";
  if (r.is_injection && !blocked) return "red.900/20";
  return "transparent";
}

function detailedResultBadge(r: EvalResultItem) {
  const blocked = r.input_filter_blocked || r.output_filter_blocked || r.blocked_by === "llm_refused";
  if (!r.is_injection && blocked) {
    return (
      <Badge colorPalette="yellow" size="sm">
        ⚠️ False Positive
      </Badge>
    );
  }
  if (blocked) {
    return (
      <Badge colorPalette="green" size="sm">
        ✅ Blocked
      </Badge>
    );
  }
  if (r.is_injection) {
    return (
      <Badge colorPalette="red" size="sm">
        ❌ Passed
      </Badge>
    );
  }
  return (
    <Badge colorPalette="gray" size="sm">
      ✓ Passed
    </Badge>
  );
}

function detailedBlockedBy(r: EvalResultItem): string {
  if (r.input_filter_blocked) return r.input_filter_type ?? "Input Filter";
  if (r.output_filter_blocked) return r.output_filter_type ?? "Output Filter";
  if (r.blocked_by === "llm_refused") return "LLM Refused";
  return "—";
}
