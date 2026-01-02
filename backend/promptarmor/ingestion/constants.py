"""Technique metadata — descriptions and display names."""

TECHNIQUE_METADATA: dict[str, dict[str, str]] = {
    "instruction_override": {
        "name": "Instruction Override",
        "description": (
            "Direct attempts to override or ignore the system prompt instructions. "
            "The most common and straightforward injection technique."
        ),
    },
    "roleplay_exploit": {
        "name": "Roleplay Exploit",
        "description": (
            "Persona or character hijacking — asking the model to assume a new identity "
            "that bypasses its safety guidelines (e.g., DAN, developer mode)."
        ),
    },
    "encoding_trick": {
        "name": "Encoding Trick",
        "description": (
            "Using encoded or obfuscated formats (base64, ROT13, pig latin, morse code) "
            "to hide malicious instructions from input filters."
        ),
    },
    "context_manipulation": {
        "name": "Context Manipulation",
        "description": (
            "Injecting fake system messages or delimiter tokens to make the model "
            "believe new instructions are coming from a trusted source."
        ),
    },
    "indirect_injection": {
        "name": "Indirect Injection",
        "description": (
            "Hiding malicious instructions inside content the model is asked to process "
            "(e.g., a document to summarize, an email to translate)."
        ),
    },
    "few_shot_poisoning": {
        "name": "Few-Shot Poisoning",
        "description": (
            "Providing carefully crafted examples that steer the model toward "
            "producing harmful or policy-violating outputs."
        ),
    },
    "output_format_exploit": {
        "name": "Output Format Exploit",
        "description": (
            "Forcing the model to output in a specific format (JSON, code) that "
            "bypasses output filters or embeds harmful content in structured fields."
        ),
    },
    "language_switch": {
        "name": "Language Switch",
        "description": (
            "Switching to a non-English language mid-conversation to evade "
            "filters that primarily analyze English text."
        ),
    },
    "payload_splitting": {
        "name": "Payload Splitting",
        "description": (
            "Splitting malicious content across multiple parts or turns so that "
            "no single fragment triggers safety filters."
        ),
    },
    "multi_turn_escalation": {
        "name": "Multi-Turn Escalation",
        "description": (
            "Gradually pushing boundaries across multiple conversational turns, "
            "building trust before introducing the malicious payload."
        ),
    },
    "unclassified": {
        "name": "Unclassified",
        "description": (
            "Injection prompts that did not match any known technique pattern. "
            "These may use novel or highly creative approaches."
        ),
    },
}

DATASET_METADATA: dict[str, dict[str, str]] = {
    "deepset": {
        "name": "deepset/prompt-injections",
        "license": "Apache-2.0",
    },
    "neuralchemy": {
        "name": "neuralchemy/Prompt-injection-dataset",
        "license": "Apache-2.0",
    },
    "spml": {
        "name": "reshabhs/SPML_Chatbot_Prompt_Injection",
        "license": "MIT",
    },
    "lakera_mosscap": {
        "name": "Lakera/mosscap_prompt_injection",
        "license": "MIT",
    },
}
