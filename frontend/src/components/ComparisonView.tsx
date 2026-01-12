/**
 * ComparisonView — side-by-side comparison of 2-3 defense configs.
 *
 * Displays:
 * 1. Shared attack set summary bar
 * 2. Mini scorecard columns (one per config)
 * 3. Coverage matrix table (techniques × configs with colored cells)
 * 4. Grouped bar chart (block rate by technique, grouped by config)
 * 5. Layer breakdown comparison
 */

import {
  Badge,
  Box,
  Card,
  Flex,
  Heading,
  SimpleGrid,
  Table,
  Text,
} from "@chakra-ui/react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Scorecard } from "../api/types";
import { TECHNIQUE_INFO } from "../theme/constants";

// ---------------------------------------------------------------------------
// Config colors & labels
// ---------------------------------------------------------------------------

const CONFIG_COLORS = ["#3b82f6", "#f59e0b", "#8b5cf6"];
const CONFIG_LABELS = ["Config A", "Config B", "Config C"];

interface ComparisonViewProps {
  scorecards: Scorecard[];
  configLabels?: string[];
}

// ---------------------------------------------------------------------------
// Coverage matrix — the most useful comparison artifact
// ---------------------------------------------------------------------------

function CoverageMatrix({
  scorecards,
  labels,
}: {
  scorecards: Scorecard[];
  labels: string[];
}) {
  // Collect all techniques across all scorecards
  const allTechniques = new Set<string>();
  for (const sc of scorecards) {
    for (const t of Object.keys(sc.by_technique)) {
      allTechniques.add(t);
    }
  }
  const techniques = [...allTechniques].sort();

  function cellColor(rate: number): string {
    if (rate >= 0.8) return "rgba(34, 197, 94, 0.25)";
    if (rate >= 0.5) return "rgba(245, 158, 11, 0.2)";
    return "rgba(239, 68, 68, 0.2)";
  }

  function diffArrow(rates: number[]): string {
    if (rates.length < 2) return "";
    const max = Math.max(...rates);
    const min = Math.min(...rates);
    if (max - min > 0.1) return " ⚡";
    return "";
  }

  return (
    <Card.Root>
      <Card.Body>
        <Heading size="sm" mb={3}>
          Coverage Matrix
        </Heading>
        <Box overflowX="auto">
          <Table.Root size="sm" variant="outline">
            <Table.Header>
              <Table.Row>
                <Table.ColumnHeader>Technique</Table.ColumnHeader>
                {labels.map((label, i) => (
                  <Table.ColumnHeader key={i} textAlign="center">
                    <Flex align="center" justify="center" gap={1}>
                      <Box
                        w="10px"
                        h="10px"
                        borderRadius="full"
                        bg={CONFIG_COLORS[i]}
                      />
                      {label}
                    </Flex>
                  </Table.ColumnHeader>
                ))}
                <Table.ColumnHeader textAlign="center">Diff</Table.ColumnHeader>
              </Table.Row>
            </Table.Header>
            <Table.Body>
              {techniques.map((techId) => {
                const rates = scorecards.map(
                  (sc) => sc.by_technique[techId]?.rate ?? 0,
                );
                const maxRate = Math.max(...rates);
                const minRate = Math.min(...rates);
                const hasBigDiff = maxRate - minRate > 0.1;
                const techName =
                  TECHNIQUE_INFO[techId]?.name ?? techId;

                return (
                  <Table.Row key={techId}>
                    <Table.Cell>
                      <Text fontSize="sm">{techName}</Text>
                    </Table.Cell>
                    {scorecards.map((sc, i) => {
                      const score = sc.by_technique[techId];
                      const rate = score?.rate ?? 0;
                      const isBest =
                        hasBigDiff && rate === maxRate;
                      const isWorst =
                        hasBigDiff && rate === minRate;

                      return (
                        <Table.Cell
                          key={i}
                          textAlign="center"
                          bg={cellColor(rate)}
                        >
                          <Text
                            fontSize="sm"
                            fontWeight={
                              isBest || isWorst ? "bold" : "normal"
                            }
                            color={
                              isBest
                                ? "green.400"
                                : isWorst
                                  ? "red.400"
                                  : undefined
                            }
                          >
                            {(rate * 100).toFixed(0)}%
                            {isBest && " ↑"}
                            {isWorst && " ↓"}
                          </Text>
                          {score && (
                            <Text fontSize="xs" color="fg.muted">
                              {score.blocked}/{score.total}
                            </Text>
                          )}
                        </Table.Cell>
                      );
                    })}
                    <Table.Cell textAlign="center">
                      {hasBigDiff ? (
                        <Badge colorPalette="orange" size="sm">
                          {((maxRate - minRate) * 100).toFixed(0)}pp
                          {diffArrow(rates)}
                        </Badge>
                      ) : (
                        <Text fontSize="xs" color="fg.muted">
                          ~
                        </Text>
                      )}
                    </Table.Cell>
                  </Table.Row>
                );
              })}
            </Table.Body>
          </Table.Root>
        </Box>
      </Card.Body>
    </Card.Root>
  );
}

