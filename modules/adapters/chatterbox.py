from importlib import import_module
from importlib.metadata import PackageNotFoundError, version
import gc
import inspect
from numbers import Integral
import os
from pathlib import Path
import warnings

import torch

from modules.adapters.base import (
    AdapterNotLoadedError,
    GeneratedAudio,
    ModelCompatibilityError,
    ModelLoadError,
    SynthesisError,
    TTSAdapterError,
    TTSModelAdapter,
    VoicePreparationError,
)
from modules.adapters.registry import supported_generation_options
from modules.app_settings import CredentialStore, CredentialStoreError
from modules.model_inventory import inspect_model_inventory


# Chatterbox 0.1.7 uses this deprecated Diffusers class internally. PEFT does
# not replace that call, so suppress only the known third-party warning.
warnings.filterwarnings(
    "ignore",
    message=r".*LoRACompatibleLinear.*",
    category=FutureWarning,
    module=r"diffusers\.models\.lora",
)


def _installed_chatterbox_version():
    try:
        return version("chatterbox-tts")
    except PackageNotFoundError:
        return "not installed"


class _ChatterboxAdapter(TTSModelAdapter):
    model_module = ""
    model_class_name = ""
    model_class = None
    load_options = {}

    def __init__(self, device, cache_dir=None):
        super().__init__(device, cache_dir=cache_dir)
        self._prepared_voice = None
        self._prepared_exaggeration = None

    def _get_model_class(self):
        if self.model_class is not None:
            return self.model_class

        try:
            module = import_module(self.model_module)
            return getattr(module, self.model_class_name)
        except Exception as error:
            raise ModelLoadError(
                f"Could not import {self.display_name}. "
                "Install a compatible chatterbox-tts package."
            ) from error

    def _compatibility_message(self):
        options = ", ".join(
            f"{name}={value!r}"
            for name, value in self.load_options.items()
        )
        installed = _installed_chatterbox_version()

        return (
            f"{self.display_name} is unavailable in the installed "
            f"chatterbox-tts package ({installed}). Its model loader must "
            f"support {options}. Upgrade chatterbox-tts to a release that "
            "provides this model, or select another adapter."
        )

    def _validate_load_options(self, loader):
        if not self.load_options:
            return

        try:
            parameters = inspect.signature(loader).parameters
        except (TypeError, ValueError):
            return

        accepts_keywords = any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD
            for parameter in parameters.values()
        )
        missing = [
            name
            for name in self.load_options
            if name not in parameters and not accepts_keywords
        ]

        if missing:
            raise ModelCompatibilityError(
                self._compatibility_message()
            )

    def _local_snapshot(self, cache_dir):
        """Return a complete local snapshot when the model is installed."""

        if cache_dir is None:
            return None

        inventory = inspect_model_inventory(self.model_id, cache_dir)

        if inventory.installed and inventory.snapshot is not None:
            return inventory.snapshot

        return None

    def load(self):
        if self.loaded:
            return self

        local_snapshot = None

        if self.cache_dir is not None:
            cache_dir = Path(self.cache_dir).expanduser().resolve()
            cache_dir.mkdir(parents=True, exist_ok=True)
            os.environ["HF_HUB_CACHE"] = str(cache_dir)
            local_snapshot = self._local_snapshot(cache_dir)

        model_class = self._get_model_class()
        local_loader = getattr(model_class, "from_local", None)
        use_local = local_snapshot is not None and callable(local_loader)
        loader = local_loader if use_local else model_class.from_pretrained
        self._validate_load_options(loader)
        credential_token = None

        if not os.environ.get("HF_TOKEN"):
            try:
                credential_token = CredentialStore().token()
            except CredentialStoreError:
                credential_token = None

        if credential_token:
            os.environ["HF_TOKEN"] = credential_token

        try:
            if use_local:
                model = loader(
                    local_snapshot,
                    device=self.device,
                    **self.load_options,
                )
            else:
                model = loader(
                    device=self.device,
                    **self.load_options,
                )
        except TypeError as error:
            if self.load_options:
                raise ModelCompatibilityError(
                    self._compatibility_message()
                ) from error

            raise ModelLoadError(
                f"Could not load {self.display_name}"
            ) from error
        except Exception as error:
            raise ModelLoadError(
                f"Could not load {self.display_name}"
            ) from error
        finally:
            if credential_token:
                os.environ.pop("HF_TOKEN", None)

        sample_rate = getattr(model, "sr", 24000)

        if (
            isinstance(sample_rate, bool)
            or not isinstance(sample_rate, Integral)
            or sample_rate <= 0
        ):
            raise ModelLoadError(
                f"{self.display_name} returned an invalid sample rate: "
                f"{sample_rate!r}"
            )

        self._model = model
        self._sample_rate = int(sample_rate)

        return self

    def _conditioning_exaggeration(self, exaggeration):
        return float(exaggeration)

    def prepare_voice(self, voice_file, exaggeration=0.5):
        if not self.loaded:
            raise AdapterNotLoadedError(
                f"Load {self.display_name} before preparing a voice"
            )

        voice_file = Path(voice_file)

        if not voice_file.is_file():
            raise VoicePreparationError(
                f"Voice reference not found: {voice_file}"
            )

        conditioning_exaggeration = self._conditioning_exaggeration(
            exaggeration
        )
        cache_key = (
            str(voice_file.resolve()),
            conditioning_exaggeration,
        )

        if cache_key == self._prepared_voice:
            return

        try:
            with torch.inference_mode():
                self._model.prepare_conditionals(
                    str(voice_file),
                    exaggeration=conditioning_exaggeration,
                )
        except Exception as error:
            raise VoicePreparationError(
                f"Could not prepare voice reference for "
                f"{self.display_name}: {voice_file}"
            ) from error

        self._prepared_voice = cache_key
        self._prepared_exaggeration = conditioning_exaggeration

    def _generation_kwargs(self, text, options):
        raise NotImplementedError

    @staticmethod
    def _standardize_waveform(waveform):
        try:
            if not isinstance(waveform, torch.Tensor):
                waveform = torch.as_tensor(waveform)

            while waveform.dim() > 2 and waveform.shape[0] == 1:
                waveform = waveform.squeeze(0)

            if waveform.dim() == 1:
                waveform = waveform.unsqueeze(0)

            if waveform.dim() != 2:
                raise ValueError(
                    "expected one-dimensional or channel-first audio"
                )

            if waveform.numel() == 0:
                raise ValueError("received an empty waveform")

            return waveform.detach().to(
                device="cpu",
                dtype=torch.float32,
            ).contiguous()
        except Exception as error:
            raise SynthesisError(
                f"Could not standardize generated audio: {error}"
            ) from error

    def generate(self, text, options):
        if not self.loaded:
            raise AdapterNotLoadedError(
                f"Load {self.display_name} before generating speech"
            )

        if self._prepared_voice is None:
            raise VoicePreparationError(
                f"Prepare a voice for {self.display_name} before generation"
            )

        if not isinstance(text, str) or not text.strip():
            raise SynthesisError("Text to synthesize cannot be empty")

        try:
            with torch.inference_mode():
                waveform = self._model.generate(
                    **self._generation_kwargs(text, options)
                )

            waveform = self._standardize_waveform(waveform)
        except TTSAdapterError:
            raise
        except Exception as error:
            raise SynthesisError(
                f"{self.display_name} generation failed"
            ) from error

        return GeneratedAudio(
            waveform=waveform,
            sample_rate=self.sample_rate,
        )

    def unload(self):
        self._model = None
        self._sample_rate = None
        self._prepared_voice = None
        self._prepared_exaggeration = None

        gc.collect()

        if torch.cuda.is_available():
            torch.cuda.empty_cache()


