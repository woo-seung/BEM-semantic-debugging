from typing import TypedDict, List, Annotated
from pydantic import Field
from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages


class StepResult(TypedDict):
    agent: str = Field(description="The name of the agent that performed the task for this step")
    reasoning: str = Field(description="The reasoning process by which the supervisor decides on the next agent and task. If the `agent` is not the supervisor, mark with '-'")
    task: str = Field(description="The task that the agent at this step has been requested to perform by the supervisor. If the `agent` is the supervisor, mark it with '-'")
    result: str = Field(description="The work results of this step")


def add_step_results(left: List[StepResult], right: List[StepResult]) -> List[StepResult]:
    if not left:
        left = []
    if not right:
        right = []
    return left + right


class AgentState(TypedDict):
    user_request: str
    
    step_results: Annotated[List[StepResult], add_step_results]

    messages: Annotated[list[AnyMessage], add_messages]

    next_agent: str

    next_task: str