// ---------------------------------------------------------------------------
// Grouped bar chart — block rate by technique, grouped by config
// ---------------------------------------------------------------------------

function GroupedTechniqueChart({
  scorecards,
  labels,
}: {
  scorecards: Scorecard[];
  labels: string[];
}) {
  // Build data: one row per technique with configA, configB, configC keys
  const allTechniques = new Set<string>();
  for (const sc of scorecards) {
    for (const t of Object.keys(sc.by_technique)) {
      allTechniques.add(t);
    }
  }

  const data = [...allTechniques]
    .sort()
    .map((techId) => {
      const row: Record<string, string | number> = {
        name: TECHNIQUE_INFO[techId]?.name ?? techId,
      };
      scorecards.forEach((sc, i) => {
        row[labels[i]] = Math.round(
          (sc.by_technique[techId]?.rate ?? 0) * 100,
        );
      });
      return row;
    });

  return (
    <Card.Root>
      <Card.Body>
        <Heading size="sm" mb={3}>
          Block Rate by Technique
        </Heading>
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height={data.length * 50 + 60}>
            <BarChart
              data={data}
              layout="vertical"
              margin={{ left: 120, right: 20, top: 5, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
              <XAxis
                type="number"
                domain={[0, 100]}
                tickFormatter={(v: number) => `${v}%`}
                fontSize={12}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={115}
                fontSize={11}
                tick={{ fill: "currentColor" }}
              />
              <Tooltip
                formatter={(value: number) => [`${value}%`, "Block Rate"]}
                contentStyle={{
                  background: "#1a1a2e",
                  border: "1px solid #333",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Legend />
              {labels.map((label, i) => (
                <Bar
                  key={label}
                  dataKey={label}
                  fill={CONFIG_COLORS[i]}
                  radius={[0, 4, 4, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <Text fontSize="sm" color="fg.muted">
            No technique data available
          </Text>
        )}
      </Card.Body>
    </Card.Root>
  );
}

// ---------------------------------------------------------------------------
// Layer breakdown comparison
// ---------------------------------------------------------------------------

function LayerComparison({
  scorecards,
  labels,
}: {
  scorecards: Scorecard[];
  labels: string[];
}) {
  const allLayers = new Set<string>();
  for (const sc of scorecards) {
    for (const l of Object.keys(sc.by_layer)) {
      allLayers.add(l);
    }
  }

  function formatLayerName(name: string): string {
    switch (name) {
      case "input_filter":
        return "Input Filter";
      case "llm_refused":
        return "LLM Refused";
      case "output_filter":
        return "Output Filter";
      default:
        return name;
    }
  }

  const data = [...allLayers].map((layerId) => {
    const row: Record<string, string | number> = {
      name: formatLayerName(layerId),
    };
    scorecards.forEach((sc, i) => {
      row[labels[i]] = sc.by_layer[layerId]?.blocked ?? 0;
    });
    return row;
  });

  return (
    <Card.Root>
      <Card.Body>
        <Heading size="sm" mb={3}>
          Blocks by Defense Layer
        </Heading>
        {data.length > 0 ? (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart
              data={data}
              margin={{ left: 10, right: 20, top: 5, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
              <XAxis dataKey="name" fontSize={12} />
              <YAxis fontSize={12} />
              <Tooltip
                formatter={(value: number) => [value, "Blocked"]}
                contentStyle={{
                  background: "#1a1a2e",
                  border: "1px solid #333",
                  borderRadius: 8,
                  fontSize: 12,
                }}
              />
              <Legend />
              {labels.map((label, i) => (
                <Bar
                  key={label}
                  dataKey={label}
                  fill={CONFIG_COLORS[i]}
                  radius={[4, 4, 0, 0]}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <Text fontSize="sm" color="fg.muted">
            No layer data available
          </Text>
        )}
      </Card.Body>
    </Card.Root>
  );
}

// ---------------------------------------------------------------------------
// Mini scorecard column
// ---------------------------------------------------------------------------

function MiniScorecard({
  scorecard,
  label,
  color,
}: {
  scorecard: Scorecard;
  label: string;
  color: string;
}) {
  const blockPct = (scorecard.attack_block_rate * 100).toFixed(1);
  const fpPct = (scorecard.false_positive_rate * 100).toFixed(1);
  const rateColor =
    scorecard.attack_block_rate >= 0.8
      ? "#22c55e"
      : scorecard.attack_block_rate >= 0.5
        ? "#f59e0b"
        : "#ef4444";

  return (
    <Card.Root borderTop="3px solid" borderTopColor={color}>
      <Card.Body>
        <Flex align="center" gap={2} mb={3}>
          <Box w="12px" h="12px" borderRadius="full" bg={color} />
          <Heading size="sm">{label}</Heading>
        </Flex>

        <Flex direction="column" gap={2}>
          <Flex justify="space-between" align="baseline">
            <Text fontSize="sm" color="fg.muted">
              Block Rate
            </Text>
            <Text fontSize="xl" fontWeight="bold" color={rateColor}>
              {blockPct}%
            </Text>
          </Flex>

          <Flex justify="space-between">
            <Text fontSize="sm" color="fg.muted">
              False Positive
            </Text>
            <Text fontSize="sm" fontWeight="medium">
              {fpPct}%
            </Text>
          </Flex>

          <Flex justify="space-between">
            <Text fontSize="sm" color="fg.muted">
              Attacks
            </Text>
            <Text fontSize="sm" fontWeight="medium">
              {Math.round(
                scorecard.attack_block_rate * scorecard.total_attacks,
              )}
              /{scorecard.total_attacks} blocked
            </Text>
          </Flex>

          <Flex justify="space-between">
            <Text fontSize="sm" color="fg.muted">
              Layers
            </Text>
            <Text fontSize="sm" fontWeight="medium">
              {Object.keys(scorecard.by_layer).length} active
            </Text>
          </Flex>
        </Flex>
      </Card.Body>
    </Card.Root>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ComparisonView({
  scorecards,
  configLabels,
}: ComparisonViewProps) {
  const labels = configLabels ?? scorecards.map((_, i) => CONFIG_LABELS[i]);

  // Compute shared attack set info from first scorecard
  const shared = scorecards[0];
  const totalPrompts = shared
    ? shared.total_attacks + shared.total_benign
    : 0;
  const totalTechniques = shared
    ? Object.keys(shared.by_technique).length
    : 0;

  return (
    <Box>
      {/* Shared attack set info bar */}
      <Card.Root mb={6}>
        <Card.Body>
          <Flex
            justify="space-between"
            align="center"
            wrap="wrap"
            gap={3}
          >
            <Heading size="sm">Comparison Results</Heading>
            <Flex gap={4}>
              <Badge size="sm" colorPalette="blue">
                {scorecards.length} Configs
              </Badge>
              <Badge size="sm" colorPalette="gray">
                {totalPrompts} Shared Prompts
              </Badge>
              <Badge size="sm" colorPalette="gray">
                {totalTechniques} Techniques
              </Badge>
            </Flex>
          </Flex>
        </Card.Body>
      </Card.Root>

      {/* Mini scorecards row */}
      <SimpleGrid
        columns={{ base: 1, md: scorecards.length }}
        gap={4}
        mb={6}
      >
        {scorecards.map((sc, i) => (
          <MiniScorecard
            key={sc.eval_run_id}
            scorecard={sc}
            label={labels[i]}
            color={CONFIG_COLORS[i]}
          />
        ))}
      </SimpleGrid>

      {/* Coverage matrix */}
      <Box mb={6}>
        <CoverageMatrix scorecards={scorecards} labels={labels} />
      </Box>

      {/* Charts */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6} mb={6}>
        <GroupedTechniqueChart scorecards={scorecards} labels={labels} />
        <LayerComparison scorecards={scorecards} labels={labels} />
      </SimpleGrid>
    </Box>
  );
}
