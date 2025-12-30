"""Ingestor for deepset/prompt-injections dataset."""

import re

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from promptarmor.ingestion.base import DatasetIngestor, make_id
from promptarmor.models.attacks import AttackPrompt

# Simple heuristic: if text contains common German words/patterns, it's likely German
_GERMAN_PATTERNS = re.compile(
    r"\b(ich|und|der|die|das|ist|ein|eine|nicht|auf|mit|für|den|dem|dass|sind|von|haben)\b",
    re.IGNORECASE,
)


def _detect_language(text: str) -> str:
    german_matches = len(_GERMAN_PATTERNS.findall(text))
    return "de" if german_matches >= 3 else "en"


def _parquet_to_rows(path: str) -> list[dict[str, object]]:
    table = pq.read_table(path)
    cols = table.column_names
    arrays = [table.column(c).to_pylist() for c in cols]
    return [dict(zip(cols, vals, strict=False)) for vals in zip(*arrays, strict=False)]


class DeepsetIngestor(DatasetIngestor):
    source_name = "deepset"

    _TRAIN_FILE = "data/train-00000-of-00001-9564e8b05b4757ab.parquet"
    _TEST_FILE = "data/test-00000-of-00001-701d16158af87368.parquet"

    def __init__(self) -> None:
        self._rows: list[dict[str, object]] = []

    def download(self, sample: int | None = None) -> None:
        rows: list[dict[str, object]] = []
        for fname in [self._TRAIN_FILE, self._TEST_FILE]:
            path = hf_hub_download(
                "deepset/prompt-injections", fname, repo_type="dataset"
            )
            rows.extend(_parquet_to_rows(path))
        self._rows = rows[:sample] if sample is not None else rows

    def normalize(self) -> list[AttackPrompt]:
        prompts = []
        for row in self._rows:
            text = str(row["text"])
            label = int(row["label"])  # type: ignore[call-overload]
            prompts.append(
                AttackPrompt(
                    id=make_id(text, self.source_name),
                    source_dataset=self.source_name,
                    original_label=str(label),
                    is_injection=label == 1,
                    prompt_text=text,
                    language=_detect_language(text),
                    character_count=len(text),
                )
            )
        return prompts
