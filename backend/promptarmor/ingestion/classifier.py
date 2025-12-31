"""Heuristic technique classifier and difficulty estimator.

Classifies injection prompts into the 10 technique categories from the spec
using regex/keyword patterns. A prompt can match multiple techniques.
"""

import logging
import re

from promptarmor.models.attacks import AttackPrompt, PromptTechnique

logger = logging.getLogger(__name__)

# Each entry: (technique_id, compiled regex, base confidence)
_TECHNIQUE_PATTERNS: list[tuple[str, re.Pattern[str], float]] = [
    (
        "instruction_override",
        re.compile(
            r"(ignore\s+(all\s+)?(previous|prior|above|earlier)|"
            r"disregard\s+(all\s+)?(previous|prior|your)|"
            r"forget\s+(all\s+)?(previous|prior|your|about)|"
            r"override\s+(previous|your|all)|"
            r"new\s+instructions?\s*:|"
            r"do\s+not\s+follow\s+(your|the)\s+(previous|original)|"
            r"stop\s+being\s+a|"
            r"from\s+now\s+on\b.*ignore)",
            re.IGNORECASE,
        ),
        0.9,
    ),
    (
        "roleplay_exploit",
        re.compile(
            r"(you\s+are\s+now\b|"
            r"pretend\s+(you\s+are|to\s+be)|"
            r"act\s+as\s+(if\s+you|a\b)|"
            r"role\s*play\s+as|"
            r"take\s+on\s+the\s+role|"
            r"\bDAN\b|"
            r"do\s+anything\s+now|"
            r"jailbreak|"
            r"you\s+have\s+been\s+freed|"
            r"enter\s+.{0,20}mode|"
            r"switch\s+to\s+.{0,20}mode|"
            r"developer\s+mode|"
            r"no\s+restrictions)",
            re.IGNORECASE,
        ),
        0.85,
    ),
    (
        "encoding_trick",
        re.compile(
            r"(base64|rot13|morse\s+code|pig\s+latin|"
            r"decode\s+this|encode\s+this|"
            r"binary\s+code|hex(adecimal)?|"
            r"caesar\s+cipher|"
            r"backwards?\s+(text|write|spell)|"
            r"reverse\s+(the\s+)?(text|letters|words)|"
            r"atbash|"
            r"[A-Za-z0-9+/]{20,}={0,2})",  # base64-like string
            re.IGNORECASE,
        ),
        0.8,
    ),
    (
        "context_manipulation",
        re.compile(
            r"(---\s*SYSTEM|"
            r"```\s*system|"
            r"END_SYSTEM|"
            r"\[SYSTEM\]|"
            r"<\|system\|>|"
            r"<system>|"
            r"<<SYS>>|"
            r"\[INST\]|"
            r"ADMIN\s*:|"
            r"DEVELOPER\s*:|"
            r"INSTRUCTIONS\s*:|"
            r"<\|im_start\|>|"
            r"Human\s*:|"
            r"Assistant\s*:)",
            re.IGNORECASE,
        ),
        0.85,
    ),
    (
        "indirect_injection",
        re.compile(
            r"(summarize\s+(this|the\s+following)\s+document|"
            r"the\s+following\s+text\s+(says|contains)|"
            r"read\s+this\s+(document|text|email)|"
            r"process\s+(this|the\s+following)|"
            r"here\s+is\s+(a\s+)?(document|text|email|message)|"
            r"translate\s+(this|the\s+following)\b.*\b(ignore|forget))",
            re.IGNORECASE,
        ),
        0.7,
    ),
    (
        "few_shot_poisoning",
        re.compile(
            r"(here\s+(is|are)\s+(an?\s+)?example|"
            r"for\s+example\s*:.*\b(ignore|forget|override)|"
            r"sample\s+response\s*:|"
            r"example\s+output\s*:|"
            r"Q\s*:.*\nA\s*:.*\b(ignore|secret|password)|"
            r"good\s+response\s*:)",
            re.IGNORECASE | re.DOTALL,
        ),
        0.75,
    ),
    (
        "output_format_exploit",
        re.compile(
            r"(respond\s+only\s+in\s+JSON|"
            r"output\s+(as|in)\s+(code|JSON|XML|markdown)|"
            r"format\s+your\s+(answer|response)\s+as|"
            r"write\s+(as|in)\s+JSON\s+where|"
            r"return\s+a\s+JSON|"
            r"wrap\s+your\s+(response|answer)\s+in)",
            re.IGNORECASE,
        ),
        0.7,
    ),
    (
        "language_switch",
        re.compile(
            r"(réponds?\s+en\s+français|"
            r"antworte\s+(auf\s+)?deutsch|"
            r"responde\s+en\s+español|"
            r"translate\s+to\s+\w+\s*:.*\b(ignore|forget)|"
            r"in\s+(french|german|spanish|chinese|japanese|korean|arabic)\s*:.*\b(ignore|forget))",
            re.IGNORECASE,
        ),
        0.75,
    ),
    (
        "payload_splitting",
        re.compile(
            r"(complete\s+this\s*(sentence|phrase|text)|"
            r"finish\s+(the\s+)?sentence|"
            r"what\s+comes\s+(after|next)|"
            r"continue\s+(from|where)|"
            r"the\s+(first|next)\s+part\s+is|"
            r"part\s+\d\s*of\s*\d|"
            r"combine\s+these\s+parts)",
            re.IGNORECASE,
        ),
        0.7,
    ),
    (
        "multi_turn_escalation",
        re.compile(
            r"(let'?s\s+start\s+with\s+a\s+simple|"
            r"now\s+that\s+we'?ve\s+established|"
            r"building\s+on\s+(our|the)\s+previous|"
            r"as\s+we\s+discussed\s+(earlier|before)|"
            r"remember\s+when\s+(you|we)\s+said|"
            r"going\s+back\s+to\s+what\s+you\s+said)",
            re.IGNORECASE,
        ),
        0.6,
    ),
]

