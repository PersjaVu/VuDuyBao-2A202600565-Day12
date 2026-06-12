"""
Benchmark: Demo tiet kiem latency nho cac toi uu hoa.

Chay: uv run python benchmark_latency.py
"""

import asyncio
import os
import sys
import time
import json

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from common.llm import get_llm
from langchain_core.messages import HumanMessage, SystemMessage


QUESTION = "If a company breaks a contract and avoids taxes, what are the legal and regulatory consequences?"


async def measure_llm_routing() -> float:
    """Do thoi gian LLM-based routing (cach cu — ca check_routing dung LLM)."""
    llm = get_llm()
    messages = [
        SystemMessage(content=(
            'You are a legal routing expert. Based on the question, decide whether '
            'specialist sub-agents are needed.\n'
            'Reply with ONLY valid JSON — no markdown, no extra text:\n'
            '{"needs_tax": <true|false>, "needs_compliance": <true|false>}'
        )),
        HumanMessage(content=QUESTION),
    ]
    t0 = time.perf_counter()
    result = await llm.ainvoke(messages)
    elapsed = time.perf_counter() - t0

    try:
        raw = result.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
    except Exception:
        parsed = {"needs_tax": True, "needs_compliance": True}

    return elapsed, parsed


async def measure_keyword_routing() -> float:
    """Do thoi gian keyword-based routing (cach moi — khong dung LLM)."""
    t0 = time.perf_counter()

    TAX_KEYWORDS = ["tax", "irs", "thue", "evasion", "offshore", "fbar", "fatca"]
    COMPLIANCE_KEYWORDS = ["compliance", "sec", "sox", "regulation", "aml", "fcpa", "gdpr"]
    q = QUESTION.lower()
    needs_tax = any(kw in q for kw in TAX_KEYWORDS)
    needs_compliance = any(kw in q for kw in COMPLIANCE_KEYWORDS)

    elapsed = time.perf_counter() - t0
    return elapsed, {"needs_tax": needs_tax, "needs_compliance": needs_compliance}


async def measure_agent_card_fetch() -> float:
    """Do thoi gian fetch agent card (no cache vs cache)."""
    import httpx
    url = "http://localhost:10101/.well-known/agent.json"
    times = []
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            for i in range(3):
                t0 = time.perf_counter()
                r = await client.get(url)
                times.append(time.perf_counter() - t0)
        return times
    except Exception:
        return []


