from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType


LANGUAGE_NAMES = MappingProxyType({
    "ar": "Arabic",
    "da": "Danish",
    "de": "German",
    "el": "Greek",
    "en": "English",
    "es": "Spanish",
    "fi": "Finnish",
    "fr": "French",
    "he": "Hebrew",
    "hi": "Hindi",
    "it": "Italian",
    "ja": "Japanese",
    "ko": "Korean",
    "ms": "Malay",
    "nl": "Dutch",
    "no": "Norwegian",
    "pl": "Polish",
    "pt": "Portuguese",
    "ru": "Russian",
    "sv": "Swedish",
    "sw": "Swahili",
    "tr": "Turkish",
    "zh": "Chinese",
})

MULTILINGUAL_LANGUAGE_CODES = tuple(LANGUAGE_NAMES)

GENERATION_CONTROL_NAMES = (
    "exaggeration",
    "cfg_weight",
    "temperature",
    "repetition_penalty",
    "min_p",
    "top_p",
    "top_k",
)

GENERATION_CONTROL_LABELS = MappingProxyType({
    "exaggeration": "Emotion intensity",
    "cfg_weight": "Guidance strength",
    "temperature": "Delivery variation",
    "repetition_penalty": "Repetition control",
    "min_p": "Rare-choice cutoff",
    "top_p": "Likely-choice range",
    "top_k": "Choice limit",
})

EXPRESSIVE_CONTROLS = frozenset({
    "exaggeration",
    "cfg_weight",
    "temperature",
    "repetition_penalty",
    "min_p",
    "top_p",
})

TURBO_CONTROLS = frozenset({
    "temperature",
    "repetition_penalty",
    "top_p",
    "top_k",
})

PARALINGUISTIC_EVENT_TAGS = (
    "[clear throat]",
    "[sigh]",
    "[shush]",
    "[cough]",
    "[groan]",
    "[sniff]",
    "[gasp]",
    "[chuckle]",
    "[laugh]",
)


class CapabilityValidationError(ValueError):
    """Raised when settings conflict with a model's capabilities."""


@dataclass(frozen=True)
class ModelCapabilities:
    model_id: str
    display_name: str
    description: str
    parameter_count_millions: int
    languages: tuple[str, ...]
    generation_controls: frozenset[str]
    event_tags: tuple[str, ...]
    devices: tuple[str, ...]
    native_sample_rates: tuple[int, ...]
    supports_voice_cloning: bool
    recommended_device: str
    requirements: tuple[str, ...]
    limitations: tuple[str, ...]

    def supports_language(self, language):
        return str(language).strip().lower() in self.languages

    def supports_control(self, control_name):
        return control_name in self.generation_controls

    def supports_device(self, device):
        return str(device).strip().lower() in self.devices

    @property
    def supports_event_tags(self):
        return bool(self.event_tags)

    @property
    def supports_emotion_intensity(self):
        return self.supports_control("exaggeration")


