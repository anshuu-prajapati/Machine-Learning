from livekit.agents import llm
from src.state import UserState
from src.config import RESTAURANT_MENU

@llm.ai_callable(description="Update customer's name when provided")
def update_customer_name(name: str, context: llm.ToolContext) -> str:
    user_state: UserState = context.raw_data["user_state"]
    user_state.customer_name = name
    return f"Customer name updated to {name}."

@llm.ai_callable(description="Update customer's phone number")
def update_phone_number(phone: str, context: llm.ToolContext) -> str:
    user_state: UserState = context.raw_data["user_state"]
    user_state.phone_number = phone
    return f"Phone number updated to {phone}."

@llm.ai_callable(description="Check available discounts and apply 10% offer if asked")
def check_active_offers(context: llm.ToolContext) -> str:
    user_state: UserState = context.raw_data["user_state"]
    user_state.discount_applied = 0.10
    return "Special Offer: 10% discount has been applied to the order."

@llm.ai_callable(description="Add an item to the user's food cart")
def add_item_to_cart(item_name: str, quantity: int, context: llm.ToolContext) -> str:
    user_state: UserState = context.raw_data["user_state"]
    matched = None
    for item in RESTAURANT_MENU:
        if item_name.lower() in item.lower():
            matched = item
            break

    if not matched:
        return f"Sorry, {item_name} is not available in our menu."

    price = RESTAURANT_MENU[matched]
    user_state.cart.append({"item": matched, "quantity": quantity, "price": price})
    return f"Added {quantity} x {matched} to cart."