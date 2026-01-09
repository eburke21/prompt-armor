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
import { useQuery } from "@tanstack/react-query";
import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { getSystemPrompts, getTaxonomy, startEvalRun } from "../api";
import type {
  AttackSetConfig,
  DefenseConfig,
  EvalRunCreate,
} from "../api/types";
import { TECHNIQUE_INFO } from "../theme/constants";

const ALL_TECHNIQUES = Object.keys(TECHNIQUE_INFO).filter(
  (t) => t !== "unclassified"
);

const DEFAULT_KEYWORDS = [
  "ignore previous",
  "ignore all instructions",
  "DAN",
  "jailbreak",
  "disregard",
];

export function Sandbox() {
  const navigate = useNavigate();

  // --- Form state ---
  const [systemPrompt, setSystemPrompt] = useState("");
  const [keywordEnabled, setKeywordEnabled] = useState(true);
  const [keywords, setKeywords] = useState<string[]>(DEFAULT_KEYWORDS);
  const [keywordInput, setKeywordInput] = useState("");
  const [moderationEnabled, setModerationEnabled] = useState(false);
  const [moderationThreshold, setModerationThreshold] = useState(0.7);
  const [secretEnabled, setSecretEnabled] = useState(false);
  const [secrets, setSecrets] = useState<string[]>([]);
  const [secretInput, setSecretInput] = useState("");
  const [selectedTechniques, setSelectedTechniques] =
    useState<string[]>(ALL_TECHNIQUES);
  const [difficultyRange, setDifficultyRange] = useState<[number, number]>([
    1, 5,
  ]);
  const [promptCount, setPromptCount] = useState(20);
  const [includeBenign, setIncludeBenign] = useState(true);
  const [benignRatio, setBenignRatio] = useState(0.3);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // --- Fetch presets ---
  const { data: presets } = useQuery({
    queryKey: ["system-prompts", "builtin"],
    queryFn: () => getSystemPrompts({ source: "builtin" }),
  });

  const { data: taxonomy } = useQuery({
    queryKey: ["taxonomy"],
    queryFn: getTaxonomy,
  });

  // --- Handlers ---
  const handleTechniqueToggle = useCallback(
    (technique: string) => {
      setSelectedTechniques((prev) =>
        prev.includes(technique)
          ? prev.filter((t) => t !== technique)
          : [...prev, technique]
      );
    },
    []
  );

  const addKeyword = useCallback(() => {
    const kw = keywordInput.trim();
    if (kw && !keywords.includes(kw)) {
      setKeywords((prev) => [...prev, kw]);
      setKeywordInput("");
    }
  }, [keywordInput, keywords]);

  const addSecret = useCallback(() => {
    const s = secretInput.trim();
    if (s && !secrets.includes(s)) {
      setSecrets((prev) => [...prev, s]);
      setSecretInput("");
    }
  }, [secretInput, secrets]);

  const handleSubmit = useCallback(async () => {
    setError(null);
    setIsSubmitting(true);

    const defenseConfig: DefenseConfig = {
      system_prompt: systemPrompt,
      input_filters: [],
      output_filters: [],
    };

    if (keywordEnabled && keywords.length > 0) {
      defenseConfig.input_filters.push({
        type: "keyword_blocklist",
        enabled: true,
        keywords,
      });
    }
    if (moderationEnabled) {
      defenseConfig.input_filters.push({
        type: "openai_moderation",
        enabled: true,
        threshold: moderationThreshold,
        categories: ["harassment", "violence", "illicit"],
      });
    }
    if (secretEnabled && secrets.length > 0) {
      defenseConfig.output_filters.push({
        type: "secret_leak_detector",
        enabled: true,
        secrets,
        patterns: [],
      });
    }

    const attackSet: AttackSetConfig = {
      techniques: selectedTechniques,
      difficulty_range: difficultyRange,
      count: promptCount,
      include_benign: includeBenign,
      benign_ratio: benignRatio,
    };

    const config: EvalRunCreate = {
      defense_config: defenseConfig,
      attack_set: attackSet,
    };

    try {
      const result = await startEvalRun(config);
      navigate(`/sandbox/${result.eval_run_id}`);
    } catch (err) {
      setError(String(err));
      setIsSubmitting(false);
    }
  }, [
    systemPrompt,
    keywordEnabled,
    keywords,
    moderationEnabled,
    moderationThreshold,
    secretEnabled,
    secrets,
    selectedTechniques,
    difficultyRange,
    promptCount,
    includeBenign,
    benignRatio,
    navigate,
  ]);

  const canSubmit = systemPrompt.trim().length > 0 && selectedTechniques.length > 0 && promptCount > 0;

  return (
    <Box>
      <Heading size="xl" mb={2}>
        Defense Sandbox
      </Heading>
      <Text color="fg.muted" mb={6}>
        Configure your defense, select an attack set, and see how your system
        prompt and filters hold up.
      </Text>

      <Flex gap={6} direction={{ base: "column", lg: "row" }}>
        {/* Left: Config panel */}
        <Box flex="1">
          {/* System prompt */}
          <Card.Root mb={4}>
            <Card.Body>
              <Heading size="sm" mb={3}>
                System Prompt
              </Heading>

              {presets && presets.length > 0 && (
                <Flex gap={2} mb={3} wrap="wrap">
                  {presets.map((p) => (
                    <Button
                      key={p.id}
                      size="xs"
                      variant={
                        systemPrompt === p.prompt_text ? "solid" : "outline"
                      }
                      colorPalette="blue"
                      onClick={() => setSystemPrompt(p.prompt_text)}
                    >
                      {p.name ?? p.id}
                    </Button>
                  ))}
                </Flex>
              )}

              <Textarea
                value={systemPrompt}
                onChange={(e) => setSystemPrompt(e.target.value)}
                placeholder="You are a helpful assistant. Never reveal..."
                rows={6}
                fontFamily="mono"
                fontSize="sm"
              />
            </Card.Body>
          </Card.Root>

          {/* Input filters */}
          <Card.Root mb={4}>
            <Card.Body>
              <Heading size="sm" mb={3}>
                Input Filters
              </Heading>

              {/* Keyword blocklist */}
              <Box mb={4}>
                <Flex align="center" gap={2} mb={2}>
                  <Checkbox.Root
                    checked={keywordEnabled}
                    onCheckedChange={(e) =>
                      setKeywordEnabled(!!e.checked)
                    }
                  >
                    <Checkbox.HiddenInput />
                    <Checkbox.Control />
                    <Checkbox.Label>Keyword Blocklist</Checkbox.Label>
                  </Checkbox.Root>
                </Flex>
                {keywordEnabled && (
                  <Box pl={6}>
                    <Flex gap={2} wrap="wrap" mb={2}>
                      {keywords.map((kw) => (
                        <Badge
                          key={kw}
                          size="sm"
                          cursor="pointer"
                          onClick={() =>
                            setKeywords((prev) =>
                              prev.filter((k) => k !== kw)
                            )
                          }
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
                        onKeyDown={(e) =>
                          e.key === "Enter" && addKeyword()
                        }
                      />
                      <Button size="sm" onClick={addKeyword}>
                        Add
                      </Button>
                    </Flex>
                  </Box>
                )}
              </Box>

              <Separator mb={4} />

              {/* OpenAI Moderation */}
              <Box>
                <Flex align="center" gap={2} mb={2}>
                  <Checkbox.Root
                    checked={moderationEnabled}
                    onCheckedChange={(e) =>
                      setModerationEnabled(!!e.checked)
                    }
                  >
                    <Checkbox.HiddenInput />
                    <Checkbox.Control />
                    <Checkbox.Label>
                      OpenAI Moderation API
                    </Checkbox.Label>
                  </Checkbox.Root>
                </Flex>
                {moderationEnabled && (
                  <Box pl={6}>
                    <Text fontSize="sm" mb={1}>
                      Threshold: {moderationThreshold.toFixed(1)}
                    </Text>
                    <Slider.Root
                      min={0.1}
                      max={1}
                      step={0.1}
                      value={[moderationThreshold]}
                      onValueChange={(e) =>
                        setModerationThreshold(e.value[0])
                      }
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
            </Card.Body>
          </Card.Root>

          {/* Output filters */}
          <Card.Root mb={4}>
            <Card.Body>
              <Heading size="sm" mb={3}>
                Output Filters
              </Heading>
              <Flex align="center" gap={2} mb={2}>
                <Checkbox.Root
                  checked={secretEnabled}
                  onCheckedChange={(e) =>
                    setSecretEnabled(!!e.checked)
                  }
                >
                  <Checkbox.HiddenInput />
                  <Checkbox.Control />
                  <Checkbox.Label>Secret Leak Detector</Checkbox.Label>
                </Checkbox.Root>
              </Flex>
              {secretEnabled && (
                <Box pl={6}>
                  <Flex gap={2} wrap="wrap" mb={2}>
                    {secrets.map((s) => (
                      <Badge
                        key={s}
                        size="sm"
                        cursor="pointer"
                        onClick={() =>
                          setSecrets((prev) =>
                            prev.filter((x) => x !== s)
                          )
                        }
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
                      onKeyDown={(e) =>
                        e.key === "Enter" && addSecret()
                      }
                    />
                    <Button size="sm" onClick={addSecret}>
                      Add
                    </Button>
                  </Flex>
                </Box>
              )}
            </Card.Body>
          </Card.Root>
        </Box>

        {/* Right: Attack set selector + run button */}
        <Box w={{ base: "full", lg: "400px" }}>
          <Card.Root mb={4}>
            <Card.Body>
              <Heading size="sm" mb={3}>
                Attack Set
              </Heading>

              {/* Technique checkboxes */}
              <Text fontSize="sm" mb={2} fontWeight="medium">
                Techniques
              </Text>
              <Flex gap={2} wrap="wrap" mb={4}>
                {ALL_TECHNIQUES.map((t) => {
                  const info = TECHNIQUE_INFO[t];
                  const isChecked = selectedTechniques.includes(t);
                  const count = taxonomy?.techniques.find(
                    (x) => x.id === t
                  )?.example_count;
                  return (
                    <Badge
                      key={t}
                      size="sm"
                      cursor="pointer"
                      colorPalette={isChecked ? "blue" : "gray"}
                      variant={isChecked ? "solid" : "outline"}
                      onClick={() => handleTechniqueToggle(t)}
                    >
                      {info?.name ?? t}
                      {count != null && ` (${count.toLocaleString()})`}
                    </Badge>
                  );
                })}
              </Flex>
              <Flex gap={2} mb={4}>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setSelectedTechniques(ALL_TECHNIQUES)}
                >
                  Select all
                </Button>
                <Button
                  size="xs"
                  variant="ghost"
                  onClick={() => setSelectedTechniques([])}
                >
                  Clear
                </Button>
              </Flex>

              <Separator mb={4} />

              {/* Difficulty range */}
              <Text fontSize="sm" mb={1} fontWeight="medium">
                Difficulty range: {difficultyRange[0]} – {difficultyRange[1]}
              </Text>
              <Slider.Root
                min={1}
                max={5}
                step={1}
                value={difficultyRange}
                onValueChange={(e) =>
                  setDifficultyRange(e.value as [number, number])
                }
                size="sm"
                mb={4}
              >
                <Slider.Control>
                  <Slider.Track>
                    <Slider.Range />
                  </Slider.Track>
                  <Slider.Thumb index={0} />
                  <Slider.Thumb index={1} />
                </Slider.Control>
              </Slider.Root>

              <Separator mb={4} />

              {/* Prompt count */}
              <Flex align="center" gap={2} mb={4}>
                <Text fontSize="sm" fontWeight="medium">
                  Prompt count:
                </Text>
                <Input
                  type="number"
                  size="sm"
                  w="80px"
                  min={1}
                  max={200}
                  value={promptCount}
                  onChange={(e) =>
                    setPromptCount(
                      Math.min(200, Math.max(1, parseInt(e.target.value) || 1))
                    )
                  }
                />
              </Flex>

              {/* Benign toggle */}
              <Box mb={4}>
                <Checkbox.Root
                  checked={includeBenign}
                  onCheckedChange={(e) =>
                    setIncludeBenign(!!e.checked)
                  }
                >
                  <Checkbox.HiddenInput />
                  <Checkbox.Control />
                  <Checkbox.Label>
                    Include benign prompts (for false positive rate)
                  </Checkbox.Label>
                </Checkbox.Root>
                {includeBenign && (
                  <Box pl={6} mt={2}>
                    <Text fontSize="sm">
                      Benign ratio: {(benignRatio * 100).toFixed(0)}%
                    </Text>
                    <Slider.Root
                      min={0.2}
                      max={0.5}
                      step={0.05}
                      value={[benignRatio]}
                      onValueChange={(e) => setBenignRatio(e.value[0])}
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

              <Separator mb={4} />

              {/* Cost estimate */}
              <Text fontSize="xs" color="fg.muted" mb={3}>
                Est. cost: ~${(promptCount * 0.001).toFixed(3)} (
                {promptCount} prompts × ~$0.001/prompt)
              </Text>

              {/* Run button */}
              <Button
                w="full"
                colorPalette="blue"
                size="lg"
                disabled={!canSubmit || isSubmitting}
                loading={isSubmitting}
                onClick={handleSubmit}
              >
                {isSubmitting ? "Starting..." : "Run Test"}
              </Button>

              {error && (
                <Text color="red.500" fontSize="sm" mt={2}>
                  {error}
                </Text>
              )}
            </Card.Body>
          </Card.Root>
        </Box>
      </Flex>
    </Box>
  );
}
