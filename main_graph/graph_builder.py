from typing import Literal
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command
from langchain_core.messages import HumanMessage, AIMessage
from .graph_states import AgentState, StepResult
from utils import get_llm_model, config, invoke_llm_with_retry
from utils.prompt import SUPERVISOR_SYSTEM_PROMPT, HISTORY_PROCESS_TEMPLATE_SUPERVISOR, HISTORY_PROCESS_TEMPLATE_SUBAGENT
from sub_agents import evidence_extractor_node, manual_analyzer_node, model_inspector_node
from sub_agents.report_writer.graph_builder import report_writer_node
from langgraph.checkpoint.memory import MemorySaver
import time


def supervisor_node(state: AgentState) -> Command[Literal["evidence_extractor", "manual_analyzer", "model_inspector", "report_writer"]]:
    
    step_results = state.get("step_results", [])

    if len(step_results) == 0:
        process_history = "The task has not started yet."
    else:
        process_history_parts = []

        for step_result in step_results:
            tmp_agent = step_result['agent']
            tmp_result = step_result['result']
            tmp_reasoning = step_result['reasoning']

            if tmp_agent == 'supervisor':
                history_part = HISTORY_PROCESS_TEMPLATE_SUPERVISOR.format(
                    agent=tmp_agent,
                    reasoning=tmp_reasoning,
                    result=tmp_result
                )
            else:
                history_part = HISTORY_PROCESS_TEMPLATE_SUBAGENT.format(
                    agent=tmp_agent,
                    result=tmp_result
                )
        
            process_history_parts.append(history_part)
        
        process_history = f"\n---\n".join(process_history_parts)

    system_prompt = SUPERVISOR_SYSTEM_PROMPT.format(
        user_request=state.get("user_request", ""),
        process_history=process_history
    )


    class SupervisorResponse(BaseModel):
        """Always use this tool to structure your response."""
        reasoning: str = Field(description="This part is a kind of memo where you freely describe your thought process. Specifically explain the reasons and judgment process of how the next agent and detailed tasks were derived through what thought process. Recording planning and work progress allows you to refer to this for your next work.")
        next_agent: str = Field(description="Name of the agent to perform the next task if next work is needed. If all materials needed for writing the review report have been collected and no additional work is needed, enter FINISH")
        next_task: str = Field(description="Specific task instructions to deliver to the next agent. If next_agent is FINISH, enter an empty string")

    llm = get_llm_model("supervisor")
    
    model_with_structure = llm.with_structured_output(SupervisorResponse)
    
    # 공통 재시도 함수 사용
    response = invoke_llm_with_retry(
        model_with_structure, 
        [HumanMessage(content=system_prompt)], 
        operation_name=f"Supervisor LLM ({config['llm']['supervisor']['model']})"
    )

    # supervisor의 reasoning과 decision을 StepResult에 저장
    supervisor_step = StepResult(
        agent="supervisor",
        reasoning=response.reasoning,
        task="-",  # supervisor는 task를 받지 않음
        result=f"Give task(`{response.next_task}`) to agent(`{response.next_agent}`)" if response.next_agent != "FINISH" else "All necessary information has been gathered. We can now begin writing the final report."
    )
    
    if response.next_agent == "FINISH":
        return Command(
            goto="report_writer",
            update={
                "next_task": "Write a report",
                "next_agent": "report_writer",
                "step_results": [supervisor_step],
                "messages": [AIMessage(content=f"All analysis has been completed. Please write a report.", name="supervisor")]
            }
        )
    else:
        return Command(
            goto=response.next_agent,
            update={
                "next_task": response.next_task,
                "next_agent": response.next_agent,
                "step_results": [supervisor_step],
                "messages": [AIMessage(content=supervisor_step['result'], name="supervisor")]
            }
        )


def build_main_graph() -> StateGraph:
    graph = StateGraph(AgentState)
    graph.add_node("supervisor", supervisor_node)
    graph.add_node("evidence_extractor", evidence_extractor_node)
    graph.add_node("manual_analyzer", manual_analyzer_node)
    graph.add_node("model_inspector", model_inspector_node)
    graph.add_node("report_writer", report_writer_node)
    graph.add_edge(START, "supervisor")
    graph.add_edge("evidence_extractor", "supervisor")
    graph.add_edge("manual_analyzer", "supervisor")  
    graph.add_edge("model_inspector", "supervisor")
    graph.add_edge("report_writer", END)
    graph = graph.compile(checkpointer=MemorySaver())
    return graph