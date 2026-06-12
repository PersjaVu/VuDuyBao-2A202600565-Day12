"""
Mock LLM — no API key needed. Returns canned responses to focus on deployment concepts.
"""
import time
import random

MOCK_RESPONSES = {
    "default": [
        "Xin chao! Toi la AI agent production-ready. (mock response)",
        "Agent dang hoat dong tot! Hoi them cau hoi di nhe. (mock response)",
        "Toi la AI agent duoc deploy len cloud. Cau hoi cua ban da duoc nhan. (mock response)",
    ],
    "docker": ["Container la cach dong goi app de chay o moi noi. Build once, run anywhere!"],
    "deploy": ["Deployment la qua trinh dua code tu may ban len server de nguoi khac dung duoc."],
    "health": ["Agent dang hoat dong binh thuong. All systems operational."],
    "redis": ["Redis la in-memory data store dung cho caching, session, rate limiting va pub/sub."],
    "scale": ["Scaling = chay nhieu instances de xu ly nhieu traffic hon. Stateless design la chìa khoa."],
}


def ask(question: str, history: list = None, delay: float = 0.1) -> str:
    """Mock LLM call with simulated latency. Accepts optional conversation history."""
    time.sleep(delay + random.uniform(0, 0.05))

    question_lower = question.lower()
    for keyword, responses in MOCK_RESPONSES.items():
        if keyword in question_lower:
            return random.choice(responses)

    # If history has context, reference it briefly
    if history and len(history) >= 2:
        last_user = next(
            (m["content"] for m in reversed(history) if m.get("role") == "user"),
            None,
        )
        if last_user and last_user != question:
            return f"(mock) Truoc do ban hoi: '{last_user[:40]}...'. Bay gio ban hoi: '{question[:40]}...'"

    return random.choice(MOCK_RESPONSES["default"])


def ask_stream(question: str):
    """Mock streaming response — yield word by word."""
    response = ask(question)
    for word in response.split():
        time.sleep(0.05)
        yield word + " "
