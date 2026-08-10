from livekit.agents import VoicePipelineAgent, llm
from livekit.plugins import openai, deepgram, cartesia, silero
from src.state import UserState
from src.config import STT_MODEL, STT_LANGUAGE, LLM_MODEL

class BaseVoiceAgent(VoicePipelineAgent):
    def __init__(self, system_prompt: str, voice_id: str, tools: list, user_state: UserState):
        full_system_prompt = f"""
{system_prompt}

LANGUAGE & TONE GUIDELINES:
- Understand and respond seamlessly in English, Hindi, or Hinglish (Roman Hindi).
- For Hinglish, use natural Roman script (e.g., "Aapka order confirm ho gaya hai").

CURRENT SESSION STATE:
{user_state.to_yaml()}
"""
        super().__init__(
            vad=silero.VAD.load(),
            stt=deepgram.STT(model=STT_MODEL, language=STT_LANGUAGE),
            llm=openai.LLM(model=LLM_MODEL),
            tts=cartesia.TTS(model="sonic-multilingual", voice=voice_id),
            chat_ctx=llm.ChatContext().append(role="system", text=full_system_prompt),
            fnc_ctx=llm.FunctionContext(tools),
            raw_data={"user_state": user_state}
        )
        self.user_state = user_state