_MODEL_CAPABILITIES = {
    "original": ModelCapabilities(
        model_id="original",
        display_name="Original (current)",
        description=(
            "The existing expressive English Chatterbox model with CFG and "
            "exaggeration controls."
        ),
        parameter_count_millions=500,
        languages=("en",),
        generation_controls=EXPRESSIVE_CONTROLS,
        event_tags=(),
        devices=("cpu", "cuda", "mps"),
        native_sample_rates=(24000,),
        supports_voice_cloning=True,
        recommended_device="cuda",
        requirements=(
            "English text",
            "A clean WAV reference is recommended for voice cloning",
        ),
        limitations=(
            "English only",
            "No native paralinguistic event tags",
        ),
    ),
    "turbo": ModelCapabilities(
        model_id="turbo",
        display_name="Turbo",
        description=(
            "A lower-compute 350M English model with native speech-event "
            "tags and a single-step decoder."
        ),
        parameter_count_millions=350,
        languages=("en",),
        generation_controls=TURBO_CONTROLS,
        event_tags=PARALINGUISTIC_EVENT_TAGS,
        devices=("cpu", "cuda", "mps"),
        native_sample_rates=(24000,),
        supports_voice_cloning=True,
        recommended_device="cuda",
        requirements=(
            "English text",
            "Voice-reference audio must be longer than 5 seconds",
        ),
        limitations=(
            "English only",
            "Guidance strength, emotion intensity, and rare-choice cutoff "
            "are not supported",
        ),
    ),
    "v3": ModelCapabilities(
        model_id="v3",
        display_name="Multilingual V3",
        description=(
            "The 500M general-purpose multilingual model with improved "
            "speaker similarity and reduced hallucination."
        ),
        parameter_count_millions=500,
        languages=MULTILINGUAL_LANGUAGE_CODES,
        generation_controls=EXPRESSIVE_CONTROLS,
        event_tags=(),
        devices=("cpu", "cuda", "mps"),
        native_sample_rates=(24000,),
        supports_voice_cloning=True,
        recommended_device="cuda",
        requirements=(
            "The configured language must match the script",
            "A matching-language voice reference gives the best accent",
        ),
        limitations=(
            "No native Turbo/Nano paralinguistic event tags",
            "CUDA is recommended for practical generation speed",
        ),
    ),
    "nano": ModelCapabilities(
        model_id="nano",
        display_name="Nano",
        description=(
            "The smallest 110M English Chatterbox model, designed for "
            "low-memory and CPU-oriented use."
        ),
        parameter_count_millions=110,
        languages=("en",),
        generation_controls=TURBO_CONTROLS,
        event_tags=PARALINGUISTIC_EVENT_TAGS,
        devices=("cpu", "cuda", "mps"),
        native_sample_rates=(24000,),
        supports_voice_cloning=True,
        recommended_device="cpu",
        requirements=(
            "English text",
            "Voice-reference audio must be longer than 5 seconds",
        ),
        limitations=(
            "English only",
            "Guidance strength, emotion intensity, and rare-choice cutoff "
            "are not supported",
        ),
    ),
}

MODEL_CAPABILITIES = MappingProxyType(_MODEL_CAPABILITIES)
MODEL_ADAPTER_NAMES = tuple(MODEL_CAPABILITIES)

MODEL_DOWNLOAD_FILES = MappingProxyType({
    "original": (
        "ResembleAI/chatterbox",
        (
            "ve.safetensors",
            "t3_cfg.safetensors",
            "s3gen.safetensors",
            "tokenizer.json",
            "conds.pt",
        ),
    ),
    "v3": (
        "ResembleAI/chatterbox",
        (
            "ve.pt",
            "t3_mtl23ls_v3.safetensors",
            "s3gen.pt",
            "grapheme_mtl_merged_expanded_v1.json",
            "conds.pt",
            "Cangjie5_TC.json",
        ),
    ),
    "turbo": (
        "ResembleAI/chatterbox-turbo",
        (
            "ve.safetensors",
            "t3_turbo_v1.safetensors",
            "s3gen_meanflow.safetensors",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
        ),
    ),
    "nano": (
        "ResembleAI/chatterbox-nano",
        (
            "ve.safetensors",
            "t3_nano_v1.safetensors",
            "s3gen_meanflow.safetensors",
            "tokenizer_config.json",
            "vocab.json",
            "merges.txt",
        ),
    ),
})
MODEL_DISPLAY_NAMES = MappingProxyType({
    model_id: capabilities.display_name
    for model_id, capabilities in MODEL_CAPABILITIES.items()
})
MODEL_IDS_BY_DISPLAY_NAME = MappingProxyType({
    display_name: model_id
    for model_id, display_name in MODEL_DISPLAY_NAMES.items()
})
ENGLISH_ONLY_MODEL_ADAPTERS = frozenset({
    model_id
    for model_id, capabilities in MODEL_CAPABILITIES.items()
    if capabilities.languages == ("en",)
})


