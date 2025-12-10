from utils.prompt import REPORT_WRITER_SYSTEM_PROMPT, HISTORY_PROCESS_TEMPLATE_SUPERVISOR, HISTORY_PROCESS_TEMPLATE_SUBAGENT
from utils import get_llm_model, config, invoke_llm_with_retry
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from main_graph.graph_states import AgentState, StepResult
from typing import Dict, Any
from langgraph.graph import StateGraph, START, END
import time



def report_writer_node(state: AgentState) -> Dict[str, Any]:
    llm = get_llm_model("report_writer")
    
    step_results = state.get("step_results", [])
    
    process_history_parts = []

    for i, step_result in enumerate(step_results):
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

    system_prompt_content = REPORT_WRITER_SYSTEM_PROMPT.format(
        user_request=state.get("user_request", ""),
        process_history=process_history
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt_content),
        ("human", "{content}")
    ])

    chain = prompt | llm

    response = invoke_llm_with_retry(
        chain, 
        {"content": f'\n\nBased on this, please write a final report.'}, 
        operation_name=f"Report Writer LLM ({config['llm']['report_writer']['model']})"
    )

    step_result = StepResult(
        agent="report_writer",
        reasoning="-",
        task='Write a report',
        result=response.content,
    )

    message = [AIMessage(content=step_result['result'], name="report_writer")]

    return {
        "step_results": [step_result],
        "messages": message
    }


# graph = StateGraph(AgentState)
# graph.add_node("report_writer", report_writer_node)
# graph.add_edge(START, "report_writer")
# graph.add_edge("report_writer", END)
# agent_graph = graph.compile()