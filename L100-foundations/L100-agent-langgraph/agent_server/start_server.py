"""FastAPI server that exposes the LangGraph ResponsesAgent over /invocations.

Mirrors the Databricks "agents on apps" server: `mlflow.genai.agent_server.AgentServer`
gives a `/health`, `/invocations`, and an optional chat-proxy UI, with MLflow tracing wired
in. The `@invoke`/`@stream` handlers delegate to the in-process `ResponsesAgent` from
`agent_server.agent`, so the exact same agent runs locally and when served.
"""

from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv

# Load env (catalog, LLM endpoint, profile) before importing the agent, so auth and config
# resolve correctly.
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

from mlflow.genai.agent_server import (  # noqa: E402
    AgentServer,
    invoke,
    setup_mlflow_git_based_version_tracking,
    stream,
)
from mlflow.types.responses import (  # noqa: E402
    ResponsesAgentRequest,
    ResponsesAgentResponse,
    ResponsesAgentStreamEvent,
)

from agent_server.agent import AGENT  # noqa: E402


@invoke()
def invoke(request: ResponsesAgentRequest) -> ResponsesAgentResponse:
    return AGENT.predict(request)


@stream()
async def stream(
    request: ResponsesAgentRequest,
) -> AsyncGenerator[ResponsesAgentStreamEvent, None]:
    # The L100 agent is single-turn; emit the full response as one done event so the
    # chat UI streams a complete answer.
    response = AGENT.predict(request)
    for item in response.output:
        yield ResponsesAgentStreamEvent(type="response.output_item.done", item=item)


agent_server = AgentServer("ResponsesAgent", enable_chat_proxy=True)
# Module-level `app` so multiple uvicorn workers can import it.
app = agent_server.app  # noqa: F841
setup_mlflow_git_based_version_tracking()


def main():
    agent_server.run(app_import_string="agent_server.start_server:app")
