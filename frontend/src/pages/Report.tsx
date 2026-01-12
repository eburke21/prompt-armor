/**
 * Report page — generates and displays a Claude-powered red team report.
 *
 * Route: /report/:runId
 * Accepts a comma-separated list of run IDs for comparison reports.
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
import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { generateReport } from "../api";
import type { ReportGenerateResponse } from "../api/types";
import { ReportViewer } from "../components/ReportViewer";

export function Report() {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [report, setReport] = useState<ReportGenerateResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Parse run IDs (supports comma-separated for comparisons)
  const runIds = runId?.split(",").filter(Boolean) ?? [];

  const fetchReport = useCallback(async () => {
    if (runIds.length === 0) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await generateReport(runIds);
      setReport(result);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to generate report",
      );
    } finally {
      setIsLoading(false);
    }
  }, [runIds.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-generate on mount
  useEffect(() => {
    if (!report && !isLoading && !error) {
      fetchReport();
    }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

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
        <Button
          variant="outline"
          size="sm"
          onClick={() => navigate(-1)}
        >
          Back to Results
        </Button>
      </Flex>

      {/* Loading state */}
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

      {/* Error state */}
      {error && !isLoading && (
        <Card.Root>
          <Card.Body>
            <Flex direction="column" align="center" py={8} gap={4}>
              <Text fontSize="xl">Report Generation Failed</Text>
              <Text color="red.400" fontSize="sm">
                {error}
              </Text>
              <Button colorPalette="blue" onClick={fetchReport}>
                Try Again
              </Button>
            </Flex>
          </Card.Body>
        </Card.Root>
      )}

      {/* Report display */}
      {report && !isLoading && (
        <ReportViewer
          markdown={report.markdown}
          modelUsed={report.model_used}
          onRegenerate={fetchReport}
          isRegenerating={isLoading}
        />
      )}
    </Box>
  );
}
