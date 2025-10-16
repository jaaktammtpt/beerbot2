import math
from fastapi import FastAPI, Request

# --- Algoritmi seadistused ja konstandid ---

# Q-väärtused (mitu nädalat laovaru hoida) on tuletatud simulatsioonidest,
# mis on optimeeritud kulude minimeerimiseks. Need on kõige olulisemad parameetrid.
# Madalam Q-väärtus jaemüüjal peegeldab kiiremat reageerimist kliendi nõudlusele.
OPTIMIZED_Q_VALUES = {
    "retailer": 1.5,
    "wholesaler": 2.5,
    "distributor": 2.5,
    "factory": 4.5,
}

# Periood (nädalates) liikuva keskmise arvutamiseks nõudluse prognoosimisel.
MOVING_AVERAGE_PERIOD = 4

# Silumisperiood (nädalates) mängu alguses, et vältida järske tellimusi.
SMOOTHING_PERIOD = 5

class BeerBot:
    """
    Kapseldab kogu loogika, mis on vajalik BeerBoti tellimuste arvutamiseks.
    Strateegia on "must kast" (blackbox), kus iga roll teeb otsuseid ainult oma andmete põhjal.
    """

    def _get_demand_forecast(self, role: str, weeks: list) -> float:
        """
        Arvutab oodatava nõudluse, kasutades liikuva keskmise meetodit.
        """
        # Eralda rolli jaoks olulised sissetulevad tellimused.
        # Teiste rollide jaoks on sisendiks neile eelneva lüli väljastatud tellimused.
        history = []
        if role == "retailer":
            history = [week["roles"]["retailer"]["incoming_orders"] for week in weeks]
        else:
            downstream_map = {
                "wholesaler": "retailer",
                "distributor": "wholesaler",
                "factory": "distributor",
            }
            downstream_role = downstream_map[role]
            # Viimane nädal ei sisalda veel järgmise lüli tellimust, seega `weeks[:-1]`
            history = [week["orders"][downstream_role] for week in weeks[:-1]]

        if not history:
            return 8.0  # Mõistlik algväärtus, kui ajalugu puudub

        # Kasuta liikuva keskmise arvutamiseks viimast `MOVING_AVERAGE_PERIOD` nädalat
        start_index = max(0, len(history) - MOVING_AVERAGE_PERIOD)
        relevant_history = history[start_index:]
        
        return sum(relevant_history) / len(relevant_history)

    def _calculate_order_for_role(self, role: str, state: dict) -> int:
        """
        Arvutab ühe rolli tellimuse koguse, rakendades "silutud Q-mudeli" strateegiat.
        """
        current_week_num = state["week"]
        weeks_history = state["weeks"]
        
        # Hangi viimase nädala andmed selle rolli kohta
        role_data = weeks_history[-1]["roles"][role]
        inventory = role_data["inventory"]
        backlog = role_data["backlog"]
        incoming_orders = role_data["incoming_orders"]
        arriving_shipments = role_data["arriving_shipments"]

        # 1. Prognoosi oodatav nõudlus
        demand_forecast = self._get_demand_forecast(role, weeks_history)

        # 2. Arvuta sihttase laovarule (target inventory)
        base_q = OPTIMIZED_Q_VALUES[role]
        
        # Rakenda silumist mängu alguses
        if current_week_num < SMOOTHING_PERIOD:
            effective_q = base_q * (current_week_num / SMOOTHING_PERIOD)
        else:
            effective_q = base_q
            
        target_inventory = effective_q * demand_forecast

        # 3. Arvuta praegune laovaru positsioon (inventory position)
        # See sisaldab olemasolevat laovaru, tellimusi ja võtab arvesse võlgnevusi.
        inventory_position = inventory - backlog + incoming_orders + arriving_shipments
        
        # 4. Arvuta tellimus
        # Eesmärk: tellida piisavalt, et katta järgmise nädala nõudlus ja liikuda sihttaseme suunas.
        order = demand_forecast + (target_inventory - inventory_position)

        # Tagasta ainult positiivne täisarv
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
    Põhiline ja ainus API otspunkt, mis tegeleb nii "käepigistuse" (handshake)
    kui ka iganädalaste simulatsiooni sammudega.
    """
    state = await request.json()

    # Esimese päringu, "käepigistuse", haldamine
    if state.get("handshake"):
        return {
            "ok": True,
            "student_email": "jaakta@taltech.ee", # MUUDA SEE ÄRA!
            "algorithm_name": "Smoothed Q-Model Blackbox",
            "version": "v1.2.1",
            "supports": {"blackbox": True, "glassbox": False},
            "message": "BeerBot ready"
        }
    
    # Iganädalase simulatsiooni sammu haldamine
    return beer_bot.get_orders(state)

@app.get("/")
def read_root():
    return {"message": "BeerBot API on töövalmis. Palun tee POST päring /api/decision."}
