from src.agents.base_agent import BaseVoiceAgent
from src.config import VOICE_ORDER, RESTAURANT_MENU
from src.tools import add_item_to_cart, check_active_offers
from src.state import UserState

ORDER_PROMPT = f"""
You are the Order Taking Assistant.
Menu: {RESTAURANT_MENU}

Goal:
1. Help the customer select items from the menu.
2. Use 'add_item_to_cart' tool when they specify items.
3. Once they are done ordering, summarize their cart in Hinglish/English and offer to transfer to Checkout.
"""

def create_order_agent(user_state: UserState) -> BaseVoiceAgent:
    user_state.current_agent = "order"
    tools = [add_item_to_cart, check_active_offers]
    return BaseVoiceAgent(ORDER_PROMPT, VOICE_ORDER, tools, user_state)