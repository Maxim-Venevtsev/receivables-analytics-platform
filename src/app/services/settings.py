import math
import os
from collections.abc import Mapping


DEFAULT_PAGE_RESPONSE_TIMEOUT_SECONDS = 30.0


def get_page_response_timeout(
    environ: Mapping[str, str] | None = None,
) -> float:
    source = os.environ if environ is None else environ
    raw = source.get("APP_PAGE_RESPONSE_TIMEOUT_SECONDS")
    if raw is None:
        return DEFAULT_PAGE_RESPONSE_TIMEOUT_SECONDS
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "APP_PAGE_RESPONSE_TIMEOUT_SECONDS must be a positive finite number"
        ) from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(
            "APP_PAGE_RESPONSE_TIMEOUT_SECONDS must be a positive finite number"
        )
    return value
