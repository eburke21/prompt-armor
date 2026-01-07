/**
 * Technique metadata — descriptions and display names for the taxonomy UI.
 * Mirrors backend/promptarmor/ingestion/constants.py.
 */

export const TECHNIQUE_INFO: Record<
  string,
  { name: string; description: string; longDescription: string }
> = {
  instruction_override: {
    name: "Instruction Override",
    description: "Direct attempts to override system instructions",
    longDescription:
      "The most straightforward injection technique: the attacker explicitly asks the LLM to ignore, disregard, or override its system prompt. Despite being obvious, this technique still works against many models because the instruction to 'ignore previous instructions' competes directly with the system prompt in the model's attention mechanism.",
  },
  roleplay_exploit: {
    name: "Roleplay Exploit",
    description: "Persona or character hijacking to bypass safety",
    longDescription:
      "The attacker asks the LLM to adopt an alternate persona (like 'DAN' — Do Anything Now) that doesn't have safety restrictions. This works because roleplay is a legitimate LLM use case, making it hard for filters to distinguish malicious persona requests from benign creative writing prompts.",
  },
  encoding_trick: {
    name: "Encoding Trick",
    description: "Base64, ROT13, or other encoding obfuscation",
    longDescription:
      "The attacker encodes their malicious instructions in Base64, ROT13, pig latin, or other transformations. The LLM can often decode these internally, bypassing keyword-based input filters that only check plain text. This exploits the gap between what filters see and what the model understands.",
  },
  context_manipulation: {
    name: "Context Manipulation",
    description: "Fake system messages or delimiter injection",
    longDescription:
      "The attacker injects fake system-level markers (like '---SYSTEM---' or '[INST]') into their prompt to trick the model into treating the injected text as privileged instructions. This exploits the model's training on instruction-following formats where certain delimiters signal authority.",
  },
  indirect_injection: {
    name: "Indirect Injection",
    description: "Payload hidden in external content for the LLM to process",
    longDescription:
      "Instead of putting the injection directly in the prompt, the attacker hides it in content the LLM is asked to process — like a document to summarize, a webpage to analyze, or a code comment. This is especially dangerous in agentic and RAG (Retrieval-Augmented Generation) architectures.",
  },
  few_shot_poisoning: {
    name: "Few-Shot Poisoning",
    description: "Malicious examples embedded in the prompt",
    longDescription:
      "The attacker provides carefully crafted 'examples' that guide the model toward producing unsafe output. By framing malicious content as example responses, the attacker exploits the model's in-context learning to establish a pattern of compliance with harmful requests.",
  },
  output_format_exploit: {
    name: "Output Format Exploit",
    description: "Forcing structured output that bypasses content filters",
    longDescription:
      "The attacker requests the model output in a specific format (JSON, CSV, encoded text) that embeds restricted content in a way that output filters might not detect. For example, asking for a JSON object where one field contains the leaked secret.",
  },
  multi_turn_escalation: {
    name: "Multi-Turn Escalation",
    description: "Gradual boundary-pushing across multiple turns",
    longDescription:
      "Rather than attacking in a single prompt, the attacker gradually shifts the conversation context over multiple turns, slowly moving the model's behavior outside its safety boundaries. Each individual turn seems benign, but the cumulative effect achieves the injection goal.",
  },
  language_switch: {
    name: "Language Switch",
    description: "Switching to another language to evade English-focused filters",
    longDescription:
      "The attacker writes their injection in a non-English language, exploiting the fact that many content filters and keyword blocklists are English-only. The model may still understand and comply with instructions in other languages while the filters fail to detect them.",
  },
  payload_splitting: {
    name: "Payload Splitting",
    description: "Splitting malicious content across multiple parts",
    longDescription:
      "The attacker splits their malicious instruction across multiple parts of the prompt — the beginning, middle, and end — so that no single part triggers keyword filters. The model reassembles the full instruction during processing, while filters that check each chunk independently miss it.",
  },
  unclassified: {
    name: "Unclassified",
    description: "Injection attempts not matching known patterns",
    longDescription:
      "These prompts were identified as injection attempts but don't clearly match any of the 10 established technique categories. They may represent novel techniques, creative approaches, or ambiguous prompts where the classification heuristic lacks confidence.",
  },
};

/** Color for block rate values */
export function blockRateColor(rate: number): string {
  if (rate >= 0.8) return "green";
  if (rate >= 0.5) return "orange";
  return "red";
}

/** Difficulty level labels */
export const DIFFICULTY_LABELS: Record<number, string> = {
  1: "Very Easy",
  2: "Easy",
  3: "Medium",
  4: "Hard",
  5: "Very Hard",
};

/** Dataset display names */
export const DATASET_NAMES: Record<string, string> = {
  deepset: "deepset/prompt-injections",
  spml: "SPML Chatbot Prompt Injection",
  lakera_mosscap: "Lakera/Mosscap CTF",
  neuralchemy: "neuralchemy/Prompt-injection",
};
