"""Ingestor for reshabhs/SPML_Chatbot_Prompt_Injection dataset.

Unique: contains system prompts paired with user injection attempts.
"""

import hashlib
import re
import uuid

import pandas as pd
from huggingface_hub import hf_hub_download

from promptarmor.ingestion.base import DatasetIngestor, make_id
from promptarmor.models.attacks import AttackPrompt, SystemPrompt

# Keywords for categorizing system prompts
_CATEGORY_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("customer_support", re.compile(r"customer|support|help desk|service", re.I)),
    ("healthcare", re.compile(r"health|medical|doctor|patient|symptom", re.I)),
    ("finance", re.compile(r"financ|banking|invest|money|budget", re.I)),
    ("education", re.compile(r"tutor|teach|learn|education|student", re.I)),
    ("code_assistant", re.compile(r"code|program|develop|software|debug", re.I)),
    ("legal", re.compile(r"legal|law|attorney|contract", re.I)),
    ("general", re.compile(r"assistant|helpful|chatbot", re.I)),
]


def _categorize_system_prompt(text: str) -> str:
    for category, pattern in _CATEGORY_PATTERNS:
        if pattern.search(text):
            return category
    return "general"


class SpmlIngestor(DatasetIngestor):
    source_name = "spml"

    def __init__(self) -> None:
        self._df: pd.DataFrame = pd.DataFrame()

    def download(self, sample: int | None = None) -> None:
        path = hf_hub_download(
            "reshabhs/SPML_Chatbot_Prompt_Injection",
            "spml_prompt_injection.csv",
            repo_type="dataset",
        )
        self._df = pd.read_csv(path)
        if sample is not None:
            self._df = self._df.head(sample)

    def normalize(self) -> list[AttackPrompt]:
        prompts = []
        for _, row in self._df.iterrows():
            text = str(row.get("User Prompt", "")).strip()
            if not text:
                continue
            degree = int(row.get("Degree", 0))
            is_injection = degree > 0
            prompts.append(
                AttackPrompt(
                    id=make_id(text, self.source_name),
                    source_dataset=self.source_name,
                    original_label=str(degree),
                    is_injection=is_injection,
                    prompt_text=text,
                    language="en",
                    character_count=len(text),
                )
            )
        return prompts

    def get_system_prompts(self) -> list[SystemPrompt]:
        seen: set[str] = set()
        system_prompts: list[SystemPrompt] = []
        for _, row in self._df.iterrows():
            text = str(row.get("System Prompt", "")).strip()
            if not text:
                continue
            text_hash = hashlib.sha256(text.encode()).hexdigest()[:32]
            if text_hash in seen:
                continue
            seen.add(text_hash)
            system_prompts.append(
                SystemPrompt(
                    id=str(uuid.UUID(text_hash)),
                    source="spml_dataset",
                    name=None,
                    prompt_text=text,
                    category=_categorize_system_prompt(text),
                )
            )
        return system_prompts
