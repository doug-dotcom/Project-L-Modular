"""Deterministic input compiler for Foundation-governed Concierge specialists.

The compiler mirrors the small public input contracts advertised by Shine Foundation.
It deliberately extracts only explicit user-supplied fields. Missing required fields are
reported back to Concierge instead of guessed, and no memory/context is read here.
"""

from __future__ import annotations

import re
from typing import Callable

SPACE = re.compile(r"\s+")
MARKET_IDENTIFIER = re.compile(
    r"\b(?:ASX|NYSE|NASDAQ|LSE|NZX|TSX|HKEX|SGX|TSE):[A-Z0-9][A-Z0-9.\-]{0,20}\b",
    re.IGNORECASE,
)
QUOTED = re.compile(r'["“”\']([^"“”\']{1,500})["“”\']')

SUPPORTED_LANGUAGES = {
    "english": "en",
    "en": "en",
    "indonesian": "id",
    "bahasa indonesia": "id",
    "id": "id",
    "japanese": "ja",
    "ja": "ja",
    "spanish": "es",
    "es": "es",
    "french": "fr",
    "fr": "fr",
    "german": "de",
    "de": "de",
    "italian": "it",
    "it": "it",
    "portuguese": "pt",
    "pt": "pt",
    "korean": "ko",
    "ko": "ko",
    "mandarin": "zh",
    "chinese": "zh",
    "zh": "zh",
    "punjabi": "pa",
    "pa": "pa",
}

FOCI = ("overview", "earnings", "dividends", "risks", "valuation")
ABILITIES = ("beginner", "intermediate", "advanced", "expert")
DIVE_CERTIFICATIONS = (
    ("advanced open water", "Advanced Open Water"),
    ("nitrox", "Enriched Air Nitrox"),
    ("enriched air", "Enriched Air Nitrox"),
)


def _text(value: str) -> str:
    return SPACE.sub(" ", str(value or "").strip())


def _packet(
    capability_id: str,
    *,
    status: str,
    reason_code: str,
    input_data: dict | None = None,
    missing_fields: list[str] | None = None,
) -> dict:
    packet = {
        "status": status,
        "reason_code": reason_code,
        "capability_id": capability_id,
        "compiler": "deterministic-foundation-contract-v1",
        "missing_fields": list(missing_fields or []),
    }
    if input_data is not None:
        packet["input_data"] = input_data
    return packet


def _bounded(value: str, limit: int) -> str | None:
    value = _text(value)
    if not value or len(value) > limit:
        return None
    return value


def _missing(capability_id: str, *fields: str) -> dict:
    return _packet(
        capability_id,
        status="needs_input",
        reason_code="specialist-input-missing",
        missing_fields=list(fields),
    )


def _ready(capability_id: str, input_data: dict) -> dict:
    return _packet(
        capability_id,
        status="ready",
        reason_code="specialist-input-ready",
        input_data=input_data,
    )


