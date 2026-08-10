from src.agents.base_agent import BaseVoiceAgent
from src.config import VOICE_CHECKOUT
from src.tools import update_customer_name, update_phone_number
from src.state import UserState

CHECKOUT_PROMPT = """
You are the Payment & Checkout Specialist.

Goal:
1. State the final total amount due (including discounts if applied).
2. Confirm the customer's Name and Phone Number.
3. Collect payment confirmation and say a polite goodbye in Hinglish/English.
"""

def create_checkout_agent(user_state: UserState) -> BaseVoiceAgent:
    user_state.current_agent = "checkout"
    tools = [update_customer_name, update_phone_number]
    return BaseVoiceAgent(CHECKOUT_PROMPT, VOICE_CHECKOUT, tools, user_state)