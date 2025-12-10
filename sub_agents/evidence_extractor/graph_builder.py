from utils.prompt import EVIDENCE_EXTRACTOR_SYSTEM_PROMPT, IMAGE_ANALYZER_SYSTEM_PROMPT, SUBAGENT_PROMPT
from langgraph.prebuilt import create_react_agent
from utils import get_llm_model, config, invoke_llm_with_retry, image_list, pdf_metadata
from pathlib import Path
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyMuPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from typing import Annotated, Union
from langchain_core.tools import tool
import pandas as pd
import os
from langchain_core.messages import SystemMessage, HumanMessage
from typing import List, Dict, Any
import base64
from main_graph.graph_states import AgentState, StepResult
from pydantic import Field, BaseModel
from langchain_core.messages import AIMessage
from langgraph.graph import StateGraph, START, END
import yaml
from datetime import datetime


class SimpleImageMemory:
    def __init__(self, memory_file: str = config['image_db']['directory']):
        self.memory_file = Path(memory_file)
        self.memory_file.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_memory_file()
    
    def _ensure_memory_file(self):
        """메모리 파일이 없으면 빈 파일 생성"""
        if not self.memory_file.exists():
            self.save_memory({})
    
    def load_memory(self) -> Dict[str, List[Dict[str, str]]]:
        """메모리 파일에서 데이터 로드"""
        try:
            with open(self.memory_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"메모리 로드 실패: {e}")
            return {}
    
    def save_memory(self, memory_data: Dict[str, List[Dict[str, str]]]):
        """메모리 데이터를 파일에 저장"""
        try:
            with open(self.memory_file, 'w', encoding='utf-8') as f:
                yaml.dump(memory_data, f, allow_unicode=True, indent=2, sort_keys=True, default_style='|')
        except Exception as e:
            print(f"메모리 저장 실패: {e}")
    
    def add_knowledge(self, image_label: str, query: str, response: str):
        """새로운 지식 추가 (query-response 쌍으로 저장)"""
        memory = self.load_memory()
        if image_label not in memory:
            memory[image_label] = []
        
        # query-response 쌍을 리스트에 추가
        memory[image_label].append({
            'query': query,
            'response': response
        })
        self.save_memory(memory)
    
    def get_all_knowledge(self) -> Dict[str, List[Dict[str, str]]]:
        """모든 지식 반환"""
        return self.load_memory()


# 전역 메모리 인스턴스
image_memory = SimpleImageMemory()


def build_pdf_vectordb(force_rebuild: bool = False) -> None:
    pdfs_path = Path(config["paths"]["user_pdfs"])
    faiss_index_path = Path(config["vector_db"]["pdf"]["persist_directory"])
    
    # 디렉토리 생성
    faiss_index_path.mkdir(parents=True, exist_ok=True)
    
    if force_rebuild or not (faiss_index_path / "index.faiss").exists():
        print("pdf 문서 벡터 데이터베이스를 새로 구축합니다...")
        
        # PDF 파일 목록 가져오기
        pdf_files = [f for f in pdfs_path.glob("*.pdf") if f.is_file()]
        
        if not pdf_files:
            print(f"경고: {pdfs_path}에서 PDF 파일을 찾을 수 없습니다.")
            return
        
        print(f"처리할 PDF 파일 수: {len(pdf_files)}")
        
        # 문서 로드
        documents = []
        for pdf_file in pdf_files:
            print(f"로딩 중: {pdf_file.name}")
            loader = PyMuPDFLoader(str(pdf_file))
            documents.extend(loader.load())
        
        print(f"총 {len(documents)}개의 문서를 로드했습니다.")
        
        # 텍스트 분할
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.get("vector_db", {}).get("pdf", {}).get("chunk_size", 1000),
            chunk_overlap=config.get("vector_db", {}).get("pdf", {}).get("chunk_overlap", 200)
        )
        splits = text_splitter.split_documents(documents)
        print(f"문서를 {len(splits)}개의 청크로 분할했습니다.")
        
        # 임베딩 생성 및 벡터스토어 구축
        print("임베딩 생성 및 벡터스토어 구축 중...")
        embeddings = OpenAIEmbeddings(model=config["embedding"]["model"])
        vectorstore = FAISS.from_documents(splits, embeddings)
        
        # 인덱스 저장
        vectorstore.save_local(folder_path=faiss_index_path)
        print(f"PDF 문서의 벡터 데이터베이스가 {faiss_index_path}에 저장되었습니다.")
    else:
        print("기존 pdf 문서 벡터 데이터베이스를 사용합니다.")


