from livekit import agents
from livekit.agents import AgentServer, AgentSession, Agent
from livekit.plugins import openai

from dotenv import load_dotenv
load_dotenv(".env")


# Defines the persona/instructions the LLM follows during the conversation.
class Assistant(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are a helpful voice AI assistant.
            Your responses are concise and without complex formatting or emojis.""",
        )


# AgentServer runs as a long-lived process; the CLI dispatches sessions on demand.
server = AgentServer()


# Triggered for each new LiveKit room session. ctx.room is the joined room.
@server.rtc_session()
async def my_agent(ctx: agents.JobContext):
    # Pick the realtime LLM (OpenAI gpt-realtime) and the voice it speaks with.
    # Voice options: alloy, ash, ballad, coral, echo, sage, shimmer, verse, marin, cedar.
    session = AgentSession(llm=openai.realtime.RealtimeModel(voice="marin"))

    # Wire the agent into the room: subscribe to the user's mic, publish the agent's voice.
    await session.start(room=ctx.room, agent=Assistant())

    # Don't wait for the user to speak first — open with a greeting.
    await session.generate_reply(instructions="Greet the user and offer your assistance.")


if __name__ == "__main__":
    agents.cli.run_app(server)
