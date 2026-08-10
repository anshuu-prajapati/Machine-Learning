import asyncio
from livekit.agents import WorkerOptions, cli, JobContext
from src.state import UserState
from src.agents.greeter import create_greeter_agent

async def entrypoint(ctx: JobContext):
    await ctx.connect()
    print(f"Room Connected: {ctx.room.name}")

    # Initialize shared session state
    user_state = UserState()

    # Start with Greeter Agent
    agent = create_greeter_agent(user_state)
    agent.start(ctx.room)

    # Initial spoken welcome in Hinglish
    await agent.say(
        "Namaste! Welcome to Agentic Kitchen. Main Kaira hoon. Aap aaj kya order karna chahenge?", 
        allow_interruptions=True
    )

if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))