/**
 * LiveResultsStream — real-time display of eval run results via SSE.
 *
 * Subscribes to the SSE stream for an eval run and renders:
 * 1. A progress bar showing completed / total prompts
 * 2. A growing results table with color-coded rows
 * 3. Auto-scrolls to the latest result (with scroll-lock toggle)
 *
 * When the `complete` event arrives, calls onComplete with the scorecard.
 */

import {
  Badge,
  Box,
  Button,
  Flex,
  Heading,
  Table,
  Text,
} from "@chakra-ui/react";
import { useCallback, useEffect, useRef, useState } from "react";

import { subscribeToEvalStream } from "../api/sse";
import type {
  CompleteEvent,
  ErrorEvent,
  ProgressEvent,
  ResultEvent,
  Scorecard,
} from "../api/types";
import { TECHNIQUE_INFO } from "../theme/constants";

interface LiveResultsStreamProps {
  runId: string;
  onComplete: (scorecard: Scorecard) => void;
  /** Called once when the first SSE event arrives, so the parent can stop
   *  any redundant polling (I9). */
  onActive?: () => void;
}

/** Internal representation distinguishing a real backend error (has message
 *  from the server) from a transient network disconnect (no server data). */
type StreamError =
  | { kind: "backend"; message: string }
  | { kind: "disconnect" };

/** Classify a result row for color coding */
function rowColor(result: ResultEvent): string {
  if (!result.is_injection && result.blocked) {
    // False positive — benign prompt incorrectly blocked
    return "yellow.900/30";
  }
  if (result.is_injection && result.blocked) {
    // Injection correctly blocked
    return "green.900/30";
  }
  if (result.is_injection && !result.blocked) {
    // Injection passed through — bad
    return "red.900/30";
  }
  // Benign correctly passed
  return "transparent";
}

function blockedByLabel(result: ResultEvent): string {
  if (!result.blocked) return "—";
  if (result.input_filter_blocked) {
    return result.input_filter_type ?? "Input Filter";
  }
  if (result.output_filter_blocked) {
    return result.output_filter_type ?? "Output Filter";
  }
  return "LLM Refused";
}

