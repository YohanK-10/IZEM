import json
import re
from typing import Any


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value).strip()
    return [text] if text else []


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()


def _try_parse_feedback_dict(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return None

    text = _strip_code_fences(value)
    if not text:
        return None

    # First handle cases where the model wrapped the JSON object inside a JSON string.
    candidate = text
    for _ in range(3):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            break
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, str):
            candidate = _strip_code_fences(parsed)
            continue
        break

    if not candidate.startswith("{"):
        match = re.search(r"\{.*\}", candidate, re.DOTALL)
        if match:
            candidate = match.group(0)

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def format_feedback_text(value: Any) -> str | None:
    if value is None:
        return None

    parsed = value
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        parsed_dict = _try_parse_feedback_dict(text)
        if parsed_dict is None:
            return _strip_code_fences(text)
        parsed = parsed_dict

    if not isinstance(parsed, dict):
        text = str(parsed).strip()
        return text or None

    # Recover gracefully when the parser stored a "failed to parse" wrapper but the raw
    # response still contains a valid structured payload.
    detected_issues = _as_list(parsed.get("detected_issues"))
    if detected_issues == ["Failed to parse AI response"]:
        nested = (
            _try_parse_feedback_dict(parsed.get("raw_feedback"))
            or _try_parse_feedback_dict(parsed.get("suggested_direction"))
        )
        if nested is not None:
            parsed = nested

    sections: list[str] = []

    progress_status = str(parsed.get("progress_status", "")).replace("_", " ").strip()
    if progress_status:
        sections.append(f"Progress status: {progress_status}")

    student_reasoning = str(parsed.get("student_reasoning", "")).strip()
    if student_reasoning:
        sections.append(f"Student reasoning:\n{student_reasoning}")

    detected_issues = _as_list(parsed.get("detected_issues"))
    if detected_issues:
        sections.append("Detected issues:\n" + "\n".join(f"- {issue}" for issue in detected_issues))

    what_they_did_right = _as_list(parsed.get("what_they_did_right"))
    if what_they_did_right:
        sections.append("What they did right:\n" + "\n".join(f"- {item}" for item in what_they_did_right))

    suggested_direction = str(parsed.get("suggested_direction", "")).strip()
    if suggested_direction:
        sections.append(f"Suggested direction:\n{suggested_direction}")

    key_concepts = _as_list(parsed.get("key_concepts"))
    if key_concepts:
        sections.append("Key concepts:\n" + "\n".join(f"- {concept}" for concept in key_concepts))

    fallback_text = str(parsed.get("raw_feedback", "")).strip()
    if not sections and fallback_text:
        return fallback_text

    return "\n\n".join(section for section in sections if section).strip() or None