def get_model_capabilities(model_id):
    normalized_id = str(model_id).strip().lower()

    try:
        return MODEL_CAPABILITIES[normalized_id]
    except KeyError as error:
        choices = ", ".join(MODEL_ADAPTER_NAMES)
        raise CapabilityValidationError(
            f"Unknown TTS model '{normalized_id}'. Choose: {choices}"
        ) from error


def model_is_installed(model_id, hub_cache):
    """Return whether one complete compatible snapshot is locally cached."""
    normalized_id = str(model_id).strip().lower()
    get_model_capabilities(normalized_id)
    repository, required_files = MODEL_DOWNLOAD_FILES[normalized_id]
    repository_folder = "models--" + repository.replace("/", "--")
    snapshots = Path(hub_cache) / repository_folder / "snapshots"

    if not snapshots.is_dir():
        return False

    return any(
        snapshot.is_dir()
        and all((snapshot / filename).is_file() for filename in required_files)
        for snapshot in snapshots.iterdir()
    )


def model_id_from_display_name(display_name):
    value = str(display_name).strip()

    if value in MODEL_IDS_BY_DISPLAY_NAME:
        return MODEL_IDS_BY_DISPLAY_NAME[value]

    normalized_value = value.lower()
    get_model_capabilities(normalized_value)
    return normalized_value


def validate_model_configuration(model_id, language, device=None):
    capabilities = get_model_capabilities(model_id)
    normalized_language = str(language).strip().lower()

    if not capabilities.supports_language(normalized_language):
        supported = ", ".join(capabilities.languages)
        raise CapabilityValidationError(
            f"{capabilities.display_name} does not support language "
            f"'{normalized_language}'. Supported language codes: {supported}"
        )

    if device is not None and not capabilities.supports_device(device):
        supported = ", ".join(capabilities.devices)
        raise CapabilityValidationError(
            f"{capabilities.display_name} does not support device "
            f"'{device}'. Supported devices: {supported}"
        )

    return capabilities


def supported_generation_options(model_id, options):
    capabilities = get_model_capabilities(model_id)

    return {
        control_name: getattr(options, control_name)
        for control_name in GENERATION_CONTROL_NAMES
        if capabilities.supports_control(control_name)
    }


def format_model_capabilities(model_id, multiline=False):
    capabilities = get_model_capabilities(model_id)
    language_text = (
        "English (en)"
        if capabilities.languages == ("en",)
        else f"{len(capabilities.languages)} languages"
    )
    controls = ", ".join(
        GENERATION_CONTROL_LABELS[control_name]
        for control_name in GENERATION_CONTROL_NAMES
        if capabilities.supports_control(control_name)
    )
    tags = (
        ", ".join(capabilities.event_tags)
        if capabilities.event_tags
        else "none"
    )
    device_text = ", ".join(
        device.upper()
        for device in capabilities.devices
    )

    if not multiline:
        return (
            f"{capabilities.parameter_count_millions}M · {language_text} · "
            f"Devices: {device_text} · Controls: {controls} · "
            f"Event tags: {tags}"
        )

    requirements = "; ".join(capabilities.requirements)
    limitations = "; ".join(capabilities.limitations)

    return "\n".join((
        f"{capabilities.display_name} "
        f"({capabilities.parameter_count_millions}M)",
        capabilities.description,
        f"Languages: {language_text}",
        f"Devices: {device_text}; recommended: "
        f"{capabilities.recommended_device.upper()}",
        f"Native sample rate: "
        f"{', '.join(str(rate) for rate in capabilities.native_sample_rates)} Hz",
        f"Voice cloning: "
        f"{'yes' if capabilities.supports_voice_cloning else 'no'}",
        f"Generation controls: {controls}",
        f"Event tags: {tags}",
        f"Requirements: {requirements}",
        f"Limitations: {limitations}",
    ))