class ChatterboxOriginalAdapter(_ChatterboxAdapter):
    model_id = "original"
    display_name = "Chatterbox Original"
    model_module = "chatterbox.tts"
    model_class_name = "ChatterboxTTS"

    def _generation_kwargs(self, text, options):
        return {
            "text": text,
            **supported_generation_options(self.model_id, options),
        }


class ChatterboxV3Adapter(_ChatterboxAdapter):
    model_id = "v3"
    display_name = "Chatterbox Multilingual V3"
    model_module = "chatterbox.mtl_tts"
    model_class_name = "ChatterboxMultilingualTTS"
    load_options = {"t3_model": "v3"}

    def _generation_kwargs(self, text, options):
        return {
            "text": text,
            "language_id": options.language.lower(),
            **supported_generation_options(self.model_id, options),
        }


class ChatterboxTurboAdapter(_ChatterboxAdapter):
    model_id = "turbo"
    display_name = "Chatterbox Turbo"
    model_module = "chatterbox.tts_turbo"
    model_class_name = "ChatterboxTurboTTS"

    def _conditioning_exaggeration(self, exaggeration):
        return 0.0

    def _generation_kwargs(self, text, options):
        return {
            "text": text,
            **supported_generation_options(self.model_id, options),
        }


class ChatterboxNanoAdapter(ChatterboxTurboAdapter):
    model_id = "nano"
    display_name = "Chatterbox Nano"
    load_options = {"nano": True}