def get_pdf_retriever():
    try:
        faiss_index_path = Path(config["vector_db"]["pdf"]["persist_directory"])
        
        if not (faiss_index_path / "index.faiss").exists():
            print("PDF 문서 벡터 DB가 존재하지 않습니다. 벡터DB를 생성합니다...")
            build_pdf_vectordb()
        
        embeddings = OpenAIEmbeddings(model=config["embedding"]["model"])
        vectorstore = FAISS.load_local(str(faiss_index_path), embeddings, allow_dangerous_deserialization=True)
        return vectorstore.as_retriever(search_kwargs={"k": config["retriever"]["pdf"]["top_k"]})
        
    except Exception as e:
        print(f"벡터스토어 로드 중 오류 발생: {e}")
        return None


@tool
def pdf_retriever(
    query: Annotated[str, "Content to search for in law. Since the search is based on vector similarity, briefly mention the core content you're looking for, focusing on keywords."]
) -> str:
    """
    Returns content related to a given query from text-based PDF legal documents as a string.
    """
    retriever = get_pdf_retriever()
    retrieved_docs = retriever.invoke(query)
    result_chunks = []
    for doc in retrieved_docs:
        source = doc.metadata.get("source", "Unknown")
        page = doc.metadata.get("page", "Unknown")
        content = doc.page_content.strip()
        result_chunks.append(
            f"[Source: {os.path.basename(source)}, Page: {page+1}]\n{content}"
        )
    return "\n\n".join(result_chunks)


@tool
def calculator(
    expression: Annotated[str, 'Python expression string to calculate (e.g., "0.21 < 0.25", "3 * (4 + 5)")']
) -> str:
    """
    Performs accurate mathematical calculations using Python. Returns the result as a string (e.g., "True", "27").
    """
    try:
        allowed_names = {"__builtins__": {}}
        result = eval(expression, allowed_names)
        return str(result)
    except Exception as e:
        return f"Calculation error: {e}"


# 이미지를 base64로 인코딩하는 함수 (파일)
def encode_image_from_file(image_path):
    with open(image_path, "rb") as image_file:
        image_content = image_file.read()
        file_ext = os.path.splitext(image_path)[1].lower()
        if file_ext in [".jpg", ".jpeg"]:
            mime_type = "image/jpeg"
        elif file_ext == ".png":
            mime_type = "image/png"
        else:
            mime_type = "image/unknown"
        return f"data:{mime_type};base64,{base64.b64encode(image_content).decode('utf-8')}"


