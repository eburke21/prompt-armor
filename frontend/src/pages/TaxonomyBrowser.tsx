import {
  Badge,
  Box,
  Card,
  Flex,
  Heading,
  Input,
  SimpleGrid,
  Skeleton,
  Text,
} from "@chakra-ui/react";
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link as RouterLink } from "react-router-dom";
import { getTaxonomy } from "../api";
import { TECHNIQUE_INFO } from "../theme/constants";

export function TaxonomyBrowser() {
  const { data, isLoading } = useQuery({
    queryKey: ["taxonomy"],
    queryFn: getTaxonomy,
  });

  const [search, setSearch] = useState("");

  const filteredTechniques = useMemo(() => {
    if (!data) return [];
    if (!search.trim()) return data.techniques;
    const q = search.toLowerCase();
    return data.techniques.filter((t) => {
      const info = TECHNIQUE_INFO[t.id];
      return (
        t.id.includes(q) ||
        (info?.name.toLowerCase().includes(q) ?? false) ||
        (info?.description.toLowerCase().includes(q) ?? false)
      );
    });
  }, [data, search]);

  return (
    <Box>
      <Flex justify="space-between" align="center" mb={6}>
        <Box>
          <Heading size="xl" mb={1}>
            Attack Taxonomy
          </Heading>
          <Text color="fg.muted">
            {data
              ? `${data.total_injections.toLocaleString()} injection prompts across ${data.techniques.length} techniques`
              : "Loading..."}
          </Text>
        </Box>
      </Flex>

      {/* Search */}
      <Box mb={6} maxW="400px">
        <Input
          placeholder="Search techniques..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          size="sm"
        />
      </Box>

      {/* Technique grid */}
      {isLoading ? (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
          {Array.from({ length: 6 }).map((_, i) => (
            <Skeleton key={i} height="180px" borderRadius="lg" />
          ))}
        </SimpleGrid>
      ) : (
        <SimpleGrid columns={{ base: 1, md: 2, lg: 3 }} gap={4}>
          {filteredTechniques.map((technique) => {
            const info = TECHNIQUE_INFO[technique.id];
            return (
              <RouterLink key={technique.id} to={`/taxonomy/${technique.id}`}>
                <Card.Root
                  size="sm"
                  _hover={{
                    borderColor: "blue.500",
                    shadow: "md",
                    transform: "translateY(-1px)",
                  }}
                  transition="all 0.15s"
                  cursor="pointer"
                  h="full"
                >
                  <Card.Body>
                    <Flex justify="space-between" align="start" mb={2}>
                      <Heading size="sm">
                        {info?.name ?? technique.id}
                      </Heading>
                      <Badge colorPalette="blue" size="sm">
                        {technique.example_count.toLocaleString()}
                      </Badge>
                    </Flex>

                    <Text fontSize="sm" color="fg.muted" mb={3}>
                      {info?.description ?? ""}
                    </Text>

                    {/* Mini difficulty distribution */}
                    <DifficultyBar
                      distribution={technique.difficulty_distribution}
                    />
                  </Card.Body>
                </Card.Root>
              </RouterLink>
            );
          })}
        </SimpleGrid>
      )}

      {filteredTechniques.length === 0 && !isLoading && (
        <Box textAlign="center" py={12}>
          <Text color="fg.muted">
            No techniques match &quot;{search}&quot;
          </Text>
        </Box>
      )}
    </Box>
  );
}

function DifficultyBar({
  distribution,
}: {
  distribution: Record<string, number>;
}) {
  const total = Object.values(distribution).reduce((a, b) => a + b, 0);
  if (total === 0) return null;

  const colors = ["green.500", "teal.500", "yellow.500", "orange.500", "red.500"];

  return (
    <Box>
      <Text fontSize="xs" color="fg.muted" mb={1}>
        Difficulty distribution
      </Text>
      <Flex h="6px" borderRadius="full" overflow="hidden" gap="1px">
        {[1, 2, 3, 4, 5].map((level) => {
          const count = distribution[String(level)] ?? 0;
          const pct = (count / total) * 100;
          return (
            <Box
              key={level}
              bg={colors[level - 1]}
              w={`${pct}%`}
              minW={count > 0 ? "2px" : "0"}
              title={`Difficulty ${level}: ${count}`}
            />
          );
        })}
      </Flex>
      <Flex justify="space-between" mt={1}>
        <Text fontSize="xs" color="fg.muted">
          Easy
        </Text>
        <Text fontSize="xs" color="fg.muted">
          Hard
        </Text>
      </Flex>
    </Box>
  );
}
