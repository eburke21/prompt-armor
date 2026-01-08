import {
  Badge,
  Box,
  Button,
  Card,
  Code,
  Flex,
  Heading,
  Skeleton,
  Text,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link as RouterLink, useParams } from "react-router-dom";
import { getAttacks } from "../api";
import type { AttackPromptDetail } from "../api/types";
import { DATASET_NAMES, DIFFICULTY_LABELS, TECHNIQUE_INFO } from "../theme/constants";

export function TechniqueDetail() {
  const { technique } = useParams<{ technique: string }>();
  const [page, setPage] = useState(0);
  const limit = 20;

  const info = technique ? TECHNIQUE_INFO[technique] : undefined;

  const { data, isLoading } = useQuery({
    queryKey: ["attacks", technique, page],
    queryFn: () =>
      getAttacks({ technique, limit, offset: page * limit }),
    enabled: !!technique,
  });

  return (
    <Box>
      {/* Breadcrumb */}
      <Flex gap={2} mb={4} fontSize="sm" color="fg.muted">
        <RouterLink to="/taxonomy">
          <Text _hover={{ textDecoration: "underline" }}>Taxonomy</Text>
        </RouterLink>
        <Text>/</Text>
        <Text fontWeight="semibold" color="fg">
          {info?.name ?? technique}
        </Text>
      </Flex>

      {/* Header */}
      <Box mb={8}>
        <Heading size="xl" mb={2}>
          {info?.name ?? technique}
        </Heading>
        <Text color="fg.muted" maxW="800px" lineHeight="tall">
          {info?.longDescription ?? info?.description ?? ""}
        </Text>
        {data && (
          <Text fontSize="sm" color="fg.muted" mt={2}>
            {data.total.toLocaleString()} prompts total
          </Text>
        )}
      </Box>

      {/* Example prompts */}
      <Heading size="md" mb={4}>
        Example Prompts
      </Heading>

      {isLoading ? (
        <Box>
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} height="80px" mb={3} borderRadius="lg" />
          ))}
        </Box>
      ) : (
        <Box>
          {data?.attacks.map((attack) => (
            <PromptCard key={attack.id} attack={attack} />
          ))}

          {/* Pagination */}
          {data && data.total > limit && (
            <Flex justify="center" gap={4} mt={6}>
              <Button
                size="sm"
                variant="outline"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </Button>
              <Text fontSize="sm" color="fg.muted" alignSelf="center">
                Page {page + 1} of {Math.ceil(data.total / limit)}
              </Text>
              <Button
                size="sm"
                variant="outline"
                disabled={(page + 1) * limit >= data.total}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </Flex>
          )}
        </Box>
      )}
    </Box>
  );
}

function PromptCard({ attack }: { attack: AttackPromptDetail }) {
  const [expanded, setExpanded] = useState(false);
  const text = attack.prompt_text;
  const isLong = text.length > 200;
  const displayText = expanded || !isLong ? text : text.slice(0, 200) + "...";

  return (
    <Card.Root mb={3} size="sm">
      <Card.Body>
        <Flex gap={2} mb={2} wrap="wrap">
          <Badge size="sm" colorPalette="gray">
            {DATASET_NAMES[attack.source_dataset] ?? attack.source_dataset}
          </Badge>
          {attack.difficulty_estimate && (
            <Badge
              size="sm"
              colorPalette={
                attack.difficulty_estimate <= 2
                  ? "green"
                  : attack.difficulty_estimate <= 3
                    ? "yellow"
                    : "red"
              }
            >
              {DIFFICULTY_LABELS[attack.difficulty_estimate] ??
                `Difficulty ${attack.difficulty_estimate}`}
            </Badge>
          )}
          {attack.language !== "en" && (
            <Badge size="sm" colorPalette="purple">
              {attack.language}
            </Badge>
          )}
          {attack.is_injection ? (
            <Badge size="sm" colorPalette="red">
              Injection
            </Badge>
          ) : (
            <Badge size="sm" colorPalette="green">
              Benign
            </Badge>
          )}
        </Flex>

        <Code
          display="block"
          whiteSpace="pre-wrap"
          p={3}
          fontSize="sm"
          bg="bg.emphasized"
          borderRadius="md"
        >
          {displayText}
        </Code>

        <Flex justify="space-between" mt={2}>
          {isLong && (
            <Button
              size="xs"
              variant="ghost"
              onClick={() => setExpanded(!expanded)}
            >
              {expanded ? "Show less" : "Show more"}
            </Button>
          )}
          <Button asChild size="xs" variant="outline" colorPalette="blue" ml="auto">
            <RouterLink to="/sandbox">Use in Sandbox</RouterLink>
          </Button>
        </Flex>
      </Card.Body>
    </Card.Root>
  );
}
