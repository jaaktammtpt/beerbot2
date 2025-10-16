import math
from fastapi import FastAPI, Request

# --- Algoritmi seadusted ja konstandid (Kaalutud prognoosiga Glassbox v4.0) ---

# SOOVITUS #2: Q-väärtused on seatud natuke kõrgemale kui eelviimases katses,
# et vähendada võlgnevuse kulu ja sihtida paremat tasakaalu.
OPTIMIZED_Q_VALUES = {
    "retailer": 1.3,
    "wholesaler": 1.5,
    "distributor": 1.7,
    "factory": 2.0,
}

# Need parameetrid on endiselt optimaalsed.
MOVING_AVERAGE_PERIOD = 4
SMOOTHING_PERIOD = 3


class BeerBot:
    """
    Kasutab kaalutud liikuvat keskmist, et saavutada parem stabiilsus ja reageerimisvõime.
    """

    def _get_demand_forecast(self, weeks: list) -> float:
        """
        SOOVITUS #1: Kasutame kaalutud liikuvat keskmist prognoosi silumiseks.
        """
        history = [week["roles"]["retailer"]["incoming_orders"] for week in weeks]
        if not history: return 8.0
        
        start_index = max(0, len(history) - MOVING_AVERAGE_PERIOD)
        relevant_history = history[start_index:]
        
        if len(relevant_history) < MOVING_AVERAGE_PERIOD:
            # Kui ajalugu on lühem kui meie periood, kasutame lihtsat keskmist
            return sum(relevant_history) / len(relevant_history)
        
        # Kaalud: viimane nädal on kõige olulisem, vanemad vähem.
        weights = [0.1, 0.2, 0.3, 0.4] # [vanim, ..., uusim]
        
        weighted_sum = sum(relevant_history[i] * weights[i] for i in range(len(weights)))
        
        return weighted_sum

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
        
        # Naaseme lihtsa ja otsese loogika juurde, mis parandab kogu vea kohe.
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
            "algorithm_name": "Weighted Glassbox v4.0",
            "version": "v1.6.0",
            "supports": {"blackbox": False, "glassbox": True},
            "message": "BeerBot ready"
        }
    return beer_bot.get_orders(state)

@app.get("/")
def read_root():
    return {"message": "BeerBot API on töövalmis. Palun tee POST päring /api/decision."}
