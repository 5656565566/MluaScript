from __future__ import annotations


def ensure_config_models_registered() -> None:
    import mluascript.shared.config.models as _
    import mluascript.maa.config.models as _
