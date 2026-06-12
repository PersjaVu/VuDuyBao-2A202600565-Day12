"""Lab Assignment — Supervisor-Worker RAG Graph.

Cải thiện pipeline RAG của Day08 bằng cách áp dụng Supervisor-Worker pattern từ Day09.

Thay vì chạy tuần tự (task1→task2→...→task10), hệ thống này phân tách
thành các agents chuyên biệt chạy SONG SONG thông qua LangGraph Send API.

============================================================
KIẾN TRÚC SUPERVISOR-WORKER
============================================================

                        User Query
                            │
                     [Supervisor]
                    analyze_query          ← phân tích câu hỏi, xác định chủ đề
                            │
                    check_routing          ← keyword routing, không dùng LLM
                            │
          ┌─────────────────┼─────────────────┐
          │ (Send)          │ (Send)           │ (Send)
          ▼                 ▼                  ▼
  legal_provision   criminal_penalty    rehabilitation      ← 3 Workers chạy SONG SONG
     _worker           _worker            _worker
    [Task 5+6]        [Task 5+6]         [Task 5+6]
    [Task 7+9]        [Task 7+9]         [Task 7+9]
   (Điều khoản)    (Hình phạt HS)    (Cai nghiện XH)
          │                 │                  │
          └─────────────────┼──────────────────┘
                            │
                        aggregate              ← tổng hợp = Task 10 (generation+citation)
                            │
                          END

============================================================
TÍCH HỢP DAY08
============================================================
Mỗi Worker gọi `retrieve()` từ Day08 task9_retrieval_pipeline với sub-query
phù hợp với domain của mình:
  - legal_provision_worker  → query tập trung vào điều khoản luật
  - criminal_penalty_worker → query tập trung vào hình phạt hình sự
  - rehabilitation_worker   → query tập trung vào cai nghiện, điều trị

Nếu RAG không có dữ liệu (chưa index), worker tự động fallback sang LLM-only.

Aggregator tổng hợp theo phong cách Task 10: context formatting + citation.
"""

from __future__ import annotations

import asyncio
import logging
import sys
import os
from typing import Annotated, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.constants import Send
from langgraph.graph import END, StateGraph

# Đảm bảo common/ có thể import từ project root
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_DAY08_ROOT = os.path.join(os.path.dirname(__file__), "Day08_RAG_pipeline_cohort2")

if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
if _DAY08_ROOT not in sys.path:
    sys.path.insert(0, _DAY08_ROOT)

from common.llm import get_llm

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Day08 RAG integration helpers
# ---------------------------------------------------------------------------

def _try_retrieve(query: str, top_k: int = 5) -> list[dict]:
    """Gọi Day08 retrieve() — trả về [] nếu chưa có data hoặc gặp lỗi.

    retrieve() là synchronous nên cần chạy trong thread khi dùng async.
    """
    try:
        from src.task9_retrieval_pipeline import retrieve
        results = retrieve(query, top_k=top_k)
        logger.info("RAG retrieve('%s'): %d chunks", query[:50], len(results))
        return results
    except FileNotFoundError:
        logger.warning("RAG index chưa tồn tại — fallback sang LLM-only")
        return []
    except Exception as exc:
        logger.warning("RAG retrieve failed (%s) — fallback sang LLM-only", exc)
        return []