@tool
def image_analyzer(
    label: Annotated[str, "Image filename to be analyzed. Must exactly match one of the available image files. (e.g., 'Architecture_Building_Overview.png')"],
    query: Annotated[str, "Query for analysis of the image. **Must not require calculations, and should only request objective information extraction from the given materials**."]
) -> str:
    """
    Analyzes the 'image' with the specified label and returns analysis results for the given query.
    This tool uses a multimodal LLM to analyze visual information within images.
    Returns a text description of the image analysis results or an error message as a str.
    **Note**: this tool lacks contextual information about the current task and foundational knowledge about modeling programs. Therefore, providing baseline contextual information when requesting information can yield more accurate responses.
    """

    # label에 해당하는 이미지 경로 찾기
    if label not in image_list:
        return f"Error: Could not find image '{label}' in available images: {image_list[:5]}..."
    
    images_dir = Path(config["paths"]["images_dir"])
    doc_path = images_dir / label

    image_resolution = config["llm"]["image_analyzer"]["image_resolution"]
    if image_resolution == "high":
        image_request = {"type": "image_url", "image_url": {"url": f"{encode_image_from_file(doc_path)}", "detail": "high"}} # high 옵션
    elif image_resolution == "auto":
        image_request = {"type": "image_url", "image_url": {"url": f"{encode_image_from_file(doc_path)}"}} # auto 옵션
    else:
        image_request = {"type": "image_url", "image_url": {"url": f"{encode_image_from_file(doc_path)}"}} # auto 옵션

    try:
        messages = [
            SystemMessage(content=IMAGE_ANALYZER_SYSTEM_PROMPT),
            HumanMessage(content=[
                {"type": "text", "text": query},
                image_request
            ])
        ]
        llm = get_llm_model("image_analyzer")
        response = invoke_llm_with_retry(
            llm, 
            messages, 
            operation_name=f"Image Analyzer LLM ({config['llm']['image_analyzer']['model']})"
        )
        
        # 자동으로 메모리에 저장 (query와 response를 별도로 저장)
        image_memory.add_knowledge(label, query, response.content)
        
        return response.content
    except Exception as e:
        return f"Error occurred during image analysis: {e}"


# update_image_memory 도구 제거 - image_analyzer가 자동으로 메모리에 저장하므로 불필요


def get_memory_context() -> str:
    """메모리 내용을 프롬프트용으로 포맷"""
    try:
        knowledge = image_memory.get_all_knowledge()
        
        if not knowledge:
            return "Not added yet"
        
        memory_context = ""
        for image_label, qa_pairs in knowledge.items():
            memory_context += f"<{image_label}>\n"
            for qa in qa_pairs:
                memory_context += f"<query>\n{qa['query']}\n</query>\n"
                memory_context += f"<response>\n{qa['response']}\n</response>\n"
            memory_context += f"</{image_label}>\n"
        
        return memory_context.strip()
        
    except Exception as e:
        return f"Memory retrieval error: {e}"


def build_evidence_extractor_agent():
    llm = get_llm_model("evidence_extractor")
    tools = [pdf_retriever, image_analyzer, calculator]
    
    # 이미지 파일 리스트를 프롬프트에 포함 (간단한 파일명만)
    image_files_info = "\n".join([f"- {filename}" for filename in image_list])
    
    # PDF 메타데이터 정보를 프롬프트에 포함
    pdf_metadata_info = "\n".join([f"- {pdf_name}" for pdf_name in pdf_metadata])
    
    # 메모리 내용 자동 주입
    memory_context = get_memory_context()
    
    formatted_prompt = EVIDENCE_EXTRACTOR_SYSTEM_PROMPT.format(
        image_files_info=image_files_info,
        pdf_metadata_info=pdf_metadata_info,
        memory_context=memory_context
    )

    agent_executor  = create_react_agent(
        model=llm.bind_tools(tools, parallel_tool_calls=False),
        tools=tools,
        prompt=formatted_prompt,
    )

    return agent_executor


def evidence_extractor_node(state: AgentState) -> Dict[str, Any]:
    agent_executor = build_evidence_extractor_agent()

    current_task = state.get("next_task", "")
    reasoning = state.get("step_results", [])[-1].get("reasoning")
    
    prompt_message = SUBAGENT_PROMPT.format(
        reasoning=reasoning,
        current_task=current_task
    )

    response = invoke_llm_with_retry(
        agent_executor, 
        {"messages": [HumanMessage(content=prompt_message)]}, 
        operation_name=f"Evidence Extractor LLM ({config['llm']['evidence_extractor']['model']})"
    )

    step_result = StepResult(
        agent="evidence_extractor",
        reasoning="-",
        task=current_task,
        result=response['messages'][-1].content,
    )

    message = [AIMessage(content=step_result['result'], name="evidence_extractor")]

    return {
        "step_results": [step_result],
        "messages": message
    }

## test
# graph = StateGraph(AgentState)
# graph.add_node("evidence_extractor", evidence_extractor_node)
# graph.add_edge(START, "evidence_extractor")
# graph.add_edge("evidence_extractor", END)
# agent_graph = graph.compile()