"""Ingestor for Lakera/mosscap_prompt_injection dataset.

This is the largest and noisiest dataset (~223K prompts from DEF CON 31's
Mosscap CTF). Many entries are casual questions, not actual injection attempts.
Requires noise filtering and heuristic injection labeling.
"""

import re

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from promptarmor.ingestion.base import DatasetIngestor, make_id
from promptarmor.models.attacks import AttackPrompt

# Level string → integer
_LEVEL_MAP = {f"Level {i}": i for i in range(1, 9)}

# Level → difficulty estimate
_LEVEL_TO_DIFFICULTY: dict[int, int] = {
    1: 1,
    2: 2,
    3: 3,
    4: 3,
    5: 3,
    6: 4,
    7: 4,
    8: 5,
}

# Heuristic: prompts that are just casual conversation, not injection attempts
_NOISE_PATTERNS = re.compile(
    r"^(hi|hello|hey|how are you|what is your name|who are you|tell me a joke|"
    r"what can you do|good morning|good evening|thanks|thank you|bye|goodbye|ok|okay)\b",
    re.IGNORECASE,
)

# Injection signal patterns in the prompt text itself
_INJECTION_SIGNALS = re.compile(
    r"(ignore|forget|disregard|override|bypass|reveal|password|secret|"
    r"previous instructions|system prompt|pretend|you are now|act as if|"
    r"jailbreak|DAN|new role|new instructions)",
    re.IGNORECASE,
)


def _parquet_to_rows(path: str) -> list[dict[str, object]]:
    table = pq.read_table(path)
    cols = table.column_names
    arrays = [table.column(c).to_pylist() for c in cols]
    return [dict(zip(cols, vals, strict=False)) for vals in zip(*arrays, strict=False)]


class LakeraIngestor(DatasetIngestor):
    source_name = "lakera_mosscap"

    _TRAIN_FILE = "data/train-00000-of-00001-07ae0ed17fa07cc1.parquet"

    def __init__(self) -> None:
        self._rows: list[dict[str, object]] = []

    def download(self, sample: int | None = None) -> None:
        path = hf_hub_download(
            "Lakera/mosscap_prompt_injection",
            self._TRAIN_FILE,
            repo_type="dataset",
        )
        self._rows = _parquet_to_rows(path)
        if sample is not None:
            self._rows = self._rows[:sample]

    def normalize(self) -> list[AttackPrompt]:
        prompts = []
        for row in self._rows:
            text = str(row.get("prompt", "")).strip()

            # Noise filter: skip very short or empty prompts
            if len(text) < 10:
                continue

            level_str = str(row.get("level", "Level 1"))
            level = _LEVEL_MAP.get(level_str, 1)
            difficulty = _LEVEL_TO_DIFFICULTY.get(level, 3)

            answer = str(row.get("answer", ""))

            # Heuristic injection labeling:
            # 1. If the prompt has injection signal words → injection
            # 2. If the answer reveals a password/secret → injection succeeded
            # 3. Casual/noise patterns → benign
            # 4. Otherwise → injection (CTF context: most prompts are attempts)
            has_injection_signals = bool(_INJECTION_SIGNALS.search(text))
            is_noise = bool(_NOISE_PATTERNS.match(text))
            answer_reveals = "password" in answer.lower() or "secret" in answer.lower()

            is_injection = not (is_noise and not has_injection_signals)

            original_label = "injection" if is_injection else "benign"
            if answer_reveals:
                original_label = "injection_succeeded"

            prompts.append(
                AttackPrompt(
                    id=make_id(text, self.source_name),
                    source_dataset=self.source_name,
                    original_label=original_label,
                    is_injection=is_injection,
                    prompt_text=text,
                    language="en",
                    difficulty_estimate=difficulty,
                    character_count=len(text),
                )
            )
        return prompts
