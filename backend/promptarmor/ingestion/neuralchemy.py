"""Ingestor for neuralchemy/Prompt-injection-dataset."""

import pyarrow.parquet as pq
from huggingface_hub import hf_hub_download

from promptarmor.ingestion.base import DatasetIngestor, make_id
from promptarmor.models.attacks import AttackPrompt


def _parquet_to_rows(path: str) -> list[dict[str, object]]:
    table = pq.read_table(path)
    cols = table.column_names
    arrays = [table.column(c).to_pylist() for c in cols]
    return [dict(zip(cols, vals, strict=False)) for vals in zip(*arrays, strict=False)]


class NeuralchemyIngestor(DatasetIngestor):
    source_name = "neuralchemy"

    _TRAIN_FILE = "data/train-00000-of-00001.parquet"

    def __init__(self) -> None:
        self._rows: list[dict[str, object]] = []

    def download(self, sample: int | None = None) -> None:
        path = hf_hub_download(
            "neuralchemy/Prompt-injection-dataset",
            self._TRAIN_FILE,
            repo_type="dataset",
        )
        self._rows = _parquet_to_rows(path)
        if sample is not None:
            self._rows = self._rows[:sample]

    def normalize(self) -> list[AttackPrompt]:
        prompts = []
        for row in self._rows:
            text = str(row.get("prompt", ""))
            if not text.strip():
                continue
            label = int(row.get("label", 0))  # type: ignore[call-overload]
            prompts.append(
                AttackPrompt(
                    id=make_id(text, self.source_name),
                    source_dataset=self.source_name,
                    original_label=str(label),
                    is_injection=label == 1,
                    prompt_text=text,
                    language="en",
                    character_count=len(text),
                )
            )
        return prompts
