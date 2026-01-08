import { Box, Flex, Heading, HStack, Link, Text } from "@chakra-ui/react";
import { Link as RouterLink, Outlet, useLocation } from "react-router-dom";

const NAV_ITEMS = [
  { label: "Dashboard", path: "/" },
  { label: "Taxonomy", path: "/taxonomy" },
  { label: "Sandbox", path: "/sandbox" },
  { label: "Compare", path: "/compare" },
];

export function Layout() {
  const location = useLocation();

  return (
    <Flex direction="column" minH="100vh" bg="bg">
      {/* Top navigation bar */}
      <Box
        as="header"
        borderBottomWidth="1px"
        borderColor="border"
        px={6}
        py={3}
        bg="bg.panel"
      >
        <Flex align="center" justify="space-between" maxW="1400px" mx="auto">
          <HStack gap={8}>
            <RouterLink to="/">
              <HStack gap={2}>
                <Text fontSize="xl" aria-label="shield">🛡️</Text>
                <Heading size="md" fontWeight="bold" letterSpacing="-0.02em">
                  PromptArmor
                </Heading>
              </HStack>
            </RouterLink>

            <HStack as="nav" gap={1}>
              {NAV_ITEMS.map((item) => {
                const isActive =
                  item.path === "/"
                    ? location.pathname === "/"
                    : location.pathname.startsWith(item.path);
                return (
                  <Link
                    key={item.path}
                    asChild
                    px={3}
                    py={1.5}
                    borderRadius="md"
                    fontSize="sm"
                    fontWeight={isActive ? "semibold" : "normal"}
                    bg={isActive ? "bg.emphasized" : "transparent"}
                    _hover={{ bg: "bg.emphasized" }}
                  >
                    <RouterLink to={item.path}>{item.label}</RouterLink>
                  </Link>
                );
              })}
            </HStack>
          </HStack>

          <HStack gap={4}>
            <Link
              href="https://github.com"
              target="_blank"
              fontSize="sm"
              color="fg.muted"
              _hover={{ color: "fg" }}
            >
              GitHub
            </Link>
          </HStack>
        </Flex>
      </Box>

      {/* Page content */}
      <Box as="main" flex="1" maxW="1400px" mx="auto" w="full" px={6} py={6}>
        <Outlet />
      </Box>

      {/* Footer */}
      <Box
        as="footer"
        borderTopWidth="1px"
        borderColor="border"
        px={6}
        py={4}
      >
        <Text fontSize="xs" color="fg.muted" textAlign="center">
          PromptArmor — Prompt injection defense testing sandbox. Built with
          FastAPI, React, and Claude.
        </Text>
      </Box>
    </Flex>
  );
}
