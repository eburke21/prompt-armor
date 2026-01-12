/**
 * ReportViewer — renders a Claude-generated Markdown report with actions.
 *
 * Features:
 * - Markdown rendering with react-markdown + remark-gfm
 * - Dark-theme styled tables, code blocks, and headings
 * - Copy to clipboard
 * - Download as .md file
 * - Regenerate button
 */

import {
  Box,
  Button,
  Card,
  Flex,
  Heading,
  Table,
  Text,
} from "@chakra-ui/react";
import { useCallback, useState } from "react";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface ReportViewerProps {
  markdown: string;
  modelUsed?: string;
  onRegenerate?: () => void;
  isRegenerating?: boolean;
}

export function ReportViewer({
  markdown,
  modelUsed,
  onRegenerate,
  isRegenerating,
}: ReportViewerProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(markdown);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = markdown;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, [markdown]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([markdown], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "promptarmor-report.md";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [markdown]);

  return (
    <Box>
      {/* Action bar */}
      <Card.Root mb={4}>
        <Card.Body>
          <Flex justify="space-between" align="center" wrap="wrap" gap={3}>
            <Flex align="center" gap={2}>
              <Heading size="sm">Generated Report</Heading>
              {modelUsed && (
                <Text fontSize="xs" color="fg.muted">
                  via {modelUsed}
                </Text>
              )}
            </Flex>
            <Flex gap={2}>
              <Button size="sm" variant="outline" onClick={handleCopy}>
                {copied ? "Copied!" : "Copy Markdown"}
              </Button>
              <Button size="sm" variant="outline" onClick={handleDownload}>
                Download .md
              </Button>
              {onRegenerate && (
                <Button
                  size="sm"
                  colorPalette="blue"
                  onClick={onRegenerate}
                  loading={isRegenerating}
                >
                  Regenerate
                </Button>
              )}
            </Flex>
          </Flex>
        </Card.Body>
      </Card.Root>

      {/* Rendered Markdown */}
      <Card.Root>
        <Card.Body>
          <Box className="report-markdown">
            <Markdown
              remarkPlugins={[remarkGfm]}
              components={{
                // Headings
                h1: ({ children }) => (
                  <Heading size="xl" mb={4} mt={6}>
                    {children}
                  </Heading>
                ),
                h2: ({ children }) => (
                  <Heading size="lg" mb={3} mt={5} pb={2} borderBottomWidth="1px" borderColor="border">
                    {children}
                  </Heading>
                ),
                h3: ({ children }) => (
                  <Heading size="md" mb={2} mt={4}>
                    {children}
                  </Heading>
                ),
                // Paragraphs
                p: ({ children }) => (
                  <Text mb={3} lineHeight="tall">
                    {children}
                  </Text>
                ),
                // Strong
                strong: ({ children }) => (
                  <Text as="span" fontWeight="bold" color="fg">
                    {children}
                  </Text>
                ),
                // Tables — styled for dark theme
                table: ({ children }) => (
                  <Box overflowX="auto" mb={4}>
                    <Table.Root size="sm" variant="outline">
                      {children}
                    </Table.Root>
                  </Box>
                ),
                thead: ({ children }) => (
                  <Table.Header>{children}</Table.Header>
                ),
                tbody: ({ children }) => (
                  <Table.Body>{children}</Table.Body>
                ),
                tr: ({ children }) => (
                  <Table.Row>{children}</Table.Row>
                ),
                th: ({ children }) => (
                  <Table.ColumnHeader fontSize="xs" fontWeight="semibold">
                    {children}
                  </Table.ColumnHeader>
                ),
                td: ({ children }) => (
                  <Table.Cell fontSize="sm">{children}</Table.Cell>
                ),
                // Lists
                ul: ({ children }) => (
                  <Box as="ul" pl={6} mb={3} listStyleType="disc">
                    {children}
                  </Box>
                ),
                ol: ({ children }) => (
                  <Box as="ol" pl={6} mb={3} listStyleType="decimal">
                    {children}
                  </Box>
                ),
                li: ({ children }) => (
                  <Box as="li" mb={1} fontSize="sm" lineHeight="tall">
                    {children}
                  </Box>
                ),
                // Blockquotes — for notable prompt examples
                blockquote: ({ children }) => (
                  <Box
                    borderLeftWidth="3px"
                    borderColor="blue.500"
                    pl={4}
                    py={2}
                    mb={3}
                    bg="bg.subtle"
                    borderRadius="md"
                    fontStyle="italic"
                  >
                    {children}
                  </Box>
                ),
                // Code
                code: ({ children, className }) => {
                  const isBlock = className?.startsWith("language-");
                  if (isBlock) {
                    return (
                      <Box
                        as="pre"
                        bg="bg.subtle"
                        p={3}
                        borderRadius="md"
                        overflowX="auto"
                        mb={3}
                        fontSize="sm"
                        fontFamily="mono"
                      >
                        <code>{children}</code>
                      </Box>
                    );
                  }
                  return (
                    <Text
                      as="code"
                      bg="bg.subtle"
                      px={1}
                      py={0.5}
                      borderRadius="sm"
                      fontSize="sm"
                      fontFamily="mono"
                    >
                      {children}
                    </Text>
                  );
                },
                // Horizontal rule
                hr: () => (
                  <Box borderBottomWidth="1px" borderColor="border" my={4} />
                ),
              }}
            >
              {markdown}
            </Markdown>
          </Box>
        </Card.Body>
      </Card.Root>
    </Box>
  );
}
