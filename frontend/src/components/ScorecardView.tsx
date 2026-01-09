/**
 * ScorecardView — renders the final eval scorecard with charts.
 *
 * Displays:
 * 1. Hero metric: overall attack block rate (animated ring)
 * 2. False positive rate
 * 3. By-technique horizontal bar chart
 * 4. By-defense-layer stacked bar chart
 * 5. By-difficulty grouped bar chart
 */

import {
  Badge,
  Box,
  Card,
  Flex,
  Heading,
  SimpleGrid,
  Text,
} from "@chakra-ui/react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import type { Scorecard } from "../api/types";
import {
  blockRateColor,
  DIFFICULTY_LABELS,
  TECHNIQUE_INFO,
} from "../theme/constants";

interface ScorecardViewProps {
  scorecard: Scorecard;
}

// ---------------------------------------------------------------------------
// Hero ring component — SVG circular progress
// ---------------------------------------------------------------------------

function BlockRateRing({
  rate,
  size = 160,
}: {
  rate: number;
  size?: number;
}) {
  const strokeWidth = 12;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference * (1 - rate);
  const pct = (rate * 100).toFixed(1);

  const color =
    rate >= 0.8 ? "#22c55e" : rate >= 0.5 ? "#f59e0b" : "#ef4444";

  return (
    <Box position="relative" w={`${size}px`} h={`${size}px`}>
      <svg width={size} height={size}>
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          opacity={0.1}
        />
        {/* Progress ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{
            transition: "stroke-dashoffset 1s ease-in-out",
          }}
        />
      </svg>
      <Flex
        position="absolute"
        inset={0}
        align="center"
        justify="center"
        direction="column"
      >
        <Text fontSize="2xl" fontWeight="bold" color={color}>
          {pct}%
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Block Rate
        </Text>
      </Flex>
    </Box>
  );
}

// ---------------------------------------------------------------------------
// Chart data helpers
// ---------------------------------------------------------------------------

function buildTechniqueData(scorecard: Scorecard) {
  return Object.entries(scorecard.by_technique)
    .map(([id, score]) => ({
      name: TECHNIQUE_INFO[id]?.name ?? id,
      id,
      rate: Math.round(score.rate * 100),
      blocked: score.blocked,
      total: score.total,
    }))
    .sort((a, b) => a.rate - b.rate); // Worst first — most useful
}

function buildLayerData(scorecard: Scorecard) {
  const layers = scorecard.by_layer;
  return Object.entries(layers).map(([name, score]) => ({
    name: formatLayerName(name),
    blocked: score.blocked,
    rate: Math.round(score.rate * 100),
  }));
}

function buildDifficultyData(scorecard: Scorecard) {
  return Object.entries(scorecard.by_difficulty)
    .map(([level, score]) => ({
      name: DIFFICULTY_LABELS[Number(level)] ?? `Level ${level}`,
      level: Number(level),
      rate: Math.round(score.rate * 100),
      blocked: score.blocked,
      total: score.total,
    }))
    .sort((a, b) => a.level - b.level);
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

const LAYER_COLORS: Record<string, string> = {
  "Input Filter": "#3b82f6",
  "LLM Refused": "#8b5cf6",
  "Output Filter": "#06b6d4",
};

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function ScorecardView({ scorecard }: ScorecardViewProps) {
  const techniqueData = buildTechniqueData(scorecard);
  const layerData = buildLayerData(scorecard);
  const difficultyData = buildDifficultyData(scorecard);

  return (
    <Box>
      {/* Hero metrics */}
      <SimpleGrid columns={{ base: 1, md: 3 }} gap={6} mb={6}>
        {/* Attack block rate ring */}
        <Card.Root>
          <Card.Body>
            <Flex direction="column" align="center" gap={2}>
              <BlockRateRing rate={scorecard.attack_block_rate} />
              <Text fontSize="sm" fontWeight="medium">
                Attack Block Rate
              </Text>
              <Text fontSize="xs" color="fg.muted">
                {scorecard.total_attacks} total attacks
              </Text>
            </Flex>
          </Card.Body>
        </Card.Root>

        {/* False positive rate */}
        <Card.Root>
          <Card.Body>
            <Flex direction="column" align="center" gap={2}>
              <BlockRateRing
                rate={1 - scorecard.false_positive_rate}
                size={120}
              />
              <Text fontSize="sm" fontWeight="medium">
                Benign Pass Rate
              </Text>
              <Text fontSize="xs" color="fg.muted">
                {scorecard.total_benign} benign prompts •{" "}
                {(scorecard.false_positive_rate * 100).toFixed(1)}% false
                positive
              </Text>
            </Flex>
          </Card.Body>
        </Card.Root>

        {/* Summary stats */}
        <Card.Root>
          <Card.Body>
            <Heading size="sm" mb={3}>
              Summary
            </Heading>
            <Flex direction="column" gap={2}>
              <Flex justify="space-between">
                <Text fontSize="sm" color="fg.muted">
                  Total prompts
                </Text>
                <Text fontSize="sm" fontWeight="medium">
                  {scorecard.total_attacks + scorecard.total_benign}
                </Text>
              </Flex>
              <Flex justify="space-between">
                <Text fontSize="sm" color="fg.muted">
                  Attacks blocked
                </Text>
                <Text fontSize="sm" fontWeight="medium">
                  {Math.round(
                    scorecard.attack_block_rate * scorecard.total_attacks,
                  )}{" "}
                  / {scorecard.total_attacks}
                </Text>
              </Flex>
              <Flex justify="space-between">
                <Text fontSize="sm" color="fg.muted">
                  Defense layers
                </Text>
                <Text fontSize="sm" fontWeight="medium">
                  {Object.keys(scorecard.by_layer).length} active
                </Text>
              </Flex>
              <Flex justify="space-between">
                <Text fontSize="sm" color="fg.muted">
                  Techniques tested
                </Text>
                <Text fontSize="sm" fontWeight="medium">
                  {Object.keys(scorecard.by_technique).length}
                </Text>
              </Flex>
            </Flex>
          </Card.Body>
        </Card.Root>
      </SimpleGrid>

      {/* Charts row */}
      <SimpleGrid columns={{ base: 1, lg: 2 }} gap={6} mb={6}>
        {/* By Technique — horizontal bar */}
        <Card.Root>
          <Card.Body>
            <Heading size="sm" mb={3}>
              Block Rate by Technique
            </Heading>
            {techniqueData.length > 0 ? (
              <ResponsiveContainer width="100%" height={techniqueData.length * 40 + 40}>
                <BarChart
                  data={techniqueData}
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
                    formatter={(value: number, _name: string, props: { payload: { blocked: number; total: number } }) => [
                      `${value}% (${props.payload.blocked}/${props.payload.total})`,
                      "Block Rate",
                    ]}
                    contentStyle={{
                      background: "#1a1a2e",
                      border: "1px solid #333",
                      borderRadius: 8,
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="rate" radius={[0, 4, 4, 0]}>
                    {techniqueData.map((entry) => (
                      <Cell
                        key={entry.id}
                        fill={
                          entry.rate >= 80
                            ? "#22c55e"
                            : entry.rate >= 50
                              ? "#f59e0b"
                              : "#ef4444"
                        }
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Text fontSize="sm" color="fg.muted">
                No technique data available
              </Text>
            )}
          </Card.Body>
        </Card.Root>

        {/* By Defense Layer */}
        <Card.Root>
          <Card.Body>
            <Heading size="sm" mb={3}>
              Blocks by Defense Layer
            </Heading>
            {layerData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart
                  data={layerData}
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
                  <Bar dataKey="blocked" radius={[4, 4, 0, 0]}>
                    {layerData.map((entry) => (
                      <Cell
                        key={entry.name}
                        fill={LAYER_COLORS[entry.name] ?? "#6b7280"}
                      />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <Text fontSize="sm" color="fg.muted">
                No layer data available
              </Text>
            )}

            {/* Layer legend */}
            <Flex gap={3} mt={2} wrap="wrap" justify="center">
              {layerData.map((l) => (
                <Flex key={l.name} align="center" gap={1}>
                  <Box
                    w="10px"
                    h="10px"
                    borderRadius="sm"
                    bg={LAYER_COLORS[l.name] ?? "#6b7280"}
                  />
                  <Text fontSize="xs" color="fg.muted">
                    {l.name}: {l.blocked}
                  </Text>
                </Flex>
              ))}
            </Flex>
          </Card.Body>
        </Card.Root>
      </SimpleGrid>

      {/* By Difficulty — line chart */}
      <Card.Root mb={6}>
        <Card.Body>
          <Heading size="sm" mb={3}>
            Block Rate by Difficulty
          </Heading>
          {difficultyData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart
                data={difficultyData}
                margin={{ left: 10, right: 20, top: 5, bottom: 5 }}
              >
                <CartesianGrid strokeDasharray="3 3" opacity={0.1} />
                <XAxis dataKey="name" fontSize={12} />
                <YAxis
                  domain={[0, 100]}
                  tickFormatter={(v: number) => `${v}%`}
                  fontSize={12}
                />
                <Tooltip
                  formatter={(value: number, _name: string, props: { payload: { blocked: number; total: number } }) => [
                    `${value}% (${props.payload.blocked}/${props.payload.total})`,
                    "Block Rate",
                  ]}
                  contentStyle={{
                    background: "#1a1a2e",
                    border: "1px solid #333",
                    borderRadius: 8,
                    fontSize: 12,
                  }}
                />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="rate"
                  name="Block Rate %"
                  stroke="#3b82f6"
                  strokeWidth={2}
                  dot={{ fill: "#3b82f6", r: 4 }}
                  activeDot={{ r: 6 }}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <Text fontSize="sm" color="fg.muted">
              No difficulty data available
            </Text>
          )}

          {/* Difficulty badges */}
          <Flex gap={2} mt={2} wrap="wrap" justify="center">
            {difficultyData.map((d) => (
              <Badge
                key={d.level}
                size="sm"
                colorPalette={blockRateColor(d.rate / 100)}
              >
                {d.name}: {d.rate}%
              </Badge>
            ))}
          </Flex>
        </Card.Body>
      </Card.Root>
    </Box>
  );
}
