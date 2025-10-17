import math
from fastapi import FastAPI, Request

# --- Algoritmi seadusted ja konstandid (Glassbox strateegia) ---

# SOOVITUS #1: Q-väärtused on drastiliselt vähendatud, kuna süsteem on stabiilne.
# Eesmärk on hoida minimaalset varu, mis on vajalik tarnetsükli katmiseks.
OPTIMIZED_Q_VALUES = {
    "retailer": 1.8, #1.60
    "wholesaler": 2.9, #2.5 
    "distributor": 3.4, #3.25
    "factory": 2.0, # 2.0  Tehas vajab veidi rohkem pikema tootmistsükli tõttu
}

# Jätame reageerimiskiiruse kõrgeks.
MOVING_AVERAGE_PERIOD = 4

# SOOVITUS #2: Lühendame silumisperioodi, kuna glassbox süsteem stabiliseerub kiiremini.
SMOOTHING_PERIOD = 3


class BeerBot:
    """
    Kapseldab kogu loogika. See implementatsioon kasutab "Glassbox" strateegiat,
    kus kõik rollid baseerivad oma otsused tegelikul kliendi nõudlusel.
    """

    def _get_demand_forecast(self, weeks: list) -> float:
        """
        Arvutab oodatava nõudluse, kasutades AINULT jaemüüja andmeid.
        See on "Glassbox" strateegia süda.
        """
        # KÕIK rollid vaatavad tegelikku kliendi nõudlust (jaemüüja sissetulevad tellimused).
        history = [week["roles"]["retailer"]["incoming_orders"] for week in weeks]

        if not history:
            return 8.0  # Mõistlik algväärtus

        start_index = max(0, len(history) - MOVING_AVERAGE_PERIOD)
        relevant_history = history[start_index:]
        
        return sum(relevant_history) / len(relevant_history)

    def _calculate_order_for_role(self, role: str, state: dict) -> int:
        """
        Arvutab ühe rolli tellimuse koguse.
        """
        current_week_num = state["week"]
        weeks_history = state["weeks"]
        
        role_data = weeks_history[-1]["roles"][role]
        inventory = role_data["inventory"]
        backlog = role_data["backlog"]
        
        # Arvutame "pipeline" ehk teel oleva kauba koguse
        # See on kõik tellimused, mis on tehtud, aga pole veel kohale jõudnud.
        pipeline = 0
        if current_week_num > 1:
            # Viimase 3 nädala tellimused on tavaliselt hea hinnang teel olevale kaubale
            start_index = max(0, len(weeks_history) - 4) 
            for week in weeks_history[start_index:-1]:
                 if role in week["orders"]:
                    pipeline += week["orders"][role]

        # 1. Prognoosi oodatav nõudlus (kõigil sama)
        demand_forecast = self._get_demand_forecast(weeks_history)

        # 2. Arvuta sihttase laovarule
        base_q = OPTIMIZED_Q_VALUES[role]
        
        if current_week_num < SMOOTHING_PERIOD:
            effective_q = base_q * (current_week_num / SMOOTHING_PERIOD)
        else:
            effective_q = base_q
            
        target_inventory = effective_q * demand_forecast

        # 3. Arvuta praegune laovaru positsioon
        inventory_position = inventory - backlog + pipeline
        
        # 4. Arvuta tellimus
        order = demand_forecast + (target_inventory - inventory_position)

        return max(0, math.ceil(order))

    def get_orders(self, state: dict) -> dict:
        """
        Genereerib tellimused kõikidele rollidele.
        """
        roles = ["retailer", "wholesaler", "distributor", "factory"]
        orders = {role: self._calculate_order_for_role(role, state) for role in roles}
        return {"orders": orders}


# --- FastAPI rakendus ---

app = FastAPI(docs_url=None, redoc_url=None)
beer_bot = BeerBot()

@app.post("/api/decision")
async def handle_decision(request: Request):
    """
    Põhiline API otspunkt.
    """
    state = await request.json()

    if state.get("handshake"):
        return {
            "ok": True,
            "student_email": "jaakta@taltech.ee", # MUUDA SEE ÄRA!
            "algorithm_name": "Coordinated Glassbox v1.0", # Uus nimi!
            "version": "v1.3.0",
            # SOOVITUS #3: Deklareerime, et toetame nüüd Glassboxi!
            "supports": {"blackbox": False, "glassbox": True},
            "message": "BeerBot ready"
        }
    
    return beer_bot.get_orders(state)

@app.get("/")
def read_root():
    return {"message": "BeerBot API on töövalmis. Palun tee POST päring /api/decision."}
