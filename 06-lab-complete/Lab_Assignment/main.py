"""Lab Assignment — Main Entry Point.

Chạy hệ thống Supervisor-Worker RAG Multi-Agent.

Cách dùng:
    # Chạy với câu hỏi mặc định (demo)
    python Lab_Assignment/main.py

    # Chạy với câu hỏi tuỳ chỉnh
    python Lab_Assignment/main.py "Hình phạt cho tội tàng trữ trái phép chất ma tuý là gì?"

Yêu cầu:
    - Tệp .env với OPENROUTER_API_KEY (hoặc OPENAI_API_KEY)
    - Optional: RAG index từ Day08 (nếu đã chạy task1-task4)
      Nếu chưa có index → các workers tự động fallback sang LLM-only

Kiến trúc (Supervisor-Worker Pattern from Day09):
    User → Supervisor (analyze + route) → Workers (parallel) → Aggregator → Answer
"""

from __future__ import annotations

import asyncio
import io
import logging
import sys
import os

# Fix Windows console encoding for Vietnamese characters
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() not in ("utf-8", "utf8"):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

from dotenv import load_dotenv

# Load .env từ project root
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))
load_dotenv()  # fallback: .env trong thư mục hiện tại

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

# Thêm project root vào sys.path để import common/
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# ---------------------------------------------------------------------------
# Demo questions
# ---------------------------------------------------------------------------

DEMO_QUESTIONS = [
    "Hình phạt cho tội tàng trữ trái phép chất ma tuý theo pháp luật Việt Nam là gì?",
    "Quy trình cai nghiện bắt buộc theo Luật Phòng chống ma tuý 2021 như thế nào?",
    "Luật phòng chống ma tuý 2021 quy định gì về việc sử dụng trái phép chất ma tuý?",
]


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run(question: str) -> str:
    """Chạy toàn bộ Supervisor-Worker pipeline và trả về câu trả lời cuối."""
    # Thêm Lab_Assignment dir vào sys.path để import graph dù chạy từ đâu
    _lab_dir = os.path.dirname(__file__)
    if _lab_dir not in sys.path:
        sys.path.insert(0, _lab_dir)
    from graph import create_graph

    logger.info("=" * 60)
    logger.info("Câu hỏi: %s", question)
    logger.info("=" * 60)

    graph = create_graph()

    initial_state = {
        "question": question,
        "query_analysis": "",
        "needs_legal_provisions": False,
        "needs_criminal_penalty": False,
        "needs_rehabilitation": False,
        "legal_provision_result": "",
        "legal_provision_chunks": "",
        "criminal_penalty_result": "",
        "criminal_penalty_chunks": "",
        "rehabilitation_result": "",
        "rehabilitation_chunks": "",
        "final_answer": "",
    }

    result = await graph.ainvoke(initial_state)
    return result.get("final_answer", "")


async def main() -> None:
    """Entry point: chạy demo hoặc câu hỏi từ command line."""
    # Lấy câu hỏi từ argv hoặc dùng demo
    if len(sys.argv) > 1:
        questions = [" ".join(sys.argv[1:])]
    else:
        questions = DEMO_QUESTIONS

    for i, question in enumerate(questions, 1):
        print(f"\n{'='*70}")
        print(f"Câu hỏi {i}: {question}")
        print("=" * 70)
        print("\nĐang xử lý qua Supervisor-Worker pipeline...\n")

        try:
            answer = await run(question)
            print("\nKẾT QUẢ:")
            print("-" * 70)
            print(answer)
            print("-" * 70)
        except Exception as exc:
            logger.exception("Lỗi khi xử lý câu hỏi: %s", exc)
            print(f"\nLỗi: {exc}")

        if i < len(questions):
            print("\n" + "~" * 70)


if __name__ == "__main__":
    asyncio.run(main())