function resultBadge(result: ResultEvent) {
  if (!result.is_injection && result.blocked) {
    return (
      <Badge colorPalette="yellow" size="sm">
        ⚠️ False Positive
      </Badge>
    );
  }
  if (result.blocked) {
    return (
      <Badge colorPalette="green" size="sm">
        ✅ Blocked
      </Badge>
    );
  }
  if (result.is_injection) {
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

export function LiveResultsStream({
  runId,
  onComplete,
  onActive,
}: LiveResultsStreamProps) {
  const [results, setResults] = useState<ResultEvent[]>([]);
  const [progress, setProgress] = useState<ProgressEvent | null>(null);
  const [streamError, setStreamError] = useState<StreamError | null>(null);
  const [autoScroll, setAutoScroll] = useState(true);
  const tableEndRef = useRef<HTMLDivElement>(null);
  const activeFiredRef = useRef(false);

  // Auto-scroll effect
  useEffect(() => {
    if (autoScroll && tableEndRef.current) {
      tableEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [results.length, autoScroll]);

  // SSE subscription
  useEffect(() => {
    const markActive = () => {
      if (!activeFiredRef.current) {
        activeFiredRef.current = true;
        onActive?.();
      }
    };

    const cleanup = subscribeToEvalStream(runId, {
      onProgress: (data: ProgressEvent) => {
        markActive();
        setProgress(data);
      },
      onResult: (data: ResultEvent) => {
        markActive();
        setResults((prev) => [...prev, data]);
      },
      onComplete: (data: CompleteEvent) => {
        markActive();
        onComplete(data.scorecard);
      },
      onError: (data: ErrorEvent) => {
        markActive();
        // Backend-emitted error with a message — surface it prominently (I7).
        setStreamError({ kind: "backend", message: data.message });
      },
      onDisconnect: () => {
        // Network-level disconnect — only fall back to this message if we
        // haven't received a definitive backend error or completion. (I7)
        setStreamError((prev) => prev ?? { kind: "disconnect" });
      },
    });

    return cleanup;
  }, [runId, onComplete, onActive]);

  const completedCount = progress?.completed ?? results.length;
  const totalCount = progress?.total ?? 0;
  const pct = totalCount > 0 ? (completedCount / totalCount) * 100 : 0;

  // Estimate ETA based on average time per prompt
  const estimateEta = useCallback(() => {
    if (completedCount === 0 || totalCount === 0) return null;
    const remaining = totalCount - completedCount;
    // Rough estimate: ~2 seconds per prompt (Claude API latency)
    const etaSeconds = remaining * 2;
    if (etaSeconds < 60) return `~${etaSeconds}s remaining`;
    return `~${Math.ceil(etaSeconds / 60)}m remaining`;
  }, [completedCount, totalCount]);

  return (
    <Box>
      {/* Progress bar */}
      <Box mb={4}>
        <Flex justify="space-between" mb={1}>
          <Text fontSize="sm" fontWeight="medium">
            Progress: {completedCount} / {totalCount} prompts
          </Text>
          <Text fontSize="sm" color="fg.muted">
            {pct > 0 && pct < 100 && estimateEta()}
            {pct >= 100 && "Computing scorecard..."}
          </Text>
        </Flex>
        <Box bg="bg.muted" borderRadius="full" h="8px" overflow="hidden">
          <Box
            bg="blue.500"
            h="full"
            borderRadius="full"
            transition="width 0.3s ease"
            style={{ width: `${Math.min(pct, 100)}%` }}
          />
        </Box>
      </Box>

      {streamError && (
        <Box
          bg={streamError.kind === "backend" ? "red.900/20" : "yellow.900/20"}
          border="1px solid"
          borderColor={
            streamError.kind === "backend" ? "red.500/30" : "yellow.500/30"
          }
          borderRadius="md"
          p={3}
          mb={4}
        >
          <Text
            color={streamError.kind === "backend" ? "red.400" : "yellow.400"}
            fontSize="sm"
            fontWeight="medium"
            mb={1}
          >
            {streamError.kind === "backend"
              ? "Backend error"
              : "Connection lost"}
          </Text>
          <Text fontSize="xs" color="fg.muted">
            {streamError.kind === "backend"
              ? streamError.message
              : "Reconnecting — any completed results above are final; remaining prompts may not appear."}
          </Text>
        </Box>
      )}

      {/* Controls */}
      <Flex justify="space-between" align="center" mb={3}>
        <Heading size="sm">
          Results ({results.length})
        </Heading>
        <Button
          size="xs"
          variant={autoScroll ? "solid" : "outline"}
          colorPalette="blue"
          onClick={() => setAutoScroll((v) => !v)}
        >
          {autoScroll ? "Auto-scroll ON" : "Auto-scroll OFF"}
        </Button>
      </Flex>

      {/* Results table */}
      <Box
        maxH="500px"
        overflowY="auto"
        borderWidth="1px"
        borderColor="border"
        borderRadius="md"
      >
        <Table.Root size="sm">
          <Table.Header>
            <Table.Row>
              <Table.ColumnHeader w="40px">#</Table.ColumnHeader>
              <Table.ColumnHeader>Prompt</Table.ColumnHeader>
              <Table.ColumnHeader w="140px">Technique</Table.ColumnHeader>
              <Table.ColumnHeader w="130px">Result</Table.ColumnHeader>
              <Table.ColumnHeader w="120px">Blocked By</Table.ColumnHeader>
              <Table.ColumnHeader w="80px" textAlign="right">
                Latency
              </Table.ColumnHeader>
            </Table.Row>
          </Table.Header>
          <Table.Body>
            {results.map((r, i) => (
              <Table.Row key={r.prompt_id} bg={rowColor(r)}>
                <Table.Cell fontSize="xs" color="fg.muted">
                  {i + 1}
                </Table.Cell>
                <Table.Cell>
                  <Text
                    fontSize="xs"
                    fontFamily="mono"
                    truncate
                    maxW="300px"
                    title={r.prompt_text}
                  >
                    {r.prompt_text}
                  </Text>
                </Table.Cell>
                <Table.Cell>
                  {r.techniques.length > 0 ? (
                    <Badge size="sm" variant="outline">
                      {TECHNIQUE_INFO[r.techniques[0]]?.name ??
                        r.techniques[0]}
                    </Badge>
                  ) : (
                    <Badge size="sm" variant="outline" colorPalette="gray">
                      benign
                    </Badge>
                  )}
                </Table.Cell>
                <Table.Cell>{resultBadge(r)}</Table.Cell>
                <Table.Cell>
                  <Text fontSize="xs">{blockedByLabel(r)}</Text>
                </Table.Cell>
                <Table.Cell textAlign="right">
                  <Text fontSize="xs" color="fg.muted">
                    {r.llm_latency_ms != null
                      ? `${r.llm_latency_ms}ms`
                      : "—"}
                  </Text>
                </Table.Cell>
              </Table.Row>
            ))}
          </Table.Body>
        </Table.Root>
        <div ref={tableEndRef} />
      </Box>
    </Box>
  );
}
