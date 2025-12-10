from utils import get_llm_model, parse_eco2od, model_ontology, config, invoke_llm_with_retry
from utils.prompt import MODEL_INSPECTOR_SYSTEM_PROMPT, SUBAGENT_PROMPT
from langgraph.prebuilt import create_react_agent
from langchain_experimental.tools import PythonAstREPLTool
import glob, os
from main_graph.graph_states import AgentState, StepResult
from typing import Dict, Any
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from utils.utils import invoke_graph
from langchain_core.runnables import RunnableConfig


model_dir = config["paths"]["models_dir"]
model_file_suffix = config["model_file"]["suffix"]
ecl2_files = glob.glob(os.path.join(model_dir, f"*{model_file_suffix}"))
parsed_model = parse_eco2od(ecl2_files[0], model_ontology)
dataframe_handler = PythonAstREPLTool(locals={"parsed_model": parsed_model})


def build_model_inspector_agent():
    llm = get_llm_model("model_inspector")
    tools = [dataframe_handler]

    agent_executor  = create_react_agent(
        model=llm.bind_tools(tools, parallel_tool_calls=False),
        tools=tools,
        prompt=MODEL_INSPECTOR_SYSTEM_PROMPT,
    )

    return agent_executor


def model_inspector_node(state: AgentState) -> Dict[str, Any]:
    agent_executor = build_model_inspector_agent()
    
    current_task = state.get("next_task", "")
    reasoning = state.get("step_results", [])[-1].get("reasoning")
    
    prompt_message = SUBAGENT_PROMPT.format(
        reasoning=reasoning,
        current_task=current_task
    )

    response = invoke_llm_with_retry(
        agent_executor, 
        {"messages": [HumanMessage(content=prompt_message)]}, 
        operation_name=f"Model Inspector LLM ({config['llm']['model_inspector']['model']})"
    )

    step_result = StepResult(
        agent="model_inspector",
        reasoning="-",
        task=current_task,
        result=response['messages'][-1].content,
    )

    message = [AIMessage(content=step_result['result'], name="model_inspector")]

    return {
        "step_results": [step_result],
        "messages": message
    }



## For langgraph studio
# graph = StateGraph(AgentState)
# graph.add_node("model_inspector", model_inspector_node)
# graph.add_edge(START, "model_inspector")
# graph.add_edge("model_inspector", END)
# agent_graph = graph.compile()