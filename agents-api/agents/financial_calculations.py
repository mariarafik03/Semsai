def calculate_gross_income(monthly_rent):
    return monthly_rent * 12
def calculate_vacancy_loss(gross_income, vacancy_rate):
    return gross_income * (vacancy_rate / 100)
def calculate_effective_gross_income(gross_income, vacancy_loss):
    return gross_income - vacancy_loss
def calculate_operating_expenses(property_taxes, insurance, maintenance, management_fees, utilities):
    return property_taxes + insurance + maintenance + management_fees + utilities
def calculate_noi(effective_gross_income, operating_expenses):
    return effective_gross_income - operating_expenses
def calculate_net_yield(noi, purchase_price):
    return (noi / purchase_price) * 100
