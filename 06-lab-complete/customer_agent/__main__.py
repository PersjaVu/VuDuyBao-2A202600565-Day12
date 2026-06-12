"""Customer Agent server entry point — port 10100."""

from __future__ import annotations

import asyncio
import logging
import os
from uuid import uuid4

import uvicorn
from dotenv import load_dotenv
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain_core.messages import HumanMessage, AIMessage

load_dotenv()

from a2a.server.apps import A2AFastAPIApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCapabilities, AgentCard, AgentSkill

from common.registry_client import register
from customer_agent.agent_executor import CustomerAgentExecutor
from customer_agent.graph import build_graph

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [customer_agent] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

PORT = 10100
AGENT_ENDPOINT = f"http://localhost:{PORT}"


async def _register_with_retry(max_attempts: int = 10, delay: float = 2.0) -> None:
    """Retry registration until the registry is up."""
    info = {
        "agent_name": "customer-agent",
        "version": "1.0",
        "description": "Entry-point legal assistant; routes user questions to the Law Agent",
        "tasks": [],  # Customer Agent is an entry point, not discovered by other agents
        "endpoint": AGENT_ENDPOINT,
        "tags": ["customer", "entry-point", "legal-assistant"],
    }
    for attempt in range(1, max_attempts + 1):
        try:
            await register(info)
            logger.info("Registered with registry (attempt %d)", attempt)
            return
        except Exception as exc:
            logger.warning(
                "Registry not ready (attempt %d/%d): %s — retrying in %.0fs",
                attempt, max_attempts, exc, delay,
            )
            await asyncio.sleep(delay)
    logger.error("Failed to register after %d attempts", max_attempts)


async def main() -> None:
    await _register_with_retry()

    agent_card = AgentCard(
        name="Customer Agent",
        description=(
            "Your legal assistant. Ask any legal question — I will route it through "
            "our network of specialist legal, tax, and compliance agents."
        ),
        url=AGENT_ENDPOINT,
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        default_input_modes=["text/plain"],
        default_output_modes=["text/plain"],
        skills=[
            AgentSkill(
                id="legal_assistant",
                name="Legal Assistant",
                description=(
                    "Answer legal questions by routing them to specialist agents "
                    "covering contract law, tax, and regulatory compliance."
                ),
                tags=["legal", "assistant", "multi-agent"],
            )
        ],
    )

    executor = CustomerAgentExecutor()
    task_store = InMemoryTaskStore()
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=task_store,
    )
    app_builder = A2AFastAPIApplication(
        agent_card=agent_card,
        http_handler=request_handler,
    )
    app = app_builder.build()

    # CORS — allow requests from Vite dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/messages")
    async def chat_endpoint(request: Request) -> JSONResponse:
        """Simple REST endpoint for the frontend demo."""
        try:
            body = await request.json()
            logger.info("REST /messages body: %s", body)
            # Accept common formats: {"content"}, {"question"}, {"message"}, {"text"},
            # or ChatGPT-style {"messages": [{"role":"user","content":"..."}]}
            question = (
                body.get("content")
                or body.get("question")
                or body.get("message")
                or body.get("text")
                or body.get("input")
                or body.get("query")
            )
            # ChatGPT-style: {"messages": [...]}
            if not question and isinstance(body.get("messages"), list):
                for m in reversed(body["messages"]):
                    if m.get("role") == "user" and m.get("content"):
                        question = m["content"]
                        break
            if not question:
                return JSONResponse(
                    {"error": "No question found", "received": body},
                    status_code=400,
                )

            trace_id = str(uuid4())
            context_id = str(uuid4())

            graph = build_graph(trace_id=trace_id, context_id=context_id, depth=0)
            result = await graph.ainvoke(
                {"messages": [HumanMessage(content=question)]},
                config={"configurable": {"thread_id": context_id}},
            )

            answer = ""
            for msg in reversed(result.get("messages", [])):
                if isinstance(msg, AIMessage) and msg.content:
                    content = msg.content
                    # Gemini returns content as list of dicts
                    if isinstance(content, list):
                        parts = [
                            p.get("text", "") if isinstance(p, dict) else str(p)
                            for p in content
                        ]
                        content = "".join(parts)
                    if content and content.strip():
                        answer = content
                        break

            return JSONResponse({"role": "assistant", "content": answer})

        except Exception as exc:
            logger.exception("REST /messages error: %s", exc)
            return JSONResponse({"error": str(exc)}, status_code=500)

    config = uvicorn.Config(app, host="0.0.0.0", port=PORT, log_level="info")
    server = uvicorn.Server(config)
    logger.info("Customer Agent listening on port %d", PORT)
    await server.serve()


if __name__ == "__main__":
    asyncio.run(main())