"""Tax Agent LangGraph definition.

Uses create_react_agent with a tax-specialised system prompt.
No tools — it answers purely from LLM knowledge.
"""

from __future__ import annotations

from langgraph.prebuilt import create_react_agent

from common.llm import get_llm

TAX_SYSTEM_PROMPT = """You are a specialist tax attorney. Answer tax law questions concisely.

Key areas: tax evasion (26 U.S.C. §7201: felony, $250K fine + 5yr prison), civil fraud penalty (75% of underpayment, IRC §6663), FBAR/FATCA offshore requirements, transfer pricing (IRC §482), IRS enforcement.

Format: bullet points only. Max 3 bullets covering (1) criminal exposure, (2) civil penalties, (3) practical steps. Keep each bullet under 30 words. Educational purposes only — consult licensed counsel.
"""


def create_graph():
    """Return a compiled LangGraph create_react_agent for tax questions."""
    llm = get_llm()
    graph = create_react_agent(
        model=llm,
        tools=[],
        prompt=TAX_SYSTEM_PROMPT,
    )
    return graph