from modules.adapters.base import ModelCompatibilityError, TTSModelAdapter
from modules.adapters.chatterbox import (
    ChatterboxNanoAdapter,
    ChatterboxOriginalAdapter,
    ChatterboxTurboAdapter,
    ChatterboxV3Adapter,
)
from modules.adapters.registry import (
    CapabilityValidationError,
    validate_model_configuration,
)


ADAPTER_CLASSES = {
    "original": ChatterboxOriginalAdapter,
    "turbo": ChatterboxTurboAdapter,
    "v3": ChatterboxV3Adapter,
    "nano": ChatterboxNanoAdapter,
}


def resolve_model_adapter_name(model_name, language, device=None):
    requested = str(model_name or "original").strip().lower()

    try:
        capabilities = validate_model_configuration(
            requested,
            language,
            device=device,
        )
    except CapabilityValidationError as error:
        raise ModelCompatibilityError(
            str(error)
        ) from error

    return capabilities.model_id


def create_tts_model_adapter(
    model_name,
    language,
    device,
    cache_dir=None,
) -> TTSModelAdapter:
    resolved_name = resolve_model_adapter_name(
        model_name,
        language,
        device=device,
    )
    adapter_class = ADAPTER_CLASSES[resolved_name]

    return adapter_class(device=device, cache_dir=cache_dir)
