import math
from fastapi import FastAPI, Request

app = FastAPI(docs_url=None, redoc_url=None)

# --- parameetrid ---
FORECAST_WINDOW = 4
SMOOTHING_PERIOD = 3
DAMPING_GLASS = 0.25        # summutus glassboxile optimaalne väärtus
DAMPING_BLACK = 0.20        # blackbox pisut tugevam amort (võib hiljem timmida)

Q_GLASSBOX = {
    "retailer": 1.8,
    "wholesaler": 3.1,
    "distributor": 4.75,
    "factory": 2.0
}

Q_BLACKBOX = {
    "retailer": 2.4, # 2.4
    "wholesaler": 3.2, # 3.2
    "distributor": 5.1, # 5.0
    "factory": 2.5
}

roles = ["retailer", "wholesaler", "distributor", "factory"]


class BeerBot:
    # ---------------------------------------------------------
    # FORECASTID
    # ---------------------------------------------------------
    def _forecast_glassbox(self, weeks):
        """Glassbox: kasutab jaemüüja tegelikku turu nõudlust."""
        history = [w["roles"]["retailer"]["incoming_orders"] for w in weeks]
        window = history[-FORECAST_WINDOW:]
        return sum(window) / len(window) if window else 4.0

    def _forecast_blackbox(self, weeks, role):
        """Blackbox: kasutab ainult oma rolli nähtavaid numbreid."""
        history = []
        for w in weeks:
            d = w["roles"][role]["incoming_orders"]
            history.append(d)
        window = history[-FORECAST_WINDOW:]
        return sum(window) / len(window) if window else 4.0

    # ---------------------------------------------------------
    # ORDER LOGIC
    # ---------------------------------------------------------
    def _compute_order(self, role, state, mode):
        weeks = state["weeks"]
        current_week = state["week"]
        role_data = weeks[-1]["roles"][role]

        inventory = role_data["inventory"]
        backlog = role_data["backlog"]

        # pipeline = viimaste 3 nädala tellimused
        if current_week > 1:
            pipeline = sum(w["orders"].get(role, 0) for w in weeks[-4:-1])
        else:
            pipeline = 0

        # forecast vastavalt mode'ile
        if mode == "glassbox":
            demand = self._forecast_glassbox(weeks)
            q = Q_GLASSBOX[role]
            damping = DAMPING_GLASS
        else:   # blackbox
            demand = self._forecast_blackbox(weeks, role)
            q = Q_BLACKBOX[role]
            damping = DAMPING_BLACK

        # smoothing esimestel nädalatel
        if current_week < SMOOTHING_PERIOD:
            q *= (current_week / SMOOTHING_PERIOD)

        # target inventory ja adjustment
        target = q * demand
        inv_position = inventory - backlog + pipeline
        adjustment = damping * (target - inv_position)

        # lõplik tellimus
        order = max(0, math.ceil(demand + adjustment))
        return order

    # ---------------------------------------------------------
    def get_orders(self, state):
        mode = state.get("mode", "blackbox")  # kui puudub, loetakse blackbox
        orders = {r: self._compute_order(r, state, mode) for r in roles}
        return {"orders": orders}


beer_bot = BeerBot()


# ---------------------------------------------------------
# API HANDLER
# ---------------------------------------------------------
@app.post("/api/decision")
async def handle(request: Request):
    data = await request.json()

    # Handshake
    if data.get("handshake"):
        return {
            "ok": True,
            "student_email": "jaakta@taltech.ee",
            "algorithm_name": "HybridGlassBlack-v1",
            "version": "v1.1.0",
            "supports": {"blackbox": True, "glassbox": True},
            "message": "BeerBot ready"
        }

    # Actual order calculation
    return beer_bot.get_orders(data)


@app.get("/")
def root():
    return {"message": "BeerBot API töötab. Kasuta POST /api/decision"}
