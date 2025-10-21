import math
from fastapi import FastAPI, Request

app = FastAPI(docs_url=None, redoc_url=None)

# --- parameetrid ---
FORECAST_WINDOW = 4
SMOOTHING_PERIOD = 3
DAMPING_GLASS = 0.25        # summutus glassboxile optimaalne väärtus
DAMPING_BLACK = 0.20        # blackbox pisut tugevam summutus

Q_GLASSBOX = {
    "retailer": 1.8,
    "wholesaler": 3.1,
    "distributor": 4.75,
    "factory": 0.9  # langetatud, et vähendada factory laovaru
}

Q_BLACKBOX = {
    "retailer": 2.4,
    "wholesaler": 3.3,
    "distributor": 5.7,
    "factory": 2.0
}

# mängu rollid
roles = ["retailer", "wholesaler", "distributor", "factory"]


class BeerBot:
    # ---------------------------------------------------------
    # FORECASTID (prognoosid)
    # ---------------------------------------------------------
    def _forecast_glassbox(self, weeks):
        """Glassbox: kasutab jaemüüja tegelikku turu nõudlust."""
        history = [w["roles"]["retailer"]["incoming_orders"] for w in weeks]
        window = history[-FORECAST_WINDOW:]
        return sum(window) / len(window) if window else 4.0

    def _forecast_blackbox(self, weeks, role):
        """Blackbox: kasutab ainult oma rolli nähtavaid numbreid."""
        history = [w["roles"][role]["incoming_orders"] for w in weeks]
        window = history[-FORECAST_WINDOW:]
        return sum(window) / len(window) if window else 4.0

    # ---------------------------------------------------------
    # ORDER LOGIC (otsustusloogika)
    # ---------------------------------------------------------
    def _compute_order(self, role, state, mode):
        weeks = state["weeks"]
        current_week = state["week"]
        role_data = weeks[-1]["roles"][role]

        # tegelik laoseis ja võlg (backlog)
        inventory = role_data["inventory"]
        backlog = role_data["backlog"]

        # pipeline = viimaste 3 nädala tellimused (teel olev kaup)
        if current_week > 1:
            pipeline = sum(w["orders"].get(role, 0) for w in weeks[-4:-1])
        else:
            pipeline = 0

        # forecast vastavalt mode'ile
        if mode == "glassbox":
            demand = self._forecast_glassbox(weeks)
            q = Q_GLASSBOX[role]
            damping = DAMPING_GLASS
        else:
            demand = self._forecast_blackbox(weeks, role)
            q = Q_BLACKBOX[role]
            damping = DAMPING_BLACK

        # Smoothing esimestel nädalatel
        if current_week < SMOOTHING_PERIOD:
            q *= (current_week / SMOOTHING_PERIOD)

        # sihtvaru (palju peaks riiulis olema)
        target = q * demand

        # inventory-position = tegelik + teel - võlad
        inv_position = inventory - backlog + pipeline

        # korrigeeriv liikumine sihtvaru poole
        adjustment = damping * (target - inv_position)

        # kui ülevaru suur → kärbi jõulisemalt (1.4x)
        if inv_position > target:
            adjustment *= 1.4

        # minimaalne vältimatu tellimus (et backlog ei kasvaks)
        expected_shortage = demand - (inventory + pipeline)
        min_needed = math.ceil(expected_shortage) if expected_shortage > 0 else 0

        # lõplik tellimus
        order = max(min_needed, math.ceil(demand + adjustment))
        return max(0, order)

    # ---------------------------------------------------------
    def get_orders(self, state):
        mode = state.get("mode", "blackbox")  # kui puudub → blackbox
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
            "version": "v1.2.0",
            "supports": {"blackbox": True, "glassbox": True},
            "message": "BeerBot ready"
        }

    # Actual order calculation
    return beer_bot.get_orders(data)


@app.get("/")
def root():
    return {"message": "BeerBot API töötab. Kasuta POST /api/decision"}
