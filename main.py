import math
from fastapi import FastAPI, Request

# --- Algoritmi seadusted ja konstandid (Lihtsustatud ja optimeeritud Glassbox v5.0) ---

# SOOVITUS #1: Q-väärtused on seatud, et saavutada parem tasakaal, tuginedes
# varasemale edukale mudelile (kogukulu 6786). Eesmärk on vähendada võlgnevuse kulu.
OPTIMIZED_Q_VALUES = {
    "retailer": 1.1,
    "wholesaler": 1.3,
    "distributor": 1.5,
    "factory": 1.8,
}

# Tagasi lihtsa ja stabiilse prognoosimise juurde.
MOVING_AVERAGE_PERIOD = 4
SMOOTHING_PERIOD = 3


class BeerBot:
    """
    Naaseb stabiilse ja tõestatud loogika juurde, keskendudes ainult Q-väärtuste
    peenhäälestamisele, et saavutada eesmärgiks seatud kogukulu.
    """

    def _get_demand_forecast(self, weeks: list) -> float:
        """
        Kasutab lihtsat, mitte-kaalutud liikuvat keskmist. See on kõige stabiilsem meetod.
        """
        history = [week["roles"]["retailer"]["incoming_orders"] for week in weeks]
        if not history: return 8.0
        
        start_index = max(0, len(history) - MOVING_AVERAGE_PERIOD)
        relevant_history = history[start_index:]
        
        return sum(relevant_history) / len(relevant_history)

    def _calculate_order_for_role(self, role: str, state: dict) -> int:
        current_week_num = state["week"]
        weeks_history = state["weeks"]
        
        role_data = weeks_history[-1]["roles"][role]
        inventory = role_data["inventory"]
        backlog = role_data["backlog"]
        arriving_shipments = role_data["arriving_shipments"]

        demand_forecast = self._get_demand_forecast(weeks_history)

        base_q = OPTIMIZED_Q_VALUES[role]
        effective_q = base_q * (current_week_num / SMOOTHING_PERIOD) if current_week_num < SMOOTHING_PERIOD else base_q
        target_inventory = effective_q * demand_forecast

        inventory_position = inventory - backlog + arriving_shipments
        
        # Parandame kogu laovaru vea koheselt. See on kõige otsesem ja ennustatavam meetod.
        inventory_error = target_inventory - inventory_position
        order = demand_forecast + inventory_error

        return max(0, math.ceil(order))

    def get_orders(self, state: dict) -> dict:
        roles = ["retailer", "wholesaler", "distributor", "factory"]
        return {"orders": {role: self._calculate_order_for_role(role, state) for role in roles}}


# --- FastAPI rakendus ---

app = FastAPI(docs_url=None, redoc_url=None)
beer_bot = BeerBot()

@app.post("/api/decision")
async def handle_decision(request: Request):
    state = await request.json()
    if state.get("handshake"):
        return {
            "ok": True,
            "student_email": "eesnimi.perenimi@taltech.ee", # MUUDA SEE ÄRA!
            "algorithm_name": "Simplified Glassbox v5.0",
            "version": "v1.7.0",
            "supports": {"blackbox": False, "glassbox": True},
            "message": "BeerBot ready"
        }
    return beer_bot.get_orders(state)

@app.get("/")
def read_root():
    return {"message": "BeerBot API on töövalmis. Palun tee POST päring /api/decision."}
