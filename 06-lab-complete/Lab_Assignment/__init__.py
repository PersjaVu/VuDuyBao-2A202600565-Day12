"""Lab Assignment — RAG Multi-Agent System with Supervisor-Worker Pattern.

Improves the Day08 RAG pipeline by wrapping it in a Day09-style
Supervisor-Worker architecture using LangGraph's StateGraph and Send API.

Architecture:
    User Query
        └→ Supervisor (analyze_query)
               └→ check_routing
                      ├→ [Send] legal_provision_worker   (Luật, điều khoản)
                      ├→ [Send] criminal_penalty_worker  (Hình phạt, tố tụng)
                      └→ [Send] rehabilitation_worker    (Cai nghiện, xã hội)
                               └→ aggregate (RAG synthesis + citation)
"""
