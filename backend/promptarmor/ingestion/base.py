"""Abstract base class for dataset ingestors."""

import abc
import hashlib
import uuid

from promptarmor.models.attacks import AttackPrompt, SystemPrompt


def make_id(text: str, source: str) -> str:
    """Deterministic UUID from prompt text + source to enable deduplication."""
    hash_input = f"{source}:{text}".encode()
    return str(uuid.UUID(hashlib.sha256(hash_input).hexdigest()[:32]))


class DatasetIngestor(abc.ABC):
    """Base class for HF dataset ingestors.

    Each subclass handles one dataset: download, normalize into AttackPrompt objects.
    The pipeline orchestrator handles deduplication and DB writes.
    """

    @property
    @abc.abstractmethod
    def source_name(self) -> str:
        """Short identifier for this dataset (e.g. 'deepset')."""

    @abc.abstractmethod
    def download(self, sample: int | None = None) -> None:
        """Download the dataset from Hugging Face. Optionally limit to `sample` rows."""

    @abc.abstractmethod
    def normalize(self) -> list[AttackPrompt]:
        """Convert raw dataset rows into normalized AttackPrompt objects."""

    def get_system_prompts(self) -> list[SystemPrompt]:
        """Return system prompts extracted from this dataset. Override if applicable."""
        return []
