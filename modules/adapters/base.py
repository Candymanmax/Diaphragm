from abc import ABC, abstractmethod
from dataclasses import dataclass

import torch


class TTSAdapterError(RuntimeError):
    """Base error raised by all model adapters."""


class AdapterNotLoadedError(TTSAdapterError):
    """Raised when an operation needs a loaded model."""


class ModelLoadError(TTSAdapterError):
    """Raised when a model cannot be loaded."""


class ModelCompatibilityError(ModelLoadError):
    """Raised when the installed package cannot provide a selected model."""


class VoicePreparationError(TTSAdapterError):
    """Raised when voice conditioning cannot be prepared."""


class SynthesisError(TTSAdapterError):
    """Raised when speech generation or output conversion fails."""


@dataclass(frozen=True)
class GenerationOptions:
    """Model-independent controls for one synthesis request."""

    language: str = "en"
    exaggeration: float = 0.6
    cfg_weight: float = 0.4
    temperature: float = 0.8
    repetition_penalty: float = 1.2
    min_p: float = 0.05
    top_p: float = 1.0
    top_k: int = 1000


@dataclass(frozen=True)
class GeneratedAudio:
    """Standard audio returned by every adapter."""

    waveform: torch.Tensor
    sample_rate: int


class TTSModelAdapter(ABC):
    """Common lifecycle and synthesis interface for TTS backends."""

    model_id = "unknown"
    display_name = "Unknown TTS model"

    def __init__(self, device, cache_dir=None):
        self.device = str(device)
        self.cache_dir = cache_dir
        self._model = None
        self._sample_rate = None

    @property
    def loaded(self):
        return self._model is not None

    @property
    def capabilities(self):
        from modules.adapters.registry import get_model_capabilities

        return get_model_capabilities(self.model_id)

    @property
    def sample_rate(self):
        if self._sample_rate is None:
            raise AdapterNotLoadedError(
                f"{self.display_name} is not loaded"
            )

        return self._sample_rate

    @abstractmethod
    def load(self):
        """Load the backing model and return this adapter."""

    @abstractmethod
    def prepare_voice(self, voice_file, exaggeration=0.5):
        """Prepare and cache conditioning for a voice reference."""

    @abstractmethod
    def generate(self, text, options):
        """Generate standardized audio for one text section."""

    @abstractmethod
    def unload(self):
        """Release the model and any associated accelerator memory."""
