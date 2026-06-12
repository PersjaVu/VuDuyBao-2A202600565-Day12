"""
Stage 6: Tong Ket & Mo Rong — Cau Hoi On Tap + Bai Tap Cong Diem

Chay: python stages/stage_6_summary/main.py
"""


def print_section(title: str, content: str) -> None:
    bar = "=" * 70
    print(f"\n{bar}")
    print(f"  {title}")
    print(bar)
    print(content)


def so_sanh_5_stages() -> None:
    print_section(
        "SO SANH 5 STAGES — LO TRINH PHAT TRIEN",
        """
  Stage 1: Direct LLM
  ┌────────────────────────────────────────────────────────────────┐
  │  User → LLM → Answer                                          │
  │  Uu diem: Don gian, nhanh                                     │
  │  Nhuoc diem: Khong co tools, khong real-time data             │
  │  Dung khi: Cau hoi don gian, chat bot, summarization          │
  └────────────────────────────────────────────────────────────────┘

  Stage 2: LLM + Tools (RAG)
  ┌────────────────────────────────────────────────────────────────┐
  │  User → LLM ⟷ Tools (database, calculator) → Answer          │
  │  Uu diem: Co the tra cuu du lieu thuc                         │
  │  Nhuoc diem: LLM tu quyet dinh khi dung tool, co the sai      │
  │  Dung khi: Q&A voi database, tinh toan, lookup               │
  └────────────────────────────────────────────────────────────────┘

  Stage 3: ReAct Agent
  ┌────────────────────────────────────────────────────────────────┐
  │  User → Agent (Think→Act→Observe loop) → Answer               │
  │  Uu diem: Multi-step reasoning, tu dong dieu phoi tools       │
  │  Nhuoc diem: Kho debug, co the bi lap (loop)                  │
  │  Dung khi: Nghiep vu phuc tap, nhieu buoc, can suy luan       │
  └────────────────────────────────────────────────────────────────┘

  Stage 4: Multi-Agent (In-Process)
  ┌────────────────────────────────────────────────────────────────┐
  │  User → Router → [TaxAgent, ComplianceAgent, PrivacyAgent]    │
  │                  → Aggregate → Answer                          │
  │  Uu diem: Parallel processing, chuyen mon hoa theo domain     │
  │  Nhuoc diem: Tat ca trong 1 process, kho scale                │
  │  Dung khi: Multi-domain questions, can specialist analysis    │
  └────────────────────────────────────────────────────────────────┘

  Stage 5: Distributed A2A
  ┌────────────────────────────────────────────────────────────────┐
  │  [CustomerAgent:10100] → [LawAgent:10101]                      │
  │                              → [TaxAgent:10102]   (HTTP/A2A)  │
  │                              → [ComplianceAgent:10103]         │
  │  Registry:10000 (service discovery)                           │
  │  Uu diem: Scale doc lap, fault-tolerant, production-ready     │
  │  Nhuoc diem: Network latency, ops overhead                    │
  │  Dung khi: Production system, nhieu teams, can scale          │
  └────────────────────────────────────────────────────────────────┘
""",
    )