def _destination(message: str, domain_words: tuple[str, ...]) -> str | None:
    text = _text(message)
    domain = "|".join(re.escape(word) for word in domain_words)
    patterns = (
        rf"\b(?:{domain})\b.*?\b(?:to|in|at|around|near|for|on)\s+"
        r"(.+?)(?=\s+(?:for|from|between|starting|leaving|with|targeting|and)\b|[.!?]|$)",
        r"\b(?:to|in|at|around|near|for|on)\s+"
        r"(.+?)(?=\s+(?:for|from|between|starting|leaving|with|targeting|and)\b|[.!?]|$)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if not match:
            continue
        value = match.group(1).strip(" ,:-")
        if value and len(value) <= 120:
            return value
    return None


def _compile_money(capability_id: str, message: str) -> dict:
    question = _bounded(message, 2000)
    if not question:
        return _missing(capability_id, "question")
    return _ready(capability_id, {"question": question})


def _compile_fiona(capability_id: str, message: str) -> dict:
    text = _text(message)
    identifier = None
    market = MARKET_IDENTIFIER.search(text)
    if market:
        identifier = market.group(0).upper()
    else:
        quoted = QUOTED.search(text)
        if quoted:
            identifier = quoted.group(1).strip()
        else:
            match = re.search(
                r"\b(?:company\s+(?:evidence\s+)?brief|brief)\s+(?:on|for|about)\s+"
                r"(.+?)(?=\s+(?:with\s+)?(?:overview|earnings|dividends|risks|valuation)\b|[.!?]|$)",
                text,
                re.IGNORECASE,
            )
            if match:
                identifier = match.group(1).strip(" ,:-")
    identifier = _bounded(identifier or "", 80)
    if not identifier:
        return _missing(capability_id, "identifier")
    data = {"identifier": identifier}
    lower = text.lower()
    focus = next((item for item in FOCI if re.search(rf"\b{item}\b", lower)), None)
    if focus:
        data["focus"] = focus
    return _ready(capability_id, data)


def _compile_daash(capability_id: str, message: str) -> dict:
    text = _text(message)
    exercise = None
    quoted = QUOTED.search(text)
    if quoted:
        exercise = quoted.group(1).strip()
    else:
        patterns = (
            r"\b(?:explain|show|describe)\s+(?:the\s+)?(?:exercise\s+)?(.+?)(?=[.!?]|$)",
            r"\b(?:exercise|movement|technique)\s*(?::|-)?\s*(.+?)(?=[.!?]|$)",
        )
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                exercise = match.group(1).strip(" ,:-")
                break
    exercise = _bounded(exercise or "", 160)
    if not exercise:
        return _missing(capability_id, "exercise")
    data = {"exercise": exercise}
    question = _bounded(text, 1000)
    if question and question.lower() != exercise.lower():
        data["question"] = question
    return _ready(capability_id, data)


def _compile_translate(capability_id: str, message: str) -> dict:
    text = _text(message)
    lower = text.lower()
    source = target = None

    language_pattern = "|".join(
        sorted((re.escape(name) for name in SUPPORTED_LANGUAGES), key=len, reverse=True)
    )
    lang_match = re.search(
        rf"\bfrom\s+({language_pattern})\s+to\s+({language_pattern})\b",
        lower,
        re.IGNORECASE,
    )
    if lang_match:
        source = SUPPORTED_LANGUAGES[lang_match.group(1).lower()]
        target = SUPPORTED_LANGUAGES[lang_match.group(2).lower()]
    else:
        target_match = re.search(
            rf"\bto\s+({language_pattern})\b",
            lower,
            re.IGNORECASE,
        )
        if target_match:
            target = SUPPORTED_LANGUAGES[target_match.group(1).lower()]

    translated_text = None
    quoted = QUOTED.search(text)
    if quoted:
        translated_text = quoted.group(1).strip()
    elif lang_match:
        prefix = text[: lang_match.start()]
        prefix = re.sub(
            r"^(?:shine\s+translate\s*[:,-]?\s*)?(?:please\s+)?translate\s+",
            "",
            prefix,
            flags=re.IGNORECASE,
        )
        translated_text = prefix.strip(" ,:-")

    missing = []
    translated_text = _bounded(translated_text or "", 500)
    if not translated_text:
        missing.append("text")
    if not source:
        missing.append("sourceLanguage")
    if not target:
        missing.append("targetLanguage")
    if missing:
        return _missing(capability_id, *missing)

    data = {
        "text": translated_text,
        "sourceLanguage": source,
        "targetLanguage": target,
    }
    tone = next(
        (value for value in ("natural", "formal", "casual") if re.search(rf"\b{value}\b", lower)),
        None,
    )
    if tone:
        data["tone"] = tone
    return _ready(capability_id, data)


def _compile_travel(capability_id: str, message: str) -> dict:
    destination = _destination(message, ("trip", "holiday", "travel"))
    if not destination:
        return _missing(capability_id, "destination")
    return _ready(capability_id, {"destination": destination})


def _compile_dive(capability_id: str, message: str) -> dict:
    destination = _destination(message, ("dive", "diving", "scuba"))
    if not destination:
        return _missing(capability_id, "destination")
    lower = _text(message).lower()
    certifications: list[str] = []
    for needle, label in DIVE_CERTIFICATIONS:
        if needle in lower and label not in certifications:
            certifications.append(label)
    data = {"destination": destination}
    if certifications:
        data["certifications"] = certifications
    return _ready(capability_id, data)


def _compile_fish(capability_id: str, message: str) -> dict:
    text = _text(message)
    destination = _destination(text, ("fish", "fishing"))
    if not destination:
        return _missing(capability_id, "destination")
    data = {"destination": destination}
    species_match = re.search(
        r"\b(?:targeting|chasing)\s+([A-Za-z][A-Za-z '\-]{1,60})(?=[,.!?]|$)",
        text,
        re.IGNORECASE,
    )
    if species_match:
        species = _bounded(species_match.group(1).strip(), 64)
        if species and species.lower() != destination.lower():
            data["species"] = species
    query = _bounded(text, 1000)
    if query:
        data["query"] = query
    return _ready(capability_id, data)


def _compile_ski(capability_id: str, message: str) -> dict:
    text = _text(message)
    destination = _destination(text, ("ski", "snow", "snowboard", "snowboarding"))
    if not destination:
        return _missing(capability_id, "destination")
    data = {"destination": destination}
    lower = text.lower()
    ability = next((item for item in ABILITIES if re.search(rf"\b{item}\b", lower)), None)
    if ability:
        data["ability"] = ability
    return _ready(capability_id, data)


def _compile_dnd(capability_id: str, message: str) -> dict:
    query = _bounded(message, 2000)
    return _ready(capability_id, {"query": query} if query else {})


COMPILERS: dict[str, Callable[[str, str], dict]] = {
    "daash.exercise_explain": _compile_daash,
    "dive.destination_brief": _compile_dive,
    "dnd.campaign_context": _compile_dnd,
    "fiona.company_brief": _compile_fiona,
    "fish.destination_brief": _compile_fish,
    "money.explain_calculate": _compile_money,
    "ski.destination_brief": _compile_ski,
    "translate.text": _compile_translate,
    "travel.plan_trip": _compile_travel,
}


def compile_specialist_input(capability_id: str, message: str) -> dict:
    """Compile one bounded specialist input from explicit user text only."""
    capability_id = str(capability_id or "").strip()
    compiler = COMPILERS.get(capability_id)
    if compiler is None:
        return _packet(
            capability_id,
            status="unsupported",
            reason_code="specialist-input-contract-unsupported",
        )
    return compiler(capability_id, message)
