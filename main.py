from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from typing import Dict, List
from math import ceil
import statistics


app = FastAPI(
    title="Vercel + FastAPI",
    description="Vercel + FastAPI",
    version="1.0.0",
)


INVENTORY_COST = 1
BACKLOG_COST = 2
TARGET_FACTOR = BACKLOG_COST / (INVENTORY_COST + BACKLOG_COST)
MIN_SAFETY_OFFSET = 2
MAX_REL_CHANGE = 0.5
RECENT_WEEKS = 4

def safe_int(x: float) -> int:
    return max(0, int(x))

def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))

def compute_forecast(demands: List[int]) -> float:
    if not demands:
        return 10.0
    n = len(demands)
    avg = sum(demands) / n
    trend = (demands[-1] - demands[0]) / (n - 1) if n > 1 else 0.0
    return avg + trend

def adaptive_safety_offset(demands: List[int]) -> int:
    if len(demands) <= 1:
        std = 0.0
    else:
        std = statistics.pstdev(demands)
    offset = int(max(MIN_SAFETY_OFFSET, ceil(std * 1.5)))
    return offset

def limited_change(prev_order: int, desired_order: int) -> int:
    if prev_order <= 0:
        return desired_order
    max_change = max(1, int(prev_order * MAX_REL_CHANGE))
    delta = desired_order - prev_order
    delta_limited = int(clamp(delta, -max_change, max_change))
    return prev_order + delta_limited

@app.post("/api/decision")
async def beerbot_decision(request: Request):
    body = await request.json()

    if body.get("handshake", False):
        return JSONResponse({
            "ok": True,
            "student_email": "jaakta@taltech.ee",
            "algorithm_name": "CostAwareStableBeerBot",
            "version": "v1.1.0",
            "supports": {"blackbox": True, "glassbox": False},
            "message": "BeerBot ready"
        })

    weeks = body.get("weeks", [])
    if not isinstance(weeks, list) or len(weeks) == 0:
        return JSONResponse({
            "orders": {"retailer": 10, "wholesaler": 10, "distributor": 10, "factory": 10}
        })

    roles_list = ["retailer", "wholesaler", "distributor", "factory"]

    def recent_demands_for(role: str) -> List[int]:
        recent = []
        for w in weeks[-RECENT_WEEKS:]:
            try:
                recent.append(int(w["roles"][role]["incoming_orders"]))
            except Exception:
                pass
        return recent

    def last_order_for(role: str) -> int:
        try:
            return int(weeks[-1]["orders"].get(role, 0))
        except Exception:
            return 0

    orders: Dict[str, int] = {}

    for role in roles_list:
        demands = recent_demands_for(role)
        forecast = compute_forecast(demands)
        safety = adaptive_safety_offset(demands)

        try:
            last_state = weeks[-1]["roles"][role]
            inventory = int(last_state.get("inventory", 0))
            backlog = int(last_state.get("backlog", 0))
            arriving_shipments = int(last_state.get("arriving_shipments", 0))
            incoming_orders = int(last_state.get("incoming_orders", 0))
        except Exception:
            inventory = backlog = arriving_shipments = incoming_orders = 0

        target = TARGET_FACTOR * forecast
        base_desired = target + backlog - inventory + safety

        expected_next_net = forecast - (inventory + arriving_shipments)
        min_needed = int(ceil(expected_next_net)) if expected_next_net > 0 else 0

        immediate_gap = incoming_orders - (inventory + arriving_shipments)
        min_cover = int(ceil(immediate_gap)) if immediate_gap > 0 else 0

        desired_order = max(base_desired, min_needed, min_cover, 0)
        desired_order_int = int(desired_order)

        if len(weeks) == 1:
            final_order = desired_order_int
        else:
            prev_order = last_order_for(role)
            final_order = limited_change(prev_order, desired_order_int)

        final_order = safe_int(final_order)
        orders[role] = final_order

    return JSONResponse({"orders": orders})
