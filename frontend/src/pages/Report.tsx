/**
 * Report page — generates and displays a Claude-powered red team report.
 *
 * Route: /report/:runId
 * Accepts a comma-separated list of run IDs for comparison reports.
 *
 * Uses TanStack Query so caching, retries, and stale-closure handling match
 * the rest of the app — previously this page rolled its own fetch/useEffect
 * with eslint-disable escapes for exhaustive-deps (I15).
 */

import {
  Box,
  Button,
  Card,
  Flex,
  Heading,
  Spinner,
  Text,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useMemo } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { generateReport } from "../api";
import { ReportViewer } from "../components/ReportViewer";

export function Report() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  // Memoize the parsed run id list so referential identity is stable across
  // renders — previously re-parsed on every render and tripped deps warnings.
  const runIds = useMemo(
    () => runId?.split(",").filter(Boolean) ?? [],
    [runId],
  );

  const {
    data: report,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["report", runIds.join(",")],
    queryFn: () => generateReport(runIds),
    enabled: runIds.length > 0,
    // The Claude generation call is non-idempotent from the user's perspective:
    // don't auto-refetch on every mount/focus. A fresh cached report per set
    // of run IDs is the correct default.
    staleTime: Infinity,
    retry: 0,
  });

  if (!runId) {
    return (
      <Box>
        <Heading size="xl" mb={4}>
          Report
        </Heading>
        <Text>No eval run ID provided.</Text>
      </Box>
    );
  }

  const errorMessage =
    error instanceof Error ? error.message : error ? String(error) : null;

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Box>
          <Heading size="xl" mb={1}>
            Red Team Report
          </Heading>
          <Text fontSize="sm" color="fg.muted">
            {runIds.length > 1
              ? `Comparison report for ${runIds.length} configs`
              : `Report for eval run ${runId}`}
          </Text>
        </Box>
        <Button variant="outline" size="sm" onClick={() => navigate(-1)}>
          Back to Results
        </Button>
      </Flex>

      {isLoading && (
        <Card.Root>
          <Card.Body>
            <Flex
              direction="column"
              align="center"
              justify="center"
              py={12}
              gap={4}
            >
              <Spinner size="xl" color="blue.500" />
              <Heading size="sm">Generating Report...</Heading>
              <Text fontSize="sm" color="fg.muted" textAlign="center">
                Claude is analyzing your eval results and writing a
                professional red team assessment. This typically takes
                10-20 seconds.
              </Text>
            </Flex>
          </Card.Body>
        </Card.Root>
      )}

      {errorMessage && !isLoading && (
        <Card.Root>
          <Card.Body>
            <Flex direction="column" align="center" py={8} gap={4}>
              <Text fontSize="xl">Report Generation Failed</Text>
              <Text color="red.400" fontSize="sm">
                {errorMessage}
              </Text>
              <Button colorPalette="blue" onClick={() => refetch()}>
                Try Again
              </Button>
            </Flex>
          </Card.Body>
        </Card.Root>
      )}

      {report && !isLoading && (
        <ReportViewer
          markdown={report.markdown}
          modelUsed={report.model_used}
          onRegenerate={() => refetch()}
          isRegenerating={isLoading}
        />
      )}
    </Box>
  );
}
