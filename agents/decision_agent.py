from state import AgentState
import os
from pymongo import MongoClient
from dotenv import load_dotenv
from financial_calculations import (
    calculate_gross_income,
    calculate_vacancy_loss,
    calculate_effective_gross_income,
    calculate_operating_expenses,
    calculate_noi,
    calculate_net_yield
)

def build_financial_summary(data):

    gross_income = calculate_gross_income(data["monthly_rent"])
    vacancy_loss = calculate_vacancy_loss(gross_income, data["vacancy_rate"])
    egi = calculate_effective_gross_income(gross_income, vacancy_loss)
    expenses = calculate_operating_expenses(**data["expenses"])
    noi = calculate_noi(egi, expenses)
    net_yield = calculate_net_yield(noi, data["purchase_price"])

    return {
        "gross_income": gross_income,
        "effective_gross_income": egi,
        "operating_expenses": expenses,
        "noi": noi,
        "net_yield": net_yield
    }