async def retrieve_async(query: str, top_k: int = 5) -> list[dict]:
    """Chạy retrieve() trong thread pool để không block event loop."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _try_retrieve, query, top_k)


def format_rag_context(chunks: list[dict]) -> str:
    """Format chunks thành context string có source label (như task10).

    Mỗi chunk được đánh số và ghi rõ nguồn để LLM có thể cite.
    """
    if not chunks:
        return ""
    parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", f"Nguồn {i}")
        doc_type = meta.get("type", "unknown")
        score = chunk.get("score", 0.0)
        parts.append(
            f"[Document {i} | Nguồn: {source} | Loại: {doc_type} | Score: {score:.3f}]\n"
            f"{chunk['content']}"
        )
    return "\n\n---\n\n".join(parts)


# ---------------------------------------------------------------------------
# Reducer helpers
# ---------------------------------------------------------------------------

def _last_wins(a: str, b: str) -> str:
    """Reducer: giữ giá trị mới nhất (cho phép parallel workers ghi đồng thời)."""
    return b if b else a


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class RAGSupervisorState(TypedDict):
    """Shared state truyền qua toàn bộ graph."""

    # Input
    question: str

    # Supervisor output
    query_analysis: str           # Phân tích sơ bộ từ Supervisor
    needs_legal_provisions: bool  # Cần Worker 1?
    needs_criminal_penalty: bool  # Cần Worker 2?
    needs_rehabilitation: bool    # Cần Worker 3?

    # Worker outputs — Annotated để parallel branches ghi đồng thời (no conflict)
    legal_provision_result: Annotated[str, _last_wins]
    legal_provision_chunks: Annotated[str, _last_wins]   # RAG chunks đã format

    criminal_penalty_result: Annotated[str, _last_wins]
    criminal_penalty_chunks: Annotated[str, _last_wins]

    rehabilitation_result: Annotated[str, _last_wins]
    rehabilitation_chunks: Annotated[str, _last_wins]

    # Final output
    final_answer: str


# ---------------------------------------------------------------------------
# Supervisor Nodes
# ---------------------------------------------------------------------------

async def analyze_query(state: RAGSupervisorState) -> dict:
    """Supervisor Node 1 — Phân tích câu hỏi.

    Vai trò tương đương `analyze_law` trong Law Agent của Day09:
    cung cấp ngữ cảnh nền trước khi dispatch tới workers chuyên biệt.
    """
    llm = get_llm()
    messages = [
        SystemMessage(content=(
            "Bạn là chuyên gia pháp lý về luật phòng chống ma tuý Việt Nam. "
            "Nhiệm vụ: đọc câu hỏi và xác định ngắn gọn (2-3 câu):\n"
            "1. Câu hỏi thuộc lĩnh vực nào (điều khoản luật / hình phạt / cai nghiện)?\n"
            "2. Cần thông tin gì để trả lời đầy đủ?"
        )),
        HumanMessage(content=state["question"]),
    ]
    result = await llm.ainvoke(messages)
    logger.info("[Supervisor] Query analyzed: %s", result.content[:80])
    return {"query_analysis": result.content}


async def check_routing(state: RAGSupervisorState) -> dict:
    """Supervisor Node 2 — Keyword routing.

    Không dùng LLM (tiết kiệm token, giảm latency).
    Quyết định workers nào được gọi dựa trên từ khóa trong câu hỏi.

    Vai trò tương đương `check_routing` trong Law Agent của Day09.
    """
    q = state["question"].lower()

    LEGAL_KW = [
        "luật", "điều", "khoản", "quy định", "nghị định", "thông tư",
        "pháp luật", "văn bản", "phòng chống", "law", "provision",
        "2021", "quy phạm", "hành chính", "vi phạm hành chính",
    ]
    CRIMINAL_KW = [
        "phạt", "hình phạt", "tù", "bắt", "khởi tố", "xét xử", "tòa",
        "tội", "tàng trữ", "buôn bán", "vận chuyển", "sản xuất",
        "penalty", "prison", "crime", "criminal", "sentence", "arrest",
        "blhs", "bộ luật hình sự",
    ]
    REHAB_KW = [
        "cai nghiện", "điều trị", "phục hồi", "trung tâm",
        "tự nguyện", "bắt buộc", "methadone", "opioid", "nghiện",
        "rehabilitation", "treatment", "recovery", "detox",
        "xã hội", "tái hòa nhập", "cộng đồng",
    ]

    needs_legal = any(kw in q for kw in LEGAL_KW)
    needs_criminal = any(kw in q for kw in CRIMINAL_KW)
    needs_rehab = any(kw in q for kw in REHAB_KW)

    # Câu hỏi tổng quát → gọi cả 3 workers để đảm bảo đầy đủ
    if not needs_legal and not needs_criminal and not needs_rehab:
        needs_legal = needs_criminal = needs_rehab = True

    logger.info(
        "[Supervisor] Routing: legal=%s  penalty=%s  rehab=%s",
        needs_legal, needs_criminal, needs_rehab,
    )
    return {
        "needs_legal_provisions": needs_legal,
        "needs_criminal_penalty": needs_criminal,
        "needs_rehabilitation": needs_rehab,
    }


def route_to_workers(state: RAGSupervisorState) -> list[Send]:
    """Edge function — tạo Send objects để dispatch workers song song.

    LangGraph thực thi tất cả Send cùng lúc (parallel).
    Tương đương `route_to_subagents` trong Law Agent.
    """
    sends: list[Send] = []
    if state.get("needs_legal_provisions"):
        sends.append(Send("legal_provision_worker", state))
    if state.get("needs_criminal_penalty"):
        sends.append(Send("criminal_penalty_worker", state))
    if state.get("needs_rehabilitation"):
        sends.append(Send("rehabilitation_worker", state))
    if not sends:  # fallback
        sends = [
            Send("legal_provision_worker", state),
            Send("criminal_penalty_worker", state),
            Send("rehabilitation_worker", state),
        ]
    return sends


# ---------------------------------------------------------------------------
# Worker Nodes — chạy song song qua Send API
# ---------------------------------------------------------------------------

async def legal_provision_worker(state: RAGSupervisorState) -> dict:
    """Worker 1 — Chuyên gia Điều khoản Pháp luật.

    Tích hợp Day08:
      - Dùng task9 retrieve() với sub-query tập trung vào điều khoản luật
      - Format chunks như task10 format_context()
      - Dùng LLM để sinh phân tích chuyên sâu có trích dẫn
      - Fallback LLM-only nếu chưa có RAG index

    Domain: Luật PCMT 2021, Nghị định 116/2021, Thông tư 11/2023
    """
    llm = get_llm()

    # Bước 1: RAG retrieval (Task 9 từ Day08) — sub-query chuyên về pháp luật
    sub_query = f"điều khoản quy định pháp luật {state['question']}"
    chunks = await retrieve_async(sub_query, top_k=4)
    rag_context = format_rag_context(chunks)

    # Bước 2: LLM generation với RAG context (Task 10 style)
    rag_section = (
        f"\n\nContext từ RAG (Day08 Task9):\n{rag_context}"
        if rag_context else
        "\n\n[Chưa có RAG index — trả lời từ kiến thức LLM]"
    )

    messages = [
        SystemMessage(content=(
            "Bạn là chuyên gia pháp lý về Luật Phòng chống ma tuý Việt Nam.\n\n"
            "Kiến thức chuyên sâu:\n"
            "• Luật Phòng chống ma tuý 2021 (hiệu lực 01/01/2022)\n"
            "• Nghị định 116/2021/NĐ-CP về phân loại chất ma tuý\n"
            "• Thông tư 11/2023/TT-BCA về xử lý hành chính ma tuý\n"
            "• Quy trình xử phạt vi phạm hành chính về ma tuý\n\n"
            "Quy tắc trả lời (theo phong cách RAG Task10):\n"
            "1. Nếu có context từ RAG → ưu tiên dùng thông tin đó, trích dẫn nguồn\n"
            "2. Mỗi điều khoản nêu ra phải có trích dẫn: [Điều X, Luật PCMT 2021]\n"
            "3. Nếu không có context → trả lời từ kiến thức và ghi rõ nguồn\n"
            "4. CHỈ phân tích điều khoản pháp luật — KHÔNG phân tích hình phạt hình sự"
        )),
        HumanMessage(content=(
            f"Phân tích tổng quát: {state.get('query_analysis', '')}\n"
            f"Câu hỏi: {state['question']}"
            f"{rag_section}"
        )),
    ]
    result = await llm.ainvoke(messages)
    logger.info("[Worker1-Legal] Done (%d chunks, %d chars)", len(chunks), len(result.content))
    return {
        "legal_provision_result": result.content,
        "legal_provision_chunks": rag_context or "",
    }


async def criminal_penalty_worker(state: RAGSupervisorState) -> dict:
    """Worker 2 — Chuyên gia Hình phạt & Tố tụng Hình sự.

    Tích hợp Day08:
      - Dùng task9 retrieve() với sub-query tập trung vào hình phạt
      - Format chunks như task10 format_context()
      - LLM sinh phân tích hình sự có trích dẫn BLHS
      - Fallback LLM-only nếu chưa có RAG index

    Domain: BLHS 2015 (sửa đổi 2017), Điều 247-259 tội phạm ma tuý
    """
    llm = get_llm()

    # Bước 1: RAG retrieval — sub-query chuyên về hình phạt
    sub_query = f"hình phạt tội phạm bộ luật hình sự {state['question']}"
    chunks = await retrieve_async(sub_query, top_k=4)
    rag_context = format_rag_context(chunks)

    rag_section = (
        f"\n\nContext từ RAG (Day08 Task9):\n{rag_context}"
        if rag_context else
        "\n\n[Chưa có RAG index — trả lời từ kiến thức LLM]"
    )

    messages = [
        SystemMessage(content=(
            "Bạn là chuyên gia luật hình sự chuyên về tội phạm ma tuý tại Việt Nam.\n\n"
            "Kiến thức chuyên sâu:\n"
            "• BLHS 2015 (sửa đổi 2017): Điều 247-259 (Chương XX)\n"
            "  - Điều 248: Tội sản xuất trái phép chất ma tuý\n"
            "  - Điều 249: Tội tàng trữ trái phép chất ma tuý\n"
            "  - Điều 250: Tội vận chuyển trái phép chất ma tuý\n"
            "  - Điều 251: Tội mua bán trái phép chất ma tuý\n"
            "  - Điều 252: Tội chiếm đoạt chất ma tuý\n"
            "• Khung hình phạt theo loại chất, số lượng, vai trò\n"
            "• Tình tiết tăng nặng/giảm nhẹ trách nhiệm hình sự\n\n"
            "Quy tắc trả lời:\n"
            "1. Nếu có context từ RAG → dùng thông tin đó làm ưu tiên\n"
            "2. Nêu điều khoản: [Điều 249 BLHS 2015]\n"
            "3. Nêu khung hình phạt cụ thể (phạt tù X-Y năm, phạt tiền)\n"
            "4. CHỈ phân tích hình phạt hình sự — KHÔNG phân tích điều khoản hành chính"
        )),
        HumanMessage(content=(
            f"Phân tích tổng quát: {state.get('query_analysis', '')}\n"
            f"Câu hỏi: {state['question']}"
            f"{rag_section}"
        )),
    ]
    result = await llm.ainvoke(messages)
    logger.info("[Worker2-Criminal] Done (%d chunks, %d chars)", len(chunks), len(result.content))
    return {
        "criminal_penalty_result": result.content,
        "criminal_penalty_chunks": rag_context or "",
    }


async def rehabilitation_worker(state: RAGSupervisorState) -> dict:
    """Worker 3 — Chuyên gia Cai nghiện & Chính sách Xã hội.

    Tích hợp Day08:
      - Dùng task9 retrieve() với sub-query tập trung vào cai nghiện
      - Format chunks như task10 format_context()
      - LLM sinh phân tích chính sách điều trị có trích dẫn
      - Fallback LLM-only nếu chưa có RAG index

    Domain: Luật PCMT 2021 Chương IV, Nghị định 116/2021, chương trình Methadone
    """
    llm = get_llm()

    # Bước 1: RAG retrieval — sub-query chuyên về cai nghiện
    sub_query = f"cai nghiện điều trị phục hồi ma tuý {state['question']}"
    chunks = await retrieve_async(sub_query, top_k=4)
    rag_context = format_rag_context(chunks)

    rag_section = (
        f"\n\nContext từ RAG (Day08 Task9):\n{rag_context}"
        if rag_context else
        "\n\n[Chưa có RAG index — trả lời từ kiến thức LLM]"
    )

    messages = [
        SystemMessage(content=(
            "Bạn là chuyên gia về chính sách ma tuý và y tế công cộng tại Việt Nam.\n\n"
            "Kiến thức chuyên sâu:\n"
            "• Luật PCMT 2021: Chương IV (Điều 29-50) — Cai nghiện ma tuý\n"
            "  - Điều 29-32: Cai nghiện tự nguyện tại cộng đồng\n"
            "  - Điều 33-39: Cai nghiện tự nguyện tại cơ sở\n"
            "  - Điều 40-50: Cai nghiện bắt buộc\n"
            "• Chương trình điều trị thay thế Methadone (DATC)\n"
            "• Chính sách hỗ trợ tái hòa nhập cộng đồng\n"
            "• Quy trình xác định người nghiện và quyết định cai nghiện bắt buộc\n\n"
            "Quy tắc trả lời:\n"
            "1. Nếu có context từ RAG → dùng thông tin đó làm ưu tiên\n"
            "2. Trích dẫn điều khoản: [Điều 32, Luật PCMT 2021]\n"
            "3. Mô tả quy trình và điều kiện áp dụng\n"
            "4. CHỈ phân tích cai nghiện và chính sách xã hội"
        )),
        HumanMessage(content=(
            f"Phân tích tổng quát: {state.get('query_analysis', '')}\n"
            f"Câu hỏi: {state['question']}"
            f"{rag_section}"
        )),
    ]
    result = await llm.ainvoke(messages)
    logger.info("[Worker3-Rehab] Done (%d chunks, %d chars)", len(chunks), len(result.content))
    return {
        "rehabilitation_result": result.content,
        "rehabilitation_chunks": rag_context or "",
    }


# ---------------------------------------------------------------------------
# Aggregator Node — Task 10 style
# ---------------------------------------------------------------------------

async def aggregate(state: RAGSupervisorState) -> dict:
    """Tổng hợp kết quả từ tất cả workers thành câu trả lời RAG có trích dẫn.

    Đây là phần tương đương Task 10 (generate_with_citation) trong Day08:
    - Context = kết quả từ 3 workers (không phải từ vector store)
    - Sinh câu trả lời tổng hợp theo chuẩn RAG có citation
    - Thêm disclaimer pháp lý

    Tương đương `aggregate` trong Law Agent của Day09.
    """
    llm = get_llm()

    # Thu thập context từ các workers (giống format_context trong task10)
    sections: list[str] = []
    if state.get("legal_provision_result"):
        sections.append(
            "## [Nguồn 1 - Worker 1] Phân tích Điều khoản Pháp luật\n"
            f"{state['legal_provision_result']}"
        )
    if state.get("criminal_penalty_result"):
        sections.append(
            "## [Nguồn 2 - Worker 2] Phân tích Hình phạt & Tố tụng Hình sự\n"
            f"{state['criminal_penalty_result']}"
        )
    if state.get("rehabilitation_result"):
        sections.append(
            "## [Nguồn 3 - Worker 3] Phân tích Cai nghiện & Chính sách Xã hội\n"
            f"{state['rehabilitation_result']}"
        )

    combined_context = "\n\n---\n\n".join(sections)

    messages = [
        SystemMessage(content=(
            "Bạn là chuyên gia pháp lý tổng hợp — kết hợp phân tích từ nhiều nguồn thành "
            "câu trả lời hoàn chỉnh theo chuẩn RAG có trích dẫn (Task 10 style).\n\n"
            "Quy tắc tổng hợp:\n"
            "1. MỌI khẳng định thực tế phải có trích dẫn: [Điều X, Văn bản Y]\n"
            "2. Tổ chức thành các phần rõ ràng (dùng ## heading)\n"
            "3. Loại bỏ thông tin trùng lặp giữa các nguồn\n"
            "4. Ưu tiên thông tin có căn cứ pháp lý cụ thể\n"
            "5. Cuối cùng: tóm tắt ngắn gọn 3-5 điểm chính\n"
            "6. Kết thúc bằng: 'Disclaimer: Thông tin trên mang tính tham khảo, "
            "vui lòng tham vấn luật sư có chuyên môn cho trường hợp cụ thể.'"
        )),
        HumanMessage(content=(
            f"Câu hỏi gốc: {state['question']}\n\n"
            f"Phân tích tổng quát (Supervisor): {state.get('query_analysis', '')}\n\n"
            f"Context từ các Workers:\n{combined_context}"
        )),
    ]
    result = await llm.ainvoke(messages)
    logger.info("[Aggregator] Final answer produced (%d chars)", len(result.content))
    return {"final_answer": result.content}


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def create_graph():
    """Xây dựng và compile Supervisor-Worker RAG Graph.

    Topology:
        analyze_query → check_routing → [Send parallel] workers → aggregate → END

    Nodes:
        Supervisor:  analyze_query, check_routing
        Workers:     legal_provision_worker, criminal_penalty_worker, rehabilitation_worker
        Aggregator:  aggregate
    """
    graph = StateGraph(RAGSupervisorState)

    # Supervisor nodes
    graph.add_node("analyze_query", analyze_query)
    graph.add_node("check_routing", check_routing)

    # Worker nodes (chạy song song qua Send)
    graph.add_node("legal_provision_worker", legal_provision_worker)
    graph.add_node("criminal_penalty_worker", criminal_penalty_worker)
    graph.add_node("rehabilitation_worker", rehabilitation_worker)

    # Aggregator node
    graph.add_node("aggregate", aggregate)

    # Edges — Supervisor flow
    graph.set_entry_point("analyze_query")
    graph.add_edge("analyze_query", "check_routing")

    # Conditional edges: check_routing → parallel workers qua Send
    graph.add_conditional_edges(
        "check_routing",
        route_to_workers,
        ["legal_provision_worker", "criminal_penalty_worker", "rehabilitation_worker"],
    )

    # Workers → Aggregator
    graph.add_edge("legal_provision_worker", "aggregate")
    graph.add_edge("criminal_penalty_worker", "aggregate")
    graph.add_edge("rehabilitation_worker", "aggregate")

    # Aggregator → END
    graph.add_edge("aggregate", END)

    return graph.compile()
