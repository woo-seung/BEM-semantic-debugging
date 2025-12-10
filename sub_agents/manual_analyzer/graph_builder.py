from typing import Dict, Any, List, Annotated
from langchain_core.tools import tool
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel, Field
from main_graph.graph_states import AgentState, StepResult
from utils import get_llm_model, config, invoke_llm_with_retry
from pathlib import Path
import os
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter
from utils.prompt import MANUAL_ANALYZER_SYSTEM_PROMPT, SUBAGENT_PROMPT
from langgraph.graph import StateGraph, START, END


def build_manual_vectordb(force_rebuild: bool = False) -> None:
    
    manual_path = Path(config["paths"]["manual"])
    faiss_index_path = Path(config["vector_db"]["manual"]["persist_directory"])
    
    # 디렉토리 생성
    faiss_index_path.mkdir(parents=True, exist_ok=True)
    
    if force_rebuild or not (faiss_index_path / "index.faiss").exists():
        print("manual 문서 벡터 데이터베이스를 새로 구축합니다...")
        
        # 마크다운 파일 목록 가져오기
        md_files = [f for f in manual_path.glob("*.md") if f.is_file()]
        
        if not md_files:
            print(f"경고: {manual_path}에서 마크다운 파일을 찾을 수 없습니다.")
            return
        
        print(f"처리할 마크다운 파일 수: {len(md_files)}")
        
        # 문서 로드
        documents = []
        for md_file in md_files:
            print(f"로딩 중: {md_file.name}")
            loader = TextLoader(str(md_file), encoding="utf-8")
            documents.extend(loader.load())
        
        print(f"총 {len(documents)}개의 문서를 로드했습니다.")
        
        headers_to_split_on = [
            ("#", "Header 1"),
            ("##", "Header 2"),
        ]
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=False
        )
        
        all_splits = []
        for doc in documents:
            splits = markdown_splitter.split_text(doc.page_content)
            # 메타데이터 유지
            for split in splits:
                split.metadata.update(doc.metadata)
            all_splits.extend(splits)
        
        print(f"문서를 {len(all_splits)}개의 청크로 분할했습니다.")
        
        # 임베딩 생성 및 벡터스토어 구축
        print("임베딩 생성 및 벡터스토어 구축 중...")
        embeddings = OpenAIEmbeddings(model=config["embedding"]["model"])
        vectorstore = FAISS.from_documents(all_splits, embeddings)
        
        # 인덱스 저장
        vectorstore.save_local(folder_path=faiss_index_path)
        print(f"Manual 문서의 벡터 데이터베이스가 {faiss_index_path}에 저장되었습니다.")
    else:
        print("기존 manual 문서 벡터 데이터베이스를 사용합니다.")


def get_manual_retriever():
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_openai import OpenAIEmbeddings
        
        faiss_index_path = Path(config["vector_db"]["manual"]["persist_directory"])
        
        if not (faiss_index_path / "index.faiss").exists():
            print("매뉴얼 벡터 데이터베이스가 존재하지 않습니다. 벡터DB를 생성합니다...")
            build_manual_vectordb()
        
        embeddings = OpenAIEmbeddings(model=config["embedding"]["model"])
        vectorstore = FAISS.load_local(str(faiss_index_path), embeddings, allow_dangerous_deserialization=True)
        return vectorstore.as_retriever(search_kwargs={"k": config["retriever"]["manual"]["top_k"]})
        
    except Exception as e:
        print(f"벡터스토어 로드 중 오류 발생: {e}")
        return None


@tool
def manual_retriever(
    query: Annotated[str, "Content you want to find in the manual related to simulation modeling procedures and guidelines"]
) -> str:
    """
    Returns relevant content as a string from a text-based manual about simulation modeling procedures and guidelines based on the given query. Asking about one topic at a time helps extract more relevant content.
    """
    retriever = get_manual_retriever()
    retrieved_docs = retriever.invoke(query)
    result_chunks = []
    for doc in retrieved_docs:
        source = doc.metadata.get("source", "Unknown")
        header1 = doc.metadata.get("Header 1", "")
        header2 = doc.metadata.get("Header 2", "")
        content = doc.page_content.strip()
        result_chunks.append(
            f"[Source: {os.path.basename(source)}, Header 1: {header1}, Header 2: {header2}]\n{content}"
        )
    return "\n\n".join(result_chunks)


def get_manual_toc():
    manual_path = Path(config["paths"]["manual"])
    md_files = [f for f in manual_path.glob("*.md") if f.is_file()]
    md_file = md_files[0]

    with open(md_file, 'r', encoding='utf-8') as file:
        lines = file.readlines()
    
    toc_lines = []
    for line in lines:
        line = line.strip()
        if line.startswith('# '):
            # H1 제목 (대분류)
            title = line[2:].strip()
            toc_lines.append(f"H1: {title}")
        elif line.startswith('## '):
            # H2 제목 (중분류)
            title = line[3:].strip()
            toc_lines.append(f"  H2: {title}")

    toc = "ECO2-OD Modeling Manual - Table of Contents\n"
    toc += "\n".join(toc_lines)
    
    return toc


def build_manual_analyzer_agent():
    llm = get_llm_model("manual_analyzer")
    tools = [manual_retriever]
    manual_toc = get_manual_toc()

    agent_executor  = create_react_agent(
        model=llm.bind_tools(tools, parallel_tool_calls=False),
        tools=tools,
        prompt=MANUAL_ANALYZER_SYSTEM_PROMPT.format(manual_toc=manual_toc),
    )

    return agent_executor


def manual_analyzer_node(state: AgentState) -> Dict[str, Any]:
    agent_executor = build_manual_analyzer_agent()

    current_task = state.get("next_task", "")
    reasoning = state.get("step_results", [])[-1].get("reasoning")
    
    prompt_message = SUBAGENT_PROMPT.format(
        reasoning=reasoning,
        current_task=current_task
    )

    response = invoke_llm_with_retry(
        agent_executor, 
        {"messages": [HumanMessage(content=prompt_message)]}, 
        operation_name=f"Manual Analyzer LLM ({config['llm']['manual_analyzer']['model']})"
    )

    step_result = StepResult(
        agent="manual_analyzer",
        reasoning="-",
        task=current_task,
        result=response['messages'][-1].content,
    )

    message = [AIMessage(content=step_result['result'], name="manual_analyzer")]

    return {
        "step_results": [step_result],
        "messages": message
    }


# graph = StateGraph(AgentState)
# graph.add_node("manual_analyzer", manual_analyzer_node)
# graph.add_edge(START, "manual_analyzer")
# graph.add_edge("manual_analyzer", END)
# agent_graph = graph.compile()