import time
from fastapi import HTTPException
from .config import settings

PRICE_PER_1K_INPUT = 0.00015
PRICE_PER_1K_OUTPUT = 0.0006
_monthly_costs: dict = {}


def check_budget(user_id: str) -> None:
    """Check monthly budget per user. Raises 402 if budget exceeded."""
    key = f"{user_id}:{time.strftime('%Y-%m')}"
    if _monthly_costs.get(key, 0.0) >= settings.monthly_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "Monthly budget exceeded",
                "used_usd": round(_monthly_costs.get(key, 0.0), 4),
                "budget_usd": settings.monthly_budget_usd,
            },
        )


def record_cost(user_id: str, input_tokens: int, output_tokens: int) -> None:
    """Record token usage cost after LLM call."""
    key = f"{user_id}:{time.strftime('%Y-%m')}"
    cost = (input_tokens / 1000) * PRICE_PER_1K_INPUT + (output_tokens / 1000) * PRICE_PER_1K_OUTPUT
    _monthly_costs[key] = _monthly_costs.get(key, 0.0) + cost
