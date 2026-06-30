"""
payment_agent.py — Handle payment type and installment details

RESPONSIBILITY
──────────────
Extract and validate payment preferences including type (cash/installment),
downpayment, and monthly installments.
All messages written by the LLM via agents.llm_messages.

WORKFLOW
────────
1. Get payment type (cash/installment)
2. If cash → we're done
3. If installment → get downpayment
4. Get monthly installment
5. Validate all payment details together
"""

from state import AgentState
from agents.utils.extractors import (
    extract_payment_type,
    extract_downpayment,
    extract_monthly_installment,
)
from agents.utils.validators import validate_payment_type, validate_payment_details
from agents.utils.error_helpers import should_retry, get_remaining_retries
from agents.llm_messages import (
    ask_for_payment_type,
    payment_type_retry,
    payment_type_give_up,
    ask_for_downpayment,
    downpayment_retry,
    downpayment_give_up,
    ask_for_monthly_installment,
    monthly_installment_retry,
    monthly_installment_give_up,
)


def payment_agent(state: AgentState) -> AgentState:
    print("\n--- Payment Agent ---")

    # ═══════════════════════════════════════════════════════════════
    # STEP 1: Get payment type first
    # ═══════════════════════════════════════════════════════════════
    if not state.context.payment_type:
        if state.waiting_for == "payment_type":
            extracted, confidence, _ = extract_payment_type(state.user_input)

            if not extracted:
                if should_retry(state, "payment_type"):
                    remaining = get_remaining_retries(state, "payment_type")
                    state.agent_message = payment_type_retry(
                        "I didn't catch that. How would you like to pay? (cash or installment)",
                        remaining,
                        state,
                    )
                    state.add_error("payment_type", state.user_input, "Could not extract")
                else:
                    state.agent_message = payment_type_give_up(state)
                    state.waiting_for = None
                    state.handoff_to_human = True

                state.sync_to_legacy()
                return state

            is_valid, normalized, error = validate_payment_type(extracted)

            if is_valid:
                state.context.payment_type = normalized
                state.waiting_for = None
                print(f"✓ Payment type set: {extracted} → {normalized}")
            else:
                if should_retry(state, "payment_type"):
                    remaining = get_remaining_retries(state, "payment_type")
                    state.agent_message = payment_type_retry(error, remaining, state)
                    state.add_error("payment_type", extracted, error)
                else:
                    state.agent_message = payment_type_give_up(state)
                    state.waiting_for = None
                    state.handoff_to_human = True

                state.sync_to_legacy()
                return state
        else:
            state.agent_message = ask_for_payment_type(state)
            state.waiting_for = "payment_type"
            state.sync_to_legacy()
            return state

    # ═══════════════════════════════════════════════════════════════
    # STEP 2: If cash → we're done
    # ═══════════════════════════════════════════════════════════════
    if state.context.payment_type == "cash":
        if state.context.downpayment is not None or state.context.monthly_installment is not None:
            print("✓ Payment changed to cash, cleared installment details")

        state.context.downpayment = None
        state.context.monthly_installment = None
        state.sync_to_legacy()
        return state

    # ═══════════════════════════════════════════════════════════════
    # STEP 3: If installment → get downpayment
    # ═══════════════════════════════════════════════════════════════
    if not state.context.downpayment:
        if state.waiting_for == "downpayment":
            extracted, confidence, _ = extract_downpayment(state.user_input)

            if not extracted:
                if should_retry(state, "downpayment"):
                    remaining = get_remaining_retries(state, "downpayment")
                    state.agent_message = downpayment_retry(remaining, state)
                    state.add_error("downpayment", state.user_input, "Could not extract")
                else:
                    state.agent_message = downpayment_give_up(state)
                    state.waiting_for = None
                    state.handoff_to_human = True

                state.sync_to_legacy()
                return state

            state.context.downpayment = extracted
            state.waiting_for = None
            print(f"✓ Downpayment set: {extracted}")
        else:
            state.agent_message = ask_for_downpayment(state)
            state.waiting_for = "downpayment"
            state.sync_to_legacy()
            return state

    # ═══════════════════════════════════════════════════════════════
    # STEP 4: Get monthly installment
    # ═══════════════════════════════════════════════════════════════
    if not state.context.monthly_installment:
        if state.waiting_for == "monthly_installment":
            extracted, confidence, _ = extract_monthly_installment(state.user_input)

            if not extracted:
                if should_retry(state, "monthly_installment"):
                    remaining = get_remaining_retries(state, "monthly_installment")
                    state.agent_message = monthly_installment_retry(remaining, state)
                    state.add_error("monthly_installment", state.user_input, "Could not extract")
                else:
                    state.agent_message = monthly_installment_give_up(state)
                    state.waiting_for = None
                    state.handoff_to_human = True

                state.sync_to_legacy()
                return state

            state.context.monthly_installment = extracted
            state.waiting_for = None
            print(f"✓ Monthly installment set: {extracted}")
        else:
            state.agent_message = ask_for_monthly_installment(state)
            state.waiting_for = "monthly_installment"
            state.sync_to_legacy()
            return state

    # ═══════════════════════════════════════════════════════════════
    # STEP 5: Validate payment details together
    # ═══════════════════════════════════════════════════════════════
    if (
        state.context.payment_type == "installment"
        and state.context.downpayment
        and state.context.monthly_installment
    ):
        is_valid, error = validate_payment_details(
            state.context.payment_type,
            state.context.budget,
            state.context.downpayment,
            state.context.monthly_installment,
        )

        if not is_valid:
            state.agent_message = error
            state.context.monthly_installment = None
            state.waiting_for = "monthly_installment"
            state.add_error(
                "payment_details",
                f"DP:{state.context.downpayment},MI:{state.context.monthly_installment}",
                error,
            )
            print(f"❌ Payment details validation failed: {error}")
        else:
            print("✓ Payment details completely validated")

    state.sync_to_legacy()
    return state
