import math
from fastapi import FastAPI, Request

app = FastAPI(docs_url=None, redoc_url=None)

# --- Konstandid ---
FORECAST_WINDOW = 4      # Moving average horizon
SMOOTHING_PERIOD = 3     # Soft start smoothing
Z_BLACKBOX = 0.25        # smaller safety param for stable blackbox
Z_GLASSBOX = 0.25        # same for uniformity

# --- Target multipliers per role (Q-values) ---
Q_GLASSBOX = {
    "retailer": 1.8,
    "wholesaler": 3.1,
    "distributor": 4.75,
    "factory": 2.0
}
Q_BLACKBOX = {
    "retailer": 2.0,
    "wholesaler": 3.0,
    "distributor": 4.0,
    "factory": 2.5
}

roles = ["retailer", "wholesaler", "distributor", "factory"]

class BeerBot:

    # --------------------------------------------------
    # FORECAST LOGIC
    # --------------------------------------------------
    def _forecast_blackbox(self, weeks, role):
        """Blackbox: only sees its own demand + backlog."""
        history = []
        for w in weeks:
            r = w["roles"][role]
            history.append(r["incoming_orders"] + r["backlog"])  # backlog-aware
        window = history[-FORECAST_WINDOW:]
        return sum(window) / len(window) if window else 4.0

    def _forecast_glassbox(self, weeks):
        """Glassbox: uses final consumer demand (retailer)."""
        history = [w["roles"]["retailer"]["incoming_orders"] for w in weeks]
        window = history[-FORECAST_WINDOW:]
        return sum(window) / len(window) if window else 4.0

    # --------------------------------------------------
    # ORDER COMPUTATION
    # --------------------------------------------------
    def _compute_order(self, role, state, mode):
        weeks = state["weeks"]
        week = state["week"]
        role_data = weeks[-1]["roles"][role]
        inventory = role_data["inventory"]
        backlog = role_data["backlog"]

        # pipeline approximation (previous orders in last 3 weeks)
        pipeline = sum(
            w["orders"].get(role, 0)
            for w in weeks[-4:-1]
        ) if week > 1 else 0

        # forecast
        if mode == "glassbox":
            demand = self._forecast_glassbox(weeks)
            q = Q_GLASSBOX[role]
            z = Z_GLASSBOX
        else:
            demand = self._forecast_blackbox(weeks, role)
            q = Q_BLACKBOX[role]
            z = Z_BLACKBOX

        # smooth ramp up for first weeks
        if week < SMOOTHING_PERIOD:
            q *= (week / SMOOTHING_PERIOD)

        # target inventory position
        target = q * demand + z * demand
        position = inventory - backlog + pipeline
        order = max(0, math.ceil(demand + (target - position)))

        return order

    # --------------------------------------------------
    # PUBLIC INTERFACE
    # --------------------------------------------------
    def get_orders(self, state):
        mode = state.get("mode", "blackbox")  # fallback if missing
        result = {r: self._compute_order(r, state, mode) for r in roles}
        return {"orders": result}

beer_bot = BeerBot()


# --- MAIN HANDLER ---
@app.post("/api/decision")
async def decision(request: Request):
    payload = await request.json()

    if payload.get("handshake"):
        return {
            "ok": True,
            "student_email": "jaakta@taltech.ee",
            "algorithm_name": "HybridGlassBlack-v1",
            "version": "v1.0.0",
            "supports": {"blackbox": True, "glassbox": True},
            "message": "BeerBot ready"
        }

    return beer_bot.get_orders(payload)


@app.get("/")
def root():
    return {"message": "BeerBot Up — try POST /api/decision"}
