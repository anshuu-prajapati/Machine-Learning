from src.agents.base_agent import BaseVoiceAgent
from src.config import VOICE_GREETER
from src.tools import update_customer_name, check_active_offers
from src.state import UserState

GREETER_PROMPT = """
You are 'Kaira', the friendly receptionist at Agentic Restaurant.
Your goal is to welcome the customer in Hinglish/English/Hindi and route them.
Ask if they would like to place a Takeaway order or check the menu.
"""

def create_greeter_agent(user_state: UserState) -> BaseVoiceAgent:
    user_state.current_agent = "greeter"
    tools = [update_customer_name, check_active_offers]
    return BaseVoiceAgent(GREETER_PROMPT, VOICE_GREETER, tools, user_state)