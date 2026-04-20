/**
 * Top-level error boundary — catches render-time exceptions in the React tree
 * and shows a friendly fallback instead of a blank white screen.
 *
 * React's render-error catching hook (`componentDidCatch`) is only available
 * on class components, so this intentionally uses the class form despite the
 * rest of the codebase being hooks-based.
 */

import { Box, Button, Code, Flex, Heading, Text } from "@chakra-ui/react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error:", error, info);
  }

  handleReload = () => {
    window.location.reload();
  };

  render() {
    if (!this.state.error) {
      return this.props.children;
    }
    return (
      <Flex
        minH="100vh"
        align="center"
        justify="center"
        p={8}
        direction="column"
        gap={4}
      >
        <Heading size="lg">Something went wrong</Heading>
        <Text color="fg.muted" maxW="600px" textAlign="center">
          The page crashed while rendering. This isn't supposed to happen —
          reloading usually recovers it.
        </Text>
        <Box
          bg="bg.subtle"
          borderRadius="md"
          p={3}
          maxW="600px"
          overflow="auto"
        >
          <Code fontSize="xs" whiteSpace="pre-wrap">
            {this.state.error.message}
          </Code>
        </Box>
        <Button onClick={this.handleReload} colorPalette="blue">
          Reload Page
        </Button>
      </Flex>
    );
  }
}
