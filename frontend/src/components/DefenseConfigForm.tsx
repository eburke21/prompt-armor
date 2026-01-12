/**
 * DefenseConfigForm — reusable defense configuration panel.
 *
 * Includes: system prompt editor, input filters (keyword blocklist,
 * OpenAI moderation), output filters (secret leak detector).
 *
 * Used by both Sandbox and Compare pages.
 */

import {
  Badge,
  Box,
  Button,
  Card,
  Checkbox,
  Flex,
  Heading,
  Input,
  Separator,
  Slider,
  Text,
  Textarea,
} from "@chakra-ui/react";
import { useCallback, useState } from "react";

import type { DefenseConfig } from "../api/types";

const DEFAULT_KEYWORDS = [
  "ignore previous",
  "ignore all instructions",
  "DAN",
  "jailbreak",
  "disregard",
];

interface DefenseConfigFormProps {
  /** Label displayed at the top, e.g. "Config A" */
  label: string;
  /** Color for the accent border */
  accentColor?: string;
  /** Initial values (for preset loading) */
  initialConfig?: Partial<DefenseConfig>;
  /** Controlled callback — fires on every change */
  onChange: (config: DefenseConfig) => void;
  /** Compact mode for side-by-side layouts */
  compact?: boolean;
}

export function DefenseConfigForm({
  label,
  accentColor = "#3b82f6",
  initialConfig,
  onChange,
  compact = false,
}: DefenseConfigFormProps) {
  // --- Form state ---
  const [systemPrompt, setSystemPrompt] = useState(
    initialConfig?.system_prompt ?? "",
  );
  const [keywordEnabled, setKeywordEnabled] = useState(
    initialConfig?.input_filters?.some((f) => f.type === "keyword_blocklist") ??
      true,
  );
  const [keywords, setKeywords] = useState<string[]>(() => {
    const kf = initialConfig?.input_filters?.find(
      (f) => f.type === "keyword_blocklist",
    );
    if (kf && kf.type === "keyword_blocklist") return kf.keywords;
    return DEFAULT_KEYWORDS;
  });
  const [keywordInput, setKeywordInput] = useState("");
  const [moderationEnabled, setModerationEnabled] = useState(
    initialConfig?.input_filters?.some(
      (f) => f.type === "openai_moderation",
    ) ?? false,
  );
  const [moderationThreshold, setModerationThreshold] = useState(() => {
    const mf = initialConfig?.input_filters?.find(
      (f) => f.type === "openai_moderation",
    );
    if (mf && mf.type === "openai_moderation") return mf.threshold;
    return 0.7;
  });
  const [secretEnabled, setSecretEnabled] = useState(
    initialConfig?.output_filters?.some(
      (f) => f.type === "secret_leak_detector",
    ) ?? false,
  );
  const [secrets, setSecrets] = useState<string[]>(() => {
    const sf = initialConfig?.output_filters?.find(
      (f) => f.type === "secret_leak_detector",
    );
    if (sf && sf.type === "secret_leak_detector") return sf.secrets;
    return [];
  });
  const [secretInput, setSecretInput] = useState("");

  // --- Build and emit DefenseConfig on any change ---
  const emitConfig = useCallback(
    (overrides: {
      systemPrompt?: string;
      keywordEnabled?: boolean;
      keywords?: string[];
      moderationEnabled?: boolean;
      moderationThreshold?: number;
      secretEnabled?: boolean;
      secrets?: string[];
    }) => {
      const sp = overrides.systemPrompt ?? systemPrompt;
      const kwE = overrides.keywordEnabled ?? keywordEnabled;
      const kws = overrides.keywords ?? keywords;
      const modE = overrides.moderationEnabled ?? moderationEnabled;
      const modT = overrides.moderationThreshold ?? moderationThreshold;
      const secE = overrides.secretEnabled ?? secretEnabled;
      const secs = overrides.secrets ?? secrets;

      const config: DefenseConfig = {
        system_prompt: sp,
        input_filters: [],
        output_filters: [],
      };

      if (kwE && kws.length > 0) {
        config.input_filters.push({
          type: "keyword_blocklist",
          enabled: true,
          keywords: kws,
        });
      }
      if (modE) {
        config.input_filters.push({
          type: "openai_moderation",
          enabled: true,
          threshold: modT,
          categories: ["harassment", "violence", "illicit"],
        });
      }
      if (secE && secs.length > 0) {
        config.output_filters.push({
          type: "secret_leak_detector",
          enabled: true,
          secrets: secs,
          patterns: [],
        });
      }

      onChange(config);
    },
    [
      systemPrompt,
      keywordEnabled,
      keywords,
      moderationEnabled,
      moderationThreshold,
      secretEnabled,
      secrets,
      onChange,
    ],
  );

  const updateSystemPrompt = (v: string) => {
    setSystemPrompt(v);
    emitConfig({ systemPrompt: v });
  };

  const addKeyword = () => {
    const kw = keywordInput.trim();
    if (kw && !keywords.includes(kw)) {
      const next = [...keywords, kw];
      setKeywords(next);
      setKeywordInput("");
      emitConfig({ keywords: next });
    }
  };

  const removeKeyword = (kw: string) => {
    const next = keywords.filter((k) => k !== kw);
    setKeywords(next);
    emitConfig({ keywords: next });
  };

  const addSecret = () => {
    const s = secretInput.trim();
    if (s && !secrets.includes(s)) {
      const next = [...secrets, s];
      setSecrets(next);
      setSecretInput("");
      emitConfig({ secrets: next });
    }
  };

  const removeSecret = (s: string) => {
    const next = secrets.filter((x) => x !== s);
    setSecrets(next);
    emitConfig({ secrets: next });
  };

  return (
    <Card.Root borderTop="3px solid" borderTopColor={accentColor}>
      <Card.Body>
        <Flex align="center" gap={2} mb={3}>
          <Box w="12px" h="12px" borderRadius="full" bg={accentColor} />
          <Heading size="sm">{label}</Heading>
        </Flex>

        {/* System Prompt */}
        <Box mb={3}>
          <Text fontSize="sm" fontWeight="medium" mb={1}>
            System Prompt
          </Text>
          <Textarea
            value={systemPrompt}
            onChange={(e) => updateSystemPrompt(e.target.value)}
            placeholder="You are a helpful assistant..."
            rows={compact ? 4 : 6}
            fontFamily="mono"
            fontSize="sm"
          />
        </Box>

        <Separator mb={3} />

        {/* Keyword Blocklist */}
        <Box mb={3}>
          <Flex align="center" gap={2} mb={2}>
            <Checkbox.Root
              checked={keywordEnabled}
              onCheckedChange={(e) => {
                const v = !!e.checked;
                setKeywordEnabled(v);
                emitConfig({ keywordEnabled: v });
              }}
            >
              <Checkbox.HiddenInput />
              <Checkbox.Control />
              <Checkbox.Label fontSize="sm">Keyword Blocklist</Checkbox.Label>
            </Checkbox.Root>
          </Flex>
          {keywordEnabled && (
            <Box pl={6}>
              <Flex gap={1} wrap="wrap" mb={2}>
                {keywords.map((kw) => (
                  <Badge
                    key={kw}
                    size="sm"
                    cursor="pointer"
                    onClick={() => removeKeyword(kw)}
                    title="Click to remove"
                  >
                    {kw} ✕
                  </Badge>
                ))}
              </Flex>
              <Flex gap={2}>
                <Input
                  size="sm"
                  placeholder="Add keyword..."
                  value={keywordInput}
                  onChange={(e) => setKeywordInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addKeyword()}
                />
                <Button size="sm" onClick={addKeyword}>
                  Add
                </Button>
              </Flex>
            </Box>
          )}
        </Box>

        {/* OpenAI Moderation */}
        <Box mb={3}>
          <Flex align="center" gap={2} mb={2}>
            <Checkbox.Root
              checked={moderationEnabled}
              onCheckedChange={(e) => {
                const v = !!e.checked;
                setModerationEnabled(v);
                emitConfig({ moderationEnabled: v });
              }}
            >
              <Checkbox.HiddenInput />
              <Checkbox.Control />
              <Checkbox.Label fontSize="sm">
                OpenAI Moderation API
              </Checkbox.Label>
            </Checkbox.Root>
          </Flex>
          {moderationEnabled && (
            <Box pl={6}>
              <Text fontSize="xs" mb={1}>
                Threshold: {moderationThreshold.toFixed(1)}
              </Text>
              <Slider.Root
                min={0.1}
                max={1}
                step={0.1}
                value={[moderationThreshold]}
                onValueChange={(e) => {
                  setModerationThreshold(e.value[0]);
                  emitConfig({ moderationThreshold: e.value[0] });
                }}
                size="sm"
              >
                <Slider.Control>
                  <Slider.Track>
                    <Slider.Range />
                  </Slider.Track>
                  <Slider.Thumb index={0} />
                </Slider.Control>
              </Slider.Root>
            </Box>
          )}
        </Box>

        <Separator mb={3} />

        {/* Secret Leak Detector */}
        <Box>
          <Flex align="center" gap={2} mb={2}>
            <Checkbox.Root
              checked={secretEnabled}
              onCheckedChange={(e) => {
                const v = !!e.checked;
                setSecretEnabled(v);
                emitConfig({ secretEnabled: v });
              }}
            >
              <Checkbox.HiddenInput />
              <Checkbox.Control />
              <Checkbox.Label fontSize="sm">
                Secret Leak Detector
              </Checkbox.Label>
            </Checkbox.Root>
          </Flex>
          {secretEnabled && (
            <Box pl={6}>
              <Flex gap={1} wrap="wrap" mb={2}>
                {secrets.map((s) => (
                  <Badge
                    key={s}
                    size="sm"
                    cursor="pointer"
                    onClick={() => removeSecret(s)}
                    title="Click to remove"
                  >
                    {s} ✕
                  </Badge>
                ))}
              </Flex>
              <Flex gap={2}>
                <Input
                  size="sm"
                  placeholder="Add secret string..."
                  value={secretInput}
                  onChange={(e) => setSecretInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && addSecret()}
                />
                <Button size="sm" onClick={addSecret}>
                  Add
                </Button>
              </Flex>
            </Box>
          )}
        </Box>
      </Card.Body>
    </Card.Root>
  );
}
