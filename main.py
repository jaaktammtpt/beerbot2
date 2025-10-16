import math
from fastapi import FastAPI, Request

# --- Algoritmi seadusted ja konstandid (Stabiliseeritud Glassbox v3.0) ---

# SOOVITUS #2: Q-väärtused on peenhäälestatud, et tabada täpselt sihtmärgi laokulu.
OPTIMIZED_Q_VALUES = {
    "retailer": 1.0,
    "wholesaler": 1.2,
    "distributor": 1.4,
    "factory": 1.7,
}

# SOOVITUS #1: See on kõige olulisem uus parameeter. See silub tellimusi ja vähendab volatiilsust.
# Parandame igal nädalal 70% laovaru veast, mitte 100%.
CORRECTION_FACTOR = 0.7

# Need parameetrid on endiselt optimaalsed.
MOVING_AVERAGE_PERIOD = 4
SMOOTHING_PERIOD = 3


class BeerBot:
    """
    Täppishäälestatud ja stabiliseeritud "Glassbox" strateegia.
    """

    def _get_demand_forecast(self, weeks: list) -> float:
        history = [week["roles"]["retailer"]["incoming_orders"] for week in weeks]
        if not history: return 8.0
        start_index = max(0, len(history) - MOVING_AVERAGE_PERIOD)
        return sum(history[start_index:]) / len(history[start_index:])

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
        
        # Arvutame, kui palju tuleks laovaru korrigeerida
        inventory_error = target_inventory - inventory_position
        
        # RAKENDAME SUMMUTUSTEGURIT: korrigeerime ainult osa veast
        correction_amount = inventory_error * CORRECTION_FACTOR

        # Lõplik tellimus = katame nõudluse + teeme sujuva korrektsiooni
        order = demand_forecast + correction_amount

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
            "algorithm_name": "Stabilized Glassbox v3.0",
            "version": "v1.5.0",
            "supports": {"blackbox": False, "glassbox": True},
            "message": "BeerBot ready"
        }
    return beer_bot.get_orders(state)

@app.get("/")
def read_root():
    return {"message": "BeerBot API on töövalmis. Palun tee POST päring /api/decision."}
