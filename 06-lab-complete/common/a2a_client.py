"""A2A delegation helper.

Provides `delegate(endpoint, question, context_id, trace_id, depth)` which
sends a message to another A2A agent and returns the text response.
"""

from __future__ import annotations

import logging
from uuid import uuid4

import httpx

from a2a.client import A2AClient
from a2a.types import (
    AgentCard,
    Message,
    MessageSendParams,
    Part,
    Role,
    SendMessageRequest,
    TextPart,
)

logger = logging.getLogger(__name__)

# Module-level cache: endpoint URL → AgentCard
# Avoids refetching /.well-known/agent.json on every delegation call
_card_cache: dict[str, AgentCard] = {}


async def _get_agent_card(http_client: httpx.AsyncClient, endpoint: str) -> AgentCard:
    """Fetch and cache the agent card for a given endpoint."""
    if endpoint not in _card_cache:
        card_url = f"{endpoint}/.well-known/agent.json"
        card_resp = await http_client.get(card_url)
        card_resp.raise_for_status()
        _card_cache[endpoint] = AgentCard.model_validate(card_resp.json())
        logger.debug("Agent card cached for %s", endpoint)
    else:
        logger.debug("Agent card cache HIT for %s", endpoint)
    return _card_cache[endpoint]


async def delegate(
    endpoint: str,
    question: str,
    context_id: str,
    trace_id: str,
    depth: int,
    max_retries: int = 3,
) -> str:
    """Send a question to an A2A agent and return the text response with retry logic.

    Args:
        endpoint: Base URL of the target agent (e.g. "http://localhost:10101").
        question: The question to ask.
        context_id: Current A2A context ID to propagate.
        trace_id: Trace ID generated at the Customer Agent; propagated throughout.
        depth: Current delegation depth (used to enforce MAX_DELEGATION_DEPTH).
        max_retries: Số lần thử lại nếu có lỗi xảy ra.

    Returns:
        The agent's text response, or an empty string if none could be extracted.
    """
    import asyncio
    
    last_exception = None
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=300.0) as http_client:
                # Fetch agent card (cached after first call)
                agent_card = await _get_agent_card(http_client, endpoint)

                # Build deprecated (legacy) A2AClient — straightforward for send_message
                client = A2AClient(httpx_client=http_client, agent_card=agent_card)

                # Build message with trace metadata
                message = Message(
                    role=Role.user,
                    parts=[Part(root=TextPart(text=question))],
                    message_id=str(uuid4()),
                    context_id=context_id,
                    metadata={
                        "trace_id": trace_id,
                        "context_id": context_id,
                        "delegation_depth": depth,
                    },
                )

                request = SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(message=message),
                )

                logger.debug(
                    "Delegating to %s (depth=%d, trace=%s) - Attempt %d/%d", 
                    endpoint, depth, trace_id, attempt, max_retries
                )

                response = await client.send_message(request)

                # Extract text from SendMessageResponse
                return _extract_text(response)
                
        except Exception as e:
            last_exception = e
            logger.warning("Attempt %d/%d failed when calling %s: %s", attempt, max_retries, endpoint, e)
            if attempt < max_retries:
                backoff_time = 2 ** attempt  # Exponential backoff: 2s, 4s...
                logger.info("Waiting %d seconds before retrying...", backoff_time)
                await asyncio.sleep(backoff_time)
            
    logger.error("Failed to delegate to %s after %d attempts.", endpoint, max_retries)
    return f"Error: Could not reach agent at {endpoint} after {max_retries} attempts. Details: {str(last_exception)}"


def _extract_text(response: object) -> str:
    """Walk the response tree and collect all TextPart.text values."""
    text = ""

    # Unwrap root if it's a RootModel
    if hasattr(response, "root"):
        response = response.root

    # SendMessageSuccessResponse has a .result (Task | Message)
    result = getattr(response, "result", None)
    if result is None:
        return text

    # Task — text lives in artifacts
    artifacts = getattr(result, "artifacts", None)
    if artifacts:
        for artifact in artifacts:
            parts = getattr(artifact, "parts", []) or []
            for part in parts:
                text += _part_text(part)
        if text:
            return text

    # Message — text lives in parts directly
    parts = getattr(result, "parts", None)
    if parts:
        for part in parts:
            text += _part_text(part)

    # Task history messages as fallback
    if not text:
        history = getattr(result, "history", None)
        if history:
            for msg in history:
                msg_parts = getattr(msg, "parts", []) or []
                for part in msg_parts:
                    text += _part_text(part)

    return text


def _part_text(part: object) -> str:
    """Extract text from a Part object (handling both Part(root=TextPart) and raw TextPart)."""
    inner = getattr(part, "root", part)
    return getattr(inner, "text", "") or ""