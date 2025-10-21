import math
from fastapi import FastAPI, Request

app = FastAPI(docs_url=None, redoc_url=None)

# ---------------------------------------------------------
# PÕHIPARAMEETRID
# ---------------------------------------------------------
FORECAST_WINDOW = 4        # Kui pika ajalooga arvestatakse nõudluse prognoosis
SMOOTHING_PERIOD = 3       # Esimestel nädalatel Q väärtuse sujuv sissejooks
DAMPING_GLASS = 0.25       # Glassbox – väiksem summutus (täpsem prognoos)
DAMPING_BLACK = 0.20       # Blackbox – rohkem summutamist (mürasem prognoos)

# Glassbox režiimis võib tehas hoida märgatavalt väiksemat Q taset,
# sest ta saab turu tegeliku nõudluse (jaeklientide põhjal) otse kätte.
Q_GLASSBOX = {
    "retailer": 1.8,
    "wholesaler": 3.1,
    "distributor": 4.75,
    "factory": 0.6   # vähendatud 2.0 → 0.9 → 0.6 → madalam inventar, väiksem kulu
}

# Blackbox režiimis risk on suurem → kõrgem puhver Q
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
    # NÕUDLUSE PROGNOOS
    # ---------------------------------------------------------
    def _forecast_glassbox(self, weeks):
        """Glassbox: kasutab jaemüüja tegelikku turu nõudlust (puhtam signaal)."""
        history = [w["roles"]["retailer"]["incoming_orders"] for w in weeks]
        window = history[-FORECAST_WINDOW:]
        return sum(window) / len(window) if window else 4.0

    def _forecast_blackbox(self, weeks, role):
        """Blackbox: roll näeb ainult *enda* incoming_orders'i (viitega signaal)."""
        history = [w["roles"][role]["incoming_orders"] for w in weeks]
        window = history[-FORECAST_WINDOW:]
        return sum(window) / len(window) if window else 4.0

    # ---------------------------------------------------------
    # TELLIMUSE ARVUTUS
    # ---------------------------------------------------------
    def _compute_order(self, role, state, mode):
        weeks = state["weeks"]
        current_week = state["week"]
        role_data = weeks[-1]["roles"][role]

        # tegelik laovaru + võimalik tarnimata võlg
        inventory = role_data["inventory"]
        backlog = role_data["backlog"]

        # pipeline = viimase 3 nädala tellimused, mis on "teel"
        if current_week > 1:
            pipeline = sum(w["orders"].get(role, 0) for w in weeks[-4:-1])
        else:
            pipeline = 0

        # Glassbox vs Blackbox
        if mode == "glassbox":
            demand = self._forecast_glassbox(weeks)
            q = Q_GLASSBOX[role]

            # TEHASEL väike summutus → kiirem kohanemine
            damping = 0.20 if role == "factory" else DAMPING_GLASS
        else:  # blackbox
            demand = self._forecast_blackbox(weeks, role)
            q = Q_BLACKBOX[role]
            damping = DAMPING_BLACK

        # Smoothing esimestel nädalatel – Q kasvab järk-järgult
        if current_week < SMOOTHING_PERIOD:
            q *= (current_week / SMOOTHING_PERIOD)

        # target inventory ja adjustment
        target = q * demand
        inv_position = inventory - backlog + pipeline
        adjustment = damping * (target - inv_position)

        # --- ASÜMMEETRILINE INVENTORY REDUKTSIOON ---
        # Kui oleme üle sihitaseme, tugevdame vähendavat efekti.
        # See aitab tehase lao "rasva" maha võtta.
        if inv_position > target:
            adjustment *= 1.8

        # lõplik tellimus
        order = max(0, math.ceil(demand + adjustment))
        return order

    # ---------------------------------------------------------
    # ORDERID KÕIGILE ROLLIDELE
    # ---------------------------------------------------------
    def get_orders(self, state):
        mode = state.get("mode", "blackbox")  # vaikimisi blackbox
        orders = {r: self._compute_order(r, state, mode) for r in roles}
        return {"orders": orders}


beer_bot = BeerBot()

# ---------------------------------------------------------
# API
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

    # Otsus loogika põhjal
    return beer_bot.get_orders(data)


@app.get("/")
def root():
    return {"message": "BeerBot API töötab. Kasuta POST /api/decision"}