def cau_hoi_on_tap() -> None:
    print_section("CAU HOI ON TAP — DAP AN", "")

    q1 = """
  CAU 1: Khi nao nen dung single agent thay vi multi-agent?

  Dung single agent khi:
  ✓  Bai toan chi can 1 chuyen mon, khong can routing
  ✓  Du lieu it, khong can parallel processing
  ✓  Team nho, muon giam complexity va debug de hon
  ✓  Latency quan trong hon thoroughness (1 LLM call vs nhieu)
  ✓  Prototype / MVP — xay nhanh, test y tuong truoc

  Dung multi-agent khi:
  ✓  Co nhieu domains ro rang (Tax, Compliance, Privacy)
  ✓  Cac tasks co the chay parallel (giam wall-clock time)
  ✓  Can isolation (loi o 1 agent khong lan sang agent khac)
  ✓  System phai scale tung phan doc lap

  NGUONG QUYET DINH: Neu co >= 2 domains chuyen biet va can
  parallel processing → chon multi-agent. Neu chi co 1 domain
  va sequential reasoning → chon single agent.
"""

    q2 = """
  CAU 2: Uu diem cua A2A protocol so voi gRPC hoac REST thuong?

  REST thuong (barebones):
  - Tu dinh nghia schema request/response
  - Khong co service discovery
  - Khong co agent capability advertisement
  - Phai tu viet error handling, retry, task tracking

  gRPC:
  - Nhanh (binary Protobuf), strong typing
  - Nhung: can .proto files, kho dung trong browser, kho debug
  - Khong built-in cho concept "agent task" hay streaming

  A2A Protocol:
  ✓  CHUAN HOA: Agent Card (/.well-known/agent.json) cong bo
       kha nang cua agent → bat ky client nao cung tu kham pha duoc
  ✓  TASK LIFECYCLE: Trang thai submitted → working → completed
       built-in, khong can tu implement state machine
  ✓  STREAMING: Ho tro Server-Sent Events (SSE) cho long-running tasks
  ✓  MULTI-MODAL: Parts co the la text, file, data — khong chi string
  ✓  INTEROPERABILITY: Agent cua cac framework khac nhau
       (LangGraph, CrewAI, Autogen) giao tiep duoc voi nhau
  ✓  REGISTRY + DISCOVERY: Khong can hardcode URLs, agents dang ky
       va tim nhau qua Registry

  → A2A = REST + task semantics + agent discovery + streaming
"""

    q3 = """
  CAU 3: Lam the nao de prevent infinite delegation loops trong A2A?

  Van de: AgentA → AgentB → AgentA → ... (vo han)

  Giai phap da implement trong du an nay:

  1. DELEGATION DEPTH COUNTER (chinh)
     - Moi request co truong delegation_depth (bat dau tu 0)
     - Moi lan delegate: truyen depth + 1 xuong
     - Law Agent co MAX_DELEGATION_DEPTH = 3
     - Khi depth >= MAX: tra ve ket qua khong delegate tiep
     Code: law_agent/graph.py → check_routing():
       if depth >= MAX_DELEGATION_DEPTH:
           return {"needs_tax": False, "needs_compliance": False}

  2. TRACE ID PROPAGATION
     - trace_id duoc tao 1 lan tai Customer Agent
     - Truyen qua tat ca cac agents
     - Trong logs: logger.info("trace_id=%s depth=%d", ...)
     - De phat hien neu cung trace_id xuat hien nhieu lan

  3. KEYWORD-BASED ROUTING (tranh loop implicit)
     - check_routing() dung keyword thay vi LLM
     - LLM co the "quyet dinh nham" → route vong vo
     - Keyword check: deterministic, no LLM hallucination

  Best practices khac (chua implement):
  - Circuit breaker: ngung goi agent bi loi lien tuc
  - Request ID deduplication: tu choi request co ID da xu ly
  - TTL (time-to-live): moi request co timeout tuyet doi
"""

    q4 = """
  CAU 4: Tai sao can Registry service? Co the hardcode URLs khong?

  Hardcode URLs (vi du: LAW_AGENT = "http://localhost:10101"):
  ✗  Khi deploy: IP/port thay doi → phai sua code + restart
  ✗  Khi scale: chay nhieu instance TaxAgent → client khong biet
  ✗  Khi agent down: khong co cach tat dong redirect sang instance khac
  ✗  Multi-environment: dev/staging/prod phai co config rieng

  Registry service (nhu trong du an):
  ✓  DONG: Agents tu dang ky khi khoi dong
       → url co the thay doi ma client khong can biet truoc
  ✓  DISCOVERY: Law Agent goi discover("tax_question")
       → Registry tra ve URL hien tai cua Tax Agent
  ✓  HEALTH CHECK: Registry co the detect agents da down
  ✓  LOAD BALANCING: Neu co nhieu TaxAgent instances,
       Registry co the round-robin hoac chon instance khoe manh
  ✓  ZERO-DOWNTIME DEPLOY: Deploy TaxAgent moi → dang ky vao Registry
       → Registry chuyen traffic → unregister instance cu

  KET LUAN: Hardcode URLs chi OK khi:
  - Demo / prototype / 1 machine / 1 environment
  - Rat hiem khi thay doi (gia nhu static infrastructure)

  Production: luon dung Registry (hoac Kubernetes Service Discovery,
  Consul, AWS Service Discovery...).
"""

    for q in [q1, q2, q3, q4]:
        print(q)
        print("-" * 70)


def bai_tap_cong_diem() -> None:
    print_section(
        "BAI TAP CONG DIEM — LATENCY ANALYSIS",
        """
  Ket qua do thuc te:
  ─────────────────────────────────────────────────────────────────
  Baseline latency (truoc toi uu):  62.38 giay   ← DA DO THUC TE

  Toi uu da implement:
  1. Keyword-based routing trong law_agent/graph.py
     Truoc: check_routing() goi LLM de quyet dinh co delegate khong
     Sau:   check_routing() dung keyword matching (khong goi LLM)
     File:  law_agent/graph.py (ham check_routing)

  2. Agent card caching trong common/a2a_client.py
     Truoc: Moi lan delegate() fetch /.well-known/agent.json
     Sau:   Fetch 1 lan, cache trong module-level dict _card_cache
     File:  common/a2a_client.py (ham _get_agent_card)

  Uoc tinh tiet kiem:
  ─────────────────────────────────────────────────────────────────
  LLM routing call bi xoa:      ~8-12 giay  (1 LLM round-trip)
  Agent card cache (2 hits):    ~0.2 giay   (2 × HTTP GET saved)
  ─────────────────────────────────────────────────────────────────
  Tong tiet kiem:               ~8-12 giay
  Optimized latency (uoc tinh): ~50-54 giay (~15-20% giam)

  Flow comparison:
  ─────────────────────────────────────────────────────────────────
  BASELINE:
    Customer LLM → [HTTP:card] → Law LLM → Law LLM(routing) ← BI XOA
    → Tax LLM ∥ Compliance LLM → Law LLM(aggregate) → Customer LLM
    = 6 LLM calls × ~10s + network ≈ 62s

  OPTIMIZED:
    Customer LLM → [HTTP:card CACHED] → Law LLM → keyword check(~0ms)
    → Tax LLM ∥ Compliance LLM → Law LLM(aggregate) → Customer LLM
    = 5 LLM calls × ~10s + network ≈ 50-52s

  Ghi chu: Credits het nen khong chay demo truc tiep duoc.
  Chay: python benchmark_latency.py de xem measurement tung phan.
""",
    )


def main() -> None:
    print("\n" + "=" * 70)
    print("  STAGE 6: TONG KET & MO RONG — Legal Multi-Agent System")
    print("=" * 70)

    so_sanh_5_stages()
    cau_hoi_on_tap()
    bai_tap_cong_diem()

    print("\n" + "=" * 70)
    print("  Chuc cac ban hoc tot! 🚀")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