async def main():
    print("=" * 65)
    print("  BENCHMARK: Latency Optimization Demo")
    print("=" * 65)
    print(f"\nQuestion: {QUESTION[:60]}...")

    # ---- MEASUREMENT 1: LLM routing call ----
    print("\n[1] LLM-based routing (cu) — goi LLM de quyet dinh routing:")
    print("    Dang do...", end="", flush=True)
    try:
        llm_time, llm_result = await measure_llm_routing()
        print(f"\r    Ket qua: {llm_result}")
        print(f"    Thoi gian: {llm_time:.2f}s")
    except Exception as e:
        llm_time = 10.0  # estimate
        print(f"\r    (Khong the chay vi het credits — uoc tinh: ~{llm_time:.1f}s)")

    # ---- MEASUREMENT 2: Keyword routing ----
    print("\n[2] Keyword-based routing (moi) — check tu khoa, khong dung LLM:")
    kw_time, kw_result = await measure_keyword_routing()
    print(f"    Ket qua: {kw_result}")
    print(f"    Thoi gian: {kw_time * 1000:.3f}ms ({kw_time:.6f}s)")

    # ---- MEASUREMENT 3: Agent card fetch ----
    print("\n[3] Agent card fetch (neu services dang chay):")
    fetch_times = await measure_agent_card_fetch()
    if fetch_times:
        print(f"    3 fetches: {[f'{t*1000:.1f}ms' for t in fetch_times]}")
        print(f"    Trung binh: {sum(fetch_times)/len(fetch_times)*1000:.1f}ms")
        print(f"    Voi cache: 3 fetches → fetch 1 lan, cache 2 lan sau = tiet kiem ~{sum(fetch_times[1:])*1000:.0f}ms")
    else:
        print("    (Services khong chay — uoc tinh: ~100-200ms moi fetch)")
        fetch_times = [0.12, 0.11, 0.10]  # estimate

    # ---- SUMMARY ----
    print("\n" + "=" * 65)
    print("  KET QUA TONG HOP")
    print("=" * 65)

    baseline_latency = 62.38

    routing_savings = llm_time
    card_savings = sum(fetch_times[1:]) if len(fetch_times) > 1 else 0.2
    total_savings = routing_savings + card_savings

    optimized_latency = baseline_latency - total_savings

    print(f"""
  Baseline latency:           {baseline_latency:.2f}s   (do thuc te)

  Toi uu #1 — Xoa LLM routing call:
    Truoc: LLM goi de quyet dinh routing  ~ {llm_time:.1f}s
    Sau:   Keyword check (khong co LLM)   ~ {kw_time*1000:.1f}ms
    Tiet kiem:                            ~ {routing_savings:.1f}s

  Toi uu #2 — Cache agent card:
    Truoc: 3 HTTP fetches (registry+agents)
    Sau:   1 fetch, 2 cache hits
    Tiet kiem:                            ~ {card_savings*1000:.0f}ms

  Tong tiet kiem:                         ~ {total_savings:.1f}s
  Optimized latency (uoc tinh):           ~ {optimized_latency:.1f}s
  Giam:                                   {total_savings/baseline_latency*100:.0f}%
""")

    print("=" * 65)
    print("  KIEN TRUC LATENCY BREAKDOWN (Stage 5 A2A)")
    print("=" * 65)
    print("""
  Request flow va thoi gian uoc tinh (moi buoc ~10s voi Claude):

  BASELINE (truoc toi uu):
  ┌─────────────────────────────────────────────────────────┐
  │ Customer Agent  LLM call #1  (quyet dinh delegate)  ~10s │
  │ HTTP: Customer → Law Agent   (fetch card + request)  ~0.2s│
  │ Law Agent       LLM call #2  (analyze_law)          ~10s │
  │ Law Agent       LLM call #3  (check_routing) [XOA]  ~10s │  ← BI LOAi
  │ Tax Agent       LLM call #4  (parallel)              ~10s │
  │ Compliance      LLM call #5  (parallel, max tu #4)  (0s) │
  │ Law Agent       LLM call #6  (aggregate)             ~10s │
  │ Customer Agent  LLM call #7  (format response)       ~10s │
  │ HTTP responses chain                                  ~0.3s│
  │                                                    ───────│
  │ TOTAL:                                              ~60-65s│
  └─────────────────────────────────────────────────────────┘

  OPTIMIZED (sau toi uu):
  ┌─────────────────────────────────────────────────────────┐
  │ Customer Agent  LLM call #1  (quyet dinh delegate)  ~10s │
  │ HTTP: Customer → Law Agent   (card CACHED)           ~0.1s│
  │ Law Agent       LLM call #2  (analyze_law)          ~10s │
  │ Law Agent       keyword check (khong LLM)             ~0ms │  ✓ TIET KIEM
  │ Tax Agent       LLM call #3  (parallel)              ~10s │
  │ Compliance      LLM call #4  (parallel, max tu #3)  (0s) │
  │ Law Agent       LLM call #5  (aggregate)             ~10s │
  │ Customer Agent  LLM call #6  (format response)       ~10s │
  │ HTTP responses  (cards CACHED)                        ~0.1s│
  │                                                    ───────│
  │ TOTAL:                                              ~50-52s│
  └─────────────────────────────────────────────────────────┘
""")


if __name__ == "__main__":
    asyncio.run(main())
