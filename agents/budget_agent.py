from state import AgentState
from main_helpers import ask_ollama


def budget_agent(state: AgentState):
    print("\n--- Budget Agent (Ollama) ---")

    
    if state.get("payment_type") is None:
        
        prompt = (
            "You are a friendly real estate assistant. "
            "Ask the user if they want to pay by cash or installments in a natural way. "
            "Do not answer for them, just ask the question."
        )
        question = ask_ollama(prompt)
        print("Agent:", question)

        
        user_payment_input = input("You: ")
        state["user_input"] = user_payment_input

       
        extract_prompt = (
            f"Extract ONLY the payment type from this input. "
            "Return exactly one word: 'cash' or 'installments'. "
            f"User said: '{user_payment_input}'"
        )
        payment_type = ask_ollama(extract_prompt).strip().lower()

        if payment_type not in ["cash", "installments"]:
            print("Agent: I couldn't understand. Please type 'cash' or 'installments'.")
            return budget_agent(state)  # retry

        state["payment_type"] = payment_type

   
    if state["payment_type"] == "cash" and state.get("budget") is None:
       
        prompt = (
            "You are a friendly real estate assistant. "
            "Ask the user about their total budget in a natural way. "
            "Do not answer for them, only ask the question."
        )
        question = ask_ollama(prompt)
        print("Agent:", question)

        
        user_budget_input = input("You: ")
        state["user_input"] = user_budget_input

        
        extract_prompt = (
            f"Extract ONLY the numeric budget from this input. "
            f"Return just the digits, no extra text.\nUser: '{user_budget_input}'"
        )
        budget_response = ask_ollama(extract_prompt)
        digits = "".join(filter(str.isdigit, budget_response))

        if digits:
            state["budget"] = int(digits)
            state["budget_valid"] = True
            state["next_step"] = "location_agent"
        else:
            print("Agent: I couldn't understand your budget. Let's try again.")
            return budget_agent(state)  # retry

    
    elif state["payment_type"] == "installments":
        
        prompt = (
            "Ask the user about the down payment and the monthly installment in a friendly way. "
            "Do not provide the answers, only ask."
        )
        question = ask_ollama(prompt)
        print("Agent:", question)

        user_downpayment = input("Down payment: ")
        user_monthly = input("Monthly installment: ")

        
        extract_down_prompt = (
            f"Extract ONLY the numeric value for down payment from this input.\nUser: '{user_downpayment}'"
        )
        extract_monthly_prompt = (
            f"Extract ONLY the numeric value for monthly installment from this input.\nUser: '{user_monthly}'"
        )

        down_digits = "".join(filter(str.isdigit, ask_ollama(extract_down_prompt)))
        monthly_digits = "".join(filter(str.isdigit, ask_ollama(extract_monthly_prompt)))

        if down_digits and monthly_digits:
            state["Downpayment"] = int(down_digits)
            state["monthlyinstall"] = int(monthly_digits)
            state["next_step"] = "location_agent"
        else:
            print("Agent: I couldn't understand the numbers. Let's try again.")
            return budget_agent(state)  # retry

    return state
