"""Unit tests — monthly budget guard."""
import pytest
import time
from app.cost_guard import check_budget, record_cost, _monthly_costs
from fastapi import HTTPException


def _flush(user_id: str):
    key = f"{user_id}:{time.strftime('%Y-%m')}"
    _monthly_costs.pop(key, None)


def test_within_budget_passes():
    _flush("cg-user-1")
    check_budget("cg-user-1")  # should not raise


def test_over_budget_raises_402():
    _flush("cg-user-2")
    # Exhaust budget: need > $10; 100M output tokens ≈ $60
    record_cost("cg-user-2", input_tokens=10_000_000, output_tokens=100_000_000)

    with pytest.raises(HTTPException) as exc_info:
        check_budget("cg-user-2")
    assert exc_info.value.status_code == 402


def test_record_cost_accumulates():
    _flush("cg-user-3")
    record_cost("cg-user-3", input_tokens=10, output_tokens=10)
    record_cost("cg-user-3", input_tokens=10, output_tokens=10)
    key = f"cg-user-3:{time.strftime('%Y-%m')}"
    assert _monthly_costs.get(key, 0) > 0
