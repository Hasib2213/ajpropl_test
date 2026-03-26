import asyncio
import random
import time
from typing import Any, Dict

import replicate

from config.settings import settings


class InvalidReplicateModelError(Exception):
    """Raised when Replicate model/version is invalid or inaccessible."""


class InvalidReplicateInputError(Exception):
    """Raised when Replicate input payload fails validation."""


_REPLICATE_SEMAPHORE = asyncio.Semaphore(max(1, settings.REPLICATE_MAX_CONCURRENT))
_LAST_REPLICATE_CALL_TS = 0.0
_LAST_REPLICATE_CALL_LOCK = asyncio.Lock()


async def _respect_min_interval() -> None:
    global _LAST_REPLICATE_CALL_TS

    min_interval = max(0.0, settings.REPLICATE_MIN_INTERVAL_SECONDS)
    if min_interval == 0:
        return

    async with _LAST_REPLICATE_CALL_LOCK:
        now = time.monotonic()
        wait_for = (_LAST_REPLICATE_CALL_TS + min_interval) - now
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        _LAST_REPLICATE_CALL_TS = time.monotonic()


def _is_invalid_model_error(error_text: str) -> bool:
    text = error_text.lower()
    return (
        "invalid version" in text
        or "specified version does not exist" in text
        or "not permitted" in text
    )


def _is_input_validation_error(error_text: str) -> bool:
    text = error_text.lower()
    return (
        "input validation failed" in text
        or "does not match format 'uri'" in text
        or ("status: 422" in text and "input." in text)
    )


def _is_rate_limit_error(error_text: str) -> bool:
    text = error_text.lower()
    return "status: 429" in text or "throttled" in text or "rate limit" in text


async def run_replicate_with_retry(model: str, input_payload: Dict[str, Any]) -> Any:
    retries = max(0, settings.REPLICATE_MAX_RETRIES)

    for attempt in range(retries + 1):
        try:
            async with _REPLICATE_SEMAPHORE:
                await _respect_min_interval()
                return await asyncio.to_thread(replicate.run, model, input=input_payload)
        except Exception as exc:
            error_text = str(exc)

            if _is_invalid_model_error(error_text):
                raise InvalidReplicateModelError(error_text) from exc

            if _is_input_validation_error(error_text):
                raise InvalidReplicateInputError(error_text) from exc

            is_last_attempt = attempt >= retries
            if not _is_rate_limit_error(error_text) or is_last_attempt:
                raise

            # Exponential backoff for 429 throttling.
            wait_seconds = min(
                settings.REPLICATE_BACKOFF_BASE_SECONDS * (2 ** attempt),
                settings.REPLICATE_BACKOFF_MAX_SECONDS,
            )
            wait_seconds += random.uniform(0.0, 0.5)
            await asyncio.sleep(wait_seconds)
