import {
  Badge,
  Box,
  Button,
  Card,
  Flex,
  Heading,
  SimpleGrid,
  Skeleton,
  Text,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { Link as RouterLink } from "react-router-dom";
import { getTaxonomy } from "../api";

export function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["taxonomy"],
    queryFn: getTaxonomy,
  });

  return (
    <Box>
      {/* Hero section */}
      <Box textAlign="center" py={12}>
        <Heading size="3xl" fontWeight="bold" mb={3}>
          <Text as="span" aria-label="shield">🛡️</Text> PromptArmor
        </Heading>
        <Text fontSize="lg" color="fg.muted" maxW="600px" mx="auto" mb={8}>
          Explore real-world prompt injection techniques, test your defenses
          against curated attack datasets, and generate red team assessment
          reports.
        </Text>
        <Flex gap={4} justify="center">
          <Button asChild size="lg" colorPalette="blue">
            <RouterLink to="/sandbox">Try the Sandbox</RouterLink>
          </Button>
          <Button asChild size="lg" variant="outline">
            <RouterLink to="/taxonomy">Browse Taxonomy</RouterLink>
          </Button>
        </Flex>
      </Box>

      {/* Stats grid */}
      <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} gap={6} mb={12}>
        <StatCard
          label="Total Prompts"
          value={data?.total_prompts}
          isLoading={isLoading}
        />
        <StatCard
          label="Injection Prompts"
          value={data?.total_injections}
          isLoading={isLoading}
          color="red"
        />
        <StatCard
          label="Benign Prompts"
          value={data?.total_benign}
          isLoading={isLoading}
          color="green"
        />
        <StatCard
          label="Technique Categories"
          value={data?.techniques.length}
          isLoading={isLoading}
          color="blue"
        />
      </SimpleGrid>

      {/* Dataset info */}
      {data && (
        <Box mb={12}>
          <Heading size="lg" mb={4}>
            Datasets
          </Heading>
          <SimpleGrid columns={{ base: 1, sm: 2, md: 4 }} gap={4}>
            {data.datasets.map((ds) => (
              <Card.Root key={ds.id} size="sm">
                <Card.Body>
                  <Text fontWeight="semibold" fontSize="sm" mb={1}>
                    {ds.name}
                  </Text>
                  <Flex gap={2} align="center">
                    <Text fontSize="2xl" fontWeight="bold">
                      {ds.count.toLocaleString()}
                    </Text>
                    <Badge size="sm">{ds.license}</Badge>
                  </Flex>
                </Card.Body>
              </Card.Root>
            ))}
          </SimpleGrid>
        </Box>
      )}

      {/* What is this */}
      <Box maxW="700px" mx="auto" textAlign="center" pb={8}>
        <Heading size="md" mb={3}>
          What is PromptArmor?
        </Heading>
        <Text color="fg.muted" fontSize="sm" lineHeight="tall">
          Prompt injection is the #1 vulnerability in the OWASP Top 10 for LLM
          Applications. PromptArmor combines curated attack datasets from 4
          sources with an interactive defense testing sandbox, letting you
          explore attack techniques, benchmark your system prompts and
          guardrails, and generate professional red team reports.
        </Text>
      </Box>

      {error && (
        <Box textAlign="center" color="red.500">
          <Text>Failed to load data: {String(error)}</Text>
        </Box>
      )}
    </Box>
  );
}

function StatCard({
  label,
  value,
  isLoading,
  color,
}: {
  label: string;
  value?: number;
  isLoading: boolean;
  color?: string;
}) {
  return (
    <Card.Root>
      <Card.Body>
        <Text fontSize="sm" color="fg.muted" mb={1}>
          {label}
        </Text>
        {isLoading ? (
          <Skeleton height="36px" width="120px" />
        ) : (
          <Text
            fontSize="3xl"
            fontWeight="bold"
            color={color ? `${color}.500` : undefined}
          >
            {value?.toLocaleString() ?? "—"}
          </Text>
        )}
      </Card.Body>
    </Card.Root>
  );
}
