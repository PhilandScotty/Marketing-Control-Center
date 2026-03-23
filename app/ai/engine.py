"""Anthropic API wrapper for MCC AI features."""
import json
import logging
from typing import Optional

import httpx

from app.config import ANTHROPIC_API_KEY

logger = logging.getLogger("mcc.ai.engine")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """You are the AI assistant for Marketing Command Center (MCC), a marketing execution platform.
You help Phil manage his marketing operations for Grindlab (a poker study SaaS launching soon).

Your personality: Direct, data-driven, action-oriented. No fluff. Focus on what needs to happen next.

You have access to tools that let you query and modify MCC data:
- Channels, metrics, tasks, automations, content pipeline, ads, outreach, subscribers, budget, tech stack, experiments.
- You can create tasks, record metrics, and retrieve execution scores.
- You can track new entities (channels, tools, content, ads, automations, contacts, metrics) and stop tracking them.
  When Phil mentions signing up for a new tool, starting a channel, planning content, etc., proactively use track_entity to add it.

When answering:
1. Lead with the most important insight or action
2. Use specific numbers and data when available
3. Flag risks and blockers proactively
4. Suggest concrete next steps
5. Keep responses concise — Phil is busy executing

Current date context will be provided with each message."""


def is_configured() -> bool:
    return bool(ANTHROPIC_API_KEY)


def _build_tools() -> list[dict]:
    """Build Claude tool definitions for chat."""
    from app.ai.tools import TOOL_DEFINITIONS
    return TOOL_DEFINITIONS


async def call_anthropic(
    messages: list[dict],
    tools: Optional[list[dict]] = None,
    system: Optional[str] = None,
) -> dict:
    """Call the Anthropic API with messages and optional tools."""
    if not ANTHROPIC_API_KEY:
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": "AI features require ANTHROPIC_API_KEY to be set."}],
        }

    payload = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": messages,
    }
    if system:
        payload["system"] = system
    if tools:
        payload["tools"] = tools

    headers = {
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(ANTHROPIC_URL, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
    except Exception as e:
        logger.error(f"Anthropic API error: {e}")
        return {
            "role": "assistant",
            "content": [{"type": "text", "text": f"AI request failed: {e}"}],
        }


async def chat_completion(
    messages: list[dict],
    page_context: Optional[str] = None,
) -> dict:
    """Run a chat completion with tool use support."""
    from datetime import date

    system = SYSTEM_PROMPT + f"\n\nToday's date: {date.today().isoformat()}"
    if page_context:
        system += f"\nPhil is currently viewing: {page_context}"

    tools = _build_tools() if is_configured() else None

    response = await call_anthropic(messages, tools=tools, system=system)
    return response


async def simple_completion(prompt: str, system_override: Optional[str] = None) -> str:
    """Simple single-turn completion for scheduled jobs."""
    if not ANTHROPIC_API_KEY:
        return ""

    system = system_override or SYSTEM_PROMPT
    messages = [{"role": "user", "content": prompt}]

    result = await call_anthropic(messages, system=system)

    # Extract text from response
    content = result.get("content", [])
    texts = [block["text"] for block in content if block.get("type") == "text"]
    return "\n".join(texts)
