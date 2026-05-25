"""
LLM wrappers around Gemini with automatic cost/latency tracking.

UPDATED Final:
- Auto-logs every call to cost_tracker
- Uses contextvars to track which agent is calling
- Returns timing info for streaming dashboards
"""
import time
from contextvars import ContextVar
from typing import Any

import google.generativeai as genai
from pydantic import BaseModel

from src.config import GEMINI_API_KEY, GEMINI_MODEL
from src.cost_tracker import log_llm_call


# Context variable: each agent sets this before calling
current_agent: ContextVar[str] = ContextVar("current_agent", default="unknown")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def _require_api_key() -> None:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY not found. Add it to your .env file.")


def set_current_agent(name: str):
    """Set the current agent name for cost-tracking attribution."""
    current_agent.set(name)


def _inline_schema_refs(schema: dict) -> dict:
    """Inline $ref references using $defs/definitions for Gemini compatibility."""
    defs = schema.get("$defs") or schema.get("definitions") or {}

    def resolve(node):
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                if ref.startswith("#/$defs/"):
                    name = ref.split("/")[-1]
                    if name in defs:
                        return resolve(defs[name])
                if ref.startswith("#/definitions/"):
                    name = ref.split("/")[-1]
                    if name in defs:
                        return resolve(defs[name])
            return {k: resolve(v) for k, v in node.items() if k != "$ref"}
        if isinstance(node, list):
            return [resolve(item) for item in node]
        return node

    inlined = resolve(schema)
    if isinstance(inlined, dict):
        inlined.pop("$defs", None)
        inlined.pop("definitions", None)
    return inlined


def _remove_unsupported_fields(schema: dict) -> None:
    """Strip unsupported JSON Schema keys for Gemini structured output."""
    unsupported_keys = [
        "title",
        "$defs",
        "definitions",
        "minimum",
        "maximum",
        "minLength",
        "maxLength",
        "minItems",
        "maxItems",
        "min_length",
        "max_length",
    ]
    for key in list(schema.keys()):
        if key in unsupported_keys:
            del schema[key]

    if "required" in schema and "properties" not in schema:
        schema["properties"] = {}

    for value in schema.values():
        if isinstance(value, dict):
            _remove_unsupported_fields(value)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    _remove_unsupported_fields(item)


def call_llm_structured(prompt: str, response_schema: type[BaseModel]) -> BaseModel:
    """
    Structured Gemini call. Returns a validated Pydantic instance.
    Auto-logs the call to the cost tracker.
    """
    agent = current_agent.get()
    start = time.time()
    output_text = ""
    success = True
    error = None

    try:
        _require_api_key()
        schema = response_schema.model_json_schema()
        schema = _inline_schema_refs(schema)
        _remove_unsupported_fields(schema)

        model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": schema,
                "temperature": 0.2,
            },
        )
        response = model.generate_content(prompt)
        output_text = response.text or ""

        try:
            result = response_schema.model_validate_json(output_text)
            return result
        except Exception as e:
            success = False
            error = f"Schema validation failed: {e}"
            raise ValueError(
                f"Failed to parse LLM response into {response_schema.__name__}: {e}\n"
                f"Raw: {output_text[:500]}"
            )
    except Exception as e:
        if success:
            success = False
            error = str(e)
        raise
    finally:
        latency_ms = int((time.time() - start) * 1000)
        log_llm_call(
            agent_name=agent,
            model=GEMINI_MODEL,
            input_text=prompt,
            output_text=output_text,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )


def call_llm_text(prompt: str, temperature: float = 0.7) -> str:
    """
    Plain text Gemini call. Auto-logs.
    """
    agent = current_agent.get()
    start = time.time()
    output_text = ""
    success = True
    error = None

    try:
        _require_api_key()
        model = genai.GenerativeModel(
            GEMINI_MODEL,
            generation_config={"temperature": temperature},
        )
        response = model.generate_content(prompt)
        output_text = response.text or ""
        return output_text
    except Exception as e:
        success = False
        error = str(e)
        raise
    finally:
        latency_ms = int((time.time() - start) * 1000)
        log_llm_call(
            agent_name=agent,
            model=GEMINI_MODEL,
            input_text=prompt,
            output_text=output_text,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )