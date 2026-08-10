import os
from dotenv import load_dotenv

load_dotenv()

LIVEKIT_URL = os.getenv("LIVEKIT_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# Multilingual Models & Voice Settings
STT_MODEL = "nova-2"
STT_LANGUAGE = "multi"  # Supports Auto-detection for English, Hindi, Hinglish

LLM_MODEL = "gpt-4o"

# Cartesia Multilingual Voice IDs suitable for Indian Accent / Hinglish
VOICE_GREETER = "79a125e8-cd45-4c13-8a67-188112f4dd22"
VOICE_ORDER = "a0e89892-eac1-4328-98e3-a006c6020c02"
VOICE_CHECKOUT = "6947081f-a107-4e37-a16d-31122616f653"

# Restaurant Menu
RESTAURANT_MENU = {
    "Margarita Pizza": 14.99,
    "Pepperoni Pizza": 16.99,
    "Garlic Bread": 5.99,
    "Tiramisu": 6.99,
    "Cold Coffee": 4.50,
    "Craft Beer": 6.00
}