# Broader CTF-style patterns for password extraction (Lakera Mosscap context)
_CTF_PASSWORD_PATTERNS = re.compile(
    r"(password|secret|passphrase|the\s+word|hidden\s+word|magic\s+word|"
    r"what\s+is\s+the\s+\w+\s+you.*protect|"
    r"tell\s+me\s+the|reveal\s+the|share\s+the|"
    r"spell\s+out|write\s+out|type\s+out|"
    r"give\s+me\s+a\s+hint|"
    r"what\s+are\s+you\s+hiding|"
    r"what\s+were\s+you\s+told|"
    r"first\s+letter|last\s+letter|each\s+letter|letter\s+by\s+letter|"
    r"rhyme\s+with|sounds\s+like|"
    r"what\s+word\s+is|"
    r"your\s+instructions|your\s+rules|your\s+guidelines|"
    r"story\s+about.*word|story\s+about.*letter|"
    r"game\s+where.*word|game\s+where.*letter|"
    r"word\s+association|guessing\s+game|"
    r"riddle|puzzle|clue|"
    r"acrostic|first\s+letters?\s+of\s+each)",
    re.IGNORECASE,
)

# Difficulty scoring by technique type
_TECHNIQUE_DIFFICULTY: dict[str, int] = {
    "instruction_override": 1,
    "roleplay_exploit": 2,
    "context_manipulation": 3,
    "encoding_trick": 3,
    "language_switch": 3,
    "few_shot_poisoning": 3,
    "output_format_exploit": 4,
    "indirect_injection": 4,
    "payload_splitting": 4,
    "multi_turn_escalation": 5,
}


def classify_techniques(
    prompt_text: str, source_dataset: str = "",
) -> list[PromptTechnique]:
    """Classify a single prompt text into technique categories."""
    techniques = []
    for technique_id, pattern, confidence in _TECHNIQUE_PATTERNS:
        if pattern.search(prompt_text):
            techniques.append(
                PromptTechnique(
                    technique=technique_id,
                    confidence=confidence,
                    classified_by="heuristic",
                )
            )

    # Secondary pass: CTF password extraction patterns
    # These are broader and used when primary patterns don't match
    if not techniques and _CTF_PASSWORD_PATTERNS.search(prompt_text):
        techniques.append(
            PromptTechnique(
                technique="instruction_override",
                confidence=0.6,
                classified_by="heuristic",
            )
        )

    # Source-aware fallback: Lakera Mosscap prompts are inherently
    # instruction_override attempts (the CTF goal is always "extract the password")
    if not techniques and source_dataset == "lakera_mosscap":
        techniques.append(
            PromptTechnique(
                technique="instruction_override",
                confidence=0.4,
                classified_by="heuristic_fallback",
            )
        )

    return techniques


def estimate_difficulty(
    prompt: AttackPrompt,
    techniques: list[PromptTechnique],
) -> int:
    """Estimate difficulty (1-5) based on techniques, length, and complexity.

    If the prompt already has a difficulty_estimate (e.g., from Lakera level mapping),
    use that. Otherwise, derive from technique types and count.
    """
    if prompt.difficulty_estimate is not None:
        return prompt.difficulty_estimate

    if not prompt.is_injection:
        return 1  # benign prompts don't have injection difficulty

    if not techniques:
        # Injection but no classified technique — assume moderate
        return 2

    # Base difficulty = max difficulty of matched techniques
    base = max(_TECHNIQUE_DIFFICULTY.get(t.technique, 2) for t in techniques)

    # Bonus for multiple techniques (combination attacks are harder)
    if len(techniques) >= 3:
        base = min(base + 2, 5)
    elif len(techniques) >= 2:
        base = min(base + 1, 5)

    # Bonus for long prompts (more sophisticated usually)
    if prompt.character_count > 500:
        base = min(base + 1, 5)

    return base


def classify_all(
    prompts: list[AttackPrompt],
) -> list[tuple[str, list[PromptTechnique]]]:
    """Classify all prompts and assign difficulty estimates.

    Returns list of (prompt_id, techniques) tuples.
    Also mutates prompt.difficulty_estimate in-place.
    """
    results: list[tuple[str, list[PromptTechnique]]] = []
    stats = {"classified": 0, "unclassified": 0, "benign_skipped": 0}

    for prompt in prompts:
        if not prompt.is_injection:
            # Benign prompts don't get technique tags
            prompt.difficulty_estimate = 1
            stats["benign_skipped"] += 1
            results.append((prompt.id, []))
            continue

        techniques = classify_techniques(prompt.prompt_text, prompt.source_dataset)

        if not techniques:
            # Injection but no heuristic match — tag as unclassified
            techniques = [
                PromptTechnique(
                    technique="unclassified",
                    confidence=0.5,
                    classified_by="heuristic",
                )
            ]
            stats["unclassified"] += 1
        else:
            stats["classified"] += 1

        prompt.difficulty_estimate = estimate_difficulty(prompt, techniques)
        results.append((prompt.id, techniques))

    total_injections = stats["classified"] + stats["unclassified"]
    if total_injections > 0:
        pct = stats["unclassified"] / total_injections * 100
        logger.info(
            "Classification: %d classified, %d unclassified (%.1f%%), %d benign skipped",
            stats["classified"],
            stats["unclassified"],
            pct,
            stats["benign_skipped"],
        )

    return results
