import uuid
import yaml
import os
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv
from langgraph.graph.state import CompiledStateGraph
from langchain_core.runnables import RunnableConfig
from typing import Callable
from langchain_core.messages import BaseMessage
import pandas as pd
from os import getenv
import time
import re


# --- LangSmith 로깅 설정 ---
def logging_langsmith(project_name=None, set_enable=True):
    if set_enable:
        langchain_key = os.environ.get("LANGCHAIN_API_KEY", "")
        langsmith_key = os.environ.get("LANGSMITH_API_KEY", "")
        # 더 긴 API 키 선택
        if len(langchain_key.strip()) >= len(langsmith_key.strip()):
            result = langchain_key
        else:
            result = langsmith_key
        if result.strip() == "":
            print(
                "LangChain/LangSmith API Key가 설정되지 않았습니다. 참고: https://wikidocs.net/250954"
            )
            return
        os.environ["LANGSMITH_ENDPOINT"] = (
            "https://api.smith.langchain.com"  # LangSmith API 엔드포인트
        )
        os.environ["LANGSMITH_TRACING"] = "true"  # true: 활성화
        os.environ["LANGSMITH_PROJECT"] = project_name  # 프로젝트명
        print(f"LangSmith 추적을 시작합니다.\n[프로젝트명]\n{project_name}")
    else:
        os.environ["LANGSMITH_TRACING"] = "false"  # false: 비활성화
        print("LangSmith 추적을 하지 않습니다.")


def get_llm_model(agent_name):
    """
    Get LLM model for a specific agent.
    Automatically gets model name and temperature from config.
    Only passes temperature parameter if it exists in config.
    
    Args:
        agent_name: Name of the agent (e.g., "supervisor", "report_writer", etc.)
    """
    from utils import config
    
    # Get model configuration from config
    if agent_name not in config.get("llm", {}):
        raise ValueError(f"Agent '{agent_name}' not found in config['llm']")
    
    model_name = config["llm"][agent_name]["model"]
    # Check if temperature exists in config
    has_temperature = "temperature" in config["llm"][agent_name]
    temperature = config["llm"][agent_name].get("temperature") if has_temperature else None
    
    # Create the LLM instance based on model type
    if model_name.startswith("gpt"):
        from langchain_openai import ChatOpenAI
        if has_temperature:
            llm = ChatOpenAI(model=model_name, temperature=temperature)
        else:
            llm = ChatOpenAI(model=model_name)
    elif model_name.startswith("gemini"):
        from langchain_google_genai import ChatGoogleGenerativeAI
        if has_temperature:
            llm = ChatGoogleGenerativeAI(model=model_name, temperature=temperature)
        else:
            llm = ChatGoogleGenerativeAI(model=model_name)
    elif model_name.startswith("claude"):
        from langchain_anthropic import ChatAnthropic
        if has_temperature:
            llm = ChatAnthropic(model=model_name, temperature=temperature)
        else:
            llm = ChatAnthropic(model=model_name)
    elif model_name.startswith("openrouter"):
        from langchain_openai import ChatOpenAI
        if has_temperature:
            llm = ChatOpenAI(
                    api_key=getenv("OPENROUTER_API_KEY"),
                    base_url=getenv("OPENROUTER_BASE_URL"),
                    model=model_name[11:],
                    temperature=temperature,
                    extra_body={
                        "provider": {
                            # 'require_parameters': True,
                            # 'data_collection': 'deny' # 'allow' or 'deny'
                        }
                    }
                )
        else:
            llm = ChatOpenAI(
                    api_key=getenv("OPENROUTER_API_KEY"),
                    base_url=getenv("OPENROUTER_BASE_URL"),
                    model=model_name[11:],
                    extra_body={
                        "provider": {
                            # 'require_parameters': True,
                            # 'data_collection': 'deny' # 'allow' or 'deny'
                        }
                    }
                )
    else:
        raise ValueError(f"Unsupported model: {model_name}")
    return llm

def get_openrouter_status():
    import requests
    import json
    response = requests.get(
        url="https://openrouter.ai/api/v1/key",
        headers={
            "Authorization": f"Bearer {getenv('OPENROUTER_API_KEY')}"
        }
    )
    return json.dumps(response.json()['data'], indent=2)

def get_openrouter_credits():
    import requests
    import json
    from os import getenv
    response = requests.get(
        url="https://openrouter.ai/api/v1/credits",
        headers={
            "Authorization": f"Bearer {getenv('OPENROUTER_API_KEY')}"
        }
    )

    return response.json()['data']

def ansi_to_html(text):
    """ANSI 색상 코드를 HTML로 변환"""
    # ANSI 색상 코드 매핑
    ansi_colors = {
        '30': 'black', '31': 'red', '32': 'green', '33': '#00ff00',
        '34': 'blue', '35': 'magenta', '36': '#00ffff', '37': 'white',
        '90': 'gray', '91': '#ff6b6b', '92': '#4ecdc4', '93': '#ffe66d',
        '94': '#74b9ff', '95': '#fd79a8', '96': '#00cec9', '97': '#ddd'
    }
    
    # HTML 특수 문자 이스케이프
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # ANSI 색상 코드를 HTML span 태그로 변환 (순서 중요!)
    # \033[0m 형태 (리셋) - 먼저 처리
    text = re.sub(r'\033\[0m', '</span>', text)
    # \033[1;36m 형태 (굵은 색상)
    text = re.sub(r'\033\[1;(\d+)m', lambda m: f'<span style="color: {ansi_colors.get(m.group(1), "inherit")}; font-weight: bold;">', text)
    # \033[36m 형태 (일반 색상)
    text = re.sub(r'\033\[(\d+)m', lambda m: f'<span style="color: {ansi_colors.get(m.group(1), "inherit")};">', text)
    
    # 줄바꿈을 <br>로 변환
    text = text.replace('\n', '<br>\n')
    
    return text


class TeeOutput:
    """콘솔과 HTML 파일에 동시에 출력하는 클래스"""
    def __init__(self, console, file_handle):
        self.console = console
        self.file = file_handle
        # HTML 헤더 작성
        self.file.write('''<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Debug Log</title>
    <style>
        body { 
            font-family: 'Consolas', 'Monaco', monospace; 
            background-color: #1e1e1e; 
            color: #d4d4d4; 
            padding: 20px;
            white-space: pre-wrap;
            line-height: 1.4;
        }
        .log-container {
            background-color: #2d2d2d;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #404040;
        }
    </style>
</head>
<body>
<div class="log-container">
''')
        self.file.flush()
    
    def write(self, message):
        self.console.write(message)
        # ANSI 코드를 HTML로 변환해서 파일에 쓰기
        html_message = ansi_to_html(message)
        self.file.write(html_message)
        self.file.flush()
    
    def flush(self):
        self.console.flush()
        self.file.flush()
    
    def close(self):
        # HTML 푸터 작성
        self.file.write('</div>\n</body>\n</html>')
        self.file.flush()
        self.file.close()


def invoke_llm_with_retry(model, inputs, max_retries=5, operation_name="LLM"):
    """
    LLM 호출을 재시도 로직과 함께 실행합니다.
    응답이 None인 경우나 JSON 파싱 에러가 발생한 경우 재시도합니다.
    
    Args:
        model: LLM 모델 객체
        inputs: 모델에 전달할 입력
        max_retries: 최대 재시도 횟수 (기본값: 5)
        operation_name: 디버깅용 operation 이름
    
    Returns:
        LLM 응답
    
    Raises:
        ValueError: 응답이 None인 상태로 모든 재시도가 실패한 경우
        Exception: API 호출 중 발생한 다른 모든 예외
    """
    for attempt in range(max_retries):
        try:
            print(f"[DEBUG] Calling {operation_name} (attempt {attempt + 1}/{max_retries})")
            response = model.invoke(inputs)
            print(f"[DEBUG] {operation_name} response type: {type(response)}")
            
            if response is not None:
                print(f"[DEBUG] {operation_name} response successful")
                return response
            else:
                print(f"[WARNING] {operation_name} response is None (attempt {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff
                    continue
                
        except Exception as e:
            # JSON 파싱 에러나 Invalid Tool Calls 에러 처리
            error_message = str(e).lower()
            if "json" in error_message or "invalid tool calls" in error_message or "jsondecodeerror" in error_message:
                print(f"[WARNING] {operation_name} JSON parsing error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)  # exponential backoff
                    # 동일한 요청을 그대로 재시도 (수정 없이)
                    continue
                else:
                    # 최대 재시도 후 에러 발생
                    print(f"[ERROR] {operation_name} failed after {max_retries} attempts due to JSON parsing error")
                    raise e
            else:
                # None 응답이 아닌 다른 예외는 즉시 발생시킴
                print(f"[ERROR] {operation_name} invoke failed with exception: {e}")
                raise e

    # 모든 재시도 후에도 response가 None인 경우 에러 발생
    raise ValueError(f"{operation_name} response is None after {max_retries} attempts. API 호출이 계속 실패합니다.")


def load_environment() -> None:
    load_dotenv()
    print("환경변수(.env)가 로드되었습니다.")


def new_uuid() -> str:
    return str(uuid.uuid4())


def load_config() -> Dict[str, Any]:
    config_path = Path("config.yaml")
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)
    return config


def load_image_list(config: Dict[str, Any]) -> List[str]:
    """
    이미지 파일명 리스트를 로드하는 함수
    
    Args:
        config: 설정 딕셔너리
        
    Returns:
        이미지 파일명 리스트
    """
    image_files = []
    try:
        images_dir = Path(config["paths"]["images_dir"])
        # 이미지 파일 확장자들
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff']
        
        for ext in image_extensions:
            image_files.extend([f.name for f in images_dir.glob(f"*{ext}") if f.is_file()])
            image_files.extend([f.name for f in images_dir.glob(f"*{ext.upper()}") if f.is_file()])
        
        image_files = list(set(image_files))  # 중복 제거
        image_files.sort()  # 정렬
        
        print(f"이미지 파일 로드 완료: {len(image_files)}개 이미지")
    except Exception as e:
        print(f"이미지 파일 로드 중 오류 발생: {e}")
    
    return image_files


def load_pdf_metadata(config: Dict[str, Any]) -> List[str]:
    """
    PDF 메타데이터를 로드하는 함수
    
    Args:
        config: 설정 딕셔너리
        
    Returns:
        PDF 파일명 리스트
    """
    pdf_metadata = []
    try:
        pdfs_dir = Path(config["paths"]["user_pdfs"])
        if pdfs_dir.exists():
            pdf_files = list(pdfs_dir.glob("*.pdf"))
            for pdf_file in pdf_files:
                pdf_metadata.append(pdf_file.name)
            print(f"PDF 메타데이터 로드 완료: {len(pdf_metadata)}개 PDF")
        else:
            print(f"PDF 디렉토리가 존재하지 않습니다: {pdfs_dir}")
    except Exception as e:
        print(f"PDF 메타데이터 로드 중 오류 발생: {e}")
    
    return pdf_metadata


# ========= ecl2 모델 파싱 관련 함수 =========

import xmltodict
import pandas as pd


def parse_xml(file_path):
    """
    XML 파일을 읽어 dict of DataFrame으로 변환합니다.
    내부적으로 xmltodict, pandas를 사용하며 다양한 XML 헤더/구조에 대응합니다.
    """
    with open(file_path, "rb") as f:
        lines = f.readlines()

    try:
        xml = "<root>" + b"".join(lines[1:-[idx for idx in range(90,130) if lines[-idx][:5] == b'</DS>'][0]]).decode("utf-8") + "</root>"
        doc = xmltodict.parse(xml)["root"]
    except:
        try:
            xml = "<root>" + b"".join(lines[2:-[idx for idx in range(90,130) if lines[-idx][:5] == b'</DS>'][0]]).decode("utf-8") + "</root>"
            doc = xmltodict.parse(xml)["root"]
        except:
            xml = "<root>" + b"".join(lines[3:-[idx for idx in range(90,130) if lines[-idx][:5] == b'</DS>'][0]]).decode("utf-8") + "</root>"
            doc = xmltodict.parse(xml)["root"]
    
    df_dict = {}
    for key in doc.keys():
        try:
            df = pd.DataFrame(doc[key])
        except ValueError as e:
            if str(e).strip() == "If using all scalar values, you must pass an index":
                df = pd.DataFrame(doc[key], index=[0])
            else:
                print(f"Error : filename - {key}")
        df_dict[key] = df
    return df_dict


def parse_eco2od(file_path, model_ontology):
    """
    ECO2OD dict of DataFrame 파일을 DataFrame(dict)으로 구조화하고, 섹션별 컬럼 매핑 및 후처리를 수행합니다.
    반환값은 {섹션명: DataFrame} dict입니다.
    """
    df_dict = parse_xml(file_path)

    model_data = {}

    section_name = "건축부문_외피_형별성능내역"
    df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
    df_tmp.columns = list(model_ontology[section_name]['columns'].values())
    df_tmp = df_tmp[df_tmp['설명'] != '(없음)'].reset_index(drop=True)

    # 부위 코드를 실제 부위 이름으로 변환
    code_dict = df_dict['tbl_common_od'][df_dict['tbl_common_od']['gubun'] == '1088']
    df_tmp['부위'] = df_tmp['부위'].apply(lambda x: code_dict[code_dict['code'] == x]['name'].values[0])

    # 창 또는 문이 포함되지 않은 부위의 창호열관류율, 일사에너지투과율을 '해당없음'으로 변경
    mask = ~df_tmp['부위'].str.contains('창|문', na=False)
    df_tmp.loc[mask, ['창호열관류율', '일사에너지투과율(-)']] = '해당없음'

    model_data[section_name] = df_tmp


    section_name = "건축부문_외피_형별성능내역_재료"
    df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
    df_tmp.columns = list(model_ontology[section_name]['columns'].values())
    df_tmp = df_tmp.reset_index(drop=True)

    # 재료명에 '열전달저항'이 포함된 행의 열전도율과 두께를 '해당없음'으로 변경
    mask = df_tmp['재료명'].str.contains('열전달저항', na=False)
    df_tmp.loc[mask, ['열전도율(W/mK)', '두께(mm)']] = '해당없음'

    # 형별성능내역별로 구분하여 처리
    processed_groups = []
    
    # 형별성능내역별로 그룹화
    for pcode, group in df_tmp.groupby('형별성능내역'):
        # 먼저 matching_row가 있는지 확인
        matching_row = model_data["건축부문_외피_형별성능내역"][model_data["건축부문_외피_형별성능내역"]['code'] == pcode]
        
        # matching_row가 있는 경우에만 처리
        if not matching_row.empty:
            # 형별성능내역 구성 순번으로 정렬
            group_sorted = group.sort_values('형별성능내역 구성 순번').copy()
            
            # 번호를 1부터 순차적으로 다시 매핑
            group_sorted['형별성능내역 구성 순번'] = range(1, len(group_sorted) + 1)
            
            # 형별성능내역을 code에서 이름으로 변경
            group_sorted['형별성능내역'] = matching_row['설명'].iloc[0]
            processed_groups.append(group_sorted)
        # matching_row가 없는 경우 해당 그룹은 제거 (아무 작업하지 않음)
    
    # 처리된 그룹들을 다시 합치기
    if processed_groups:
        df_tmp = pd.concat(processed_groups, ignore_index=True)
    else:
        df_tmp = pd.DataFrame(columns=df_tmp.columns)

    model_data[section_name] = df_tmp


    section_name = "건축부문_외피"
    df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
    df_tmp.columns = list(model_ontology[section_name]['columns'].values())
    df_tmp = df_tmp[df_tmp['설명'] != '(없음)'].reset_index(drop=True)

    # 부위에 문 또는 창이 포함되지 않은 경우 수평/수직차양각을 해당없음으로 변경
    mask = ~df_tmp['부위'].str.contains('문|창', na=False)
    df_tmp[['수평차양각(°)', '수직차양각(°)']] = df_tmp[['수평차양각(°)', '수직차양각(°)']].astype('object')
    df_tmp.loc[mask, ['수평차양각(°)', '수직차양각(°)']] = '해당없음'

    df_tmp = df_tmp.drop('부위', axis=1)

    # 형별성능내역을 code에서 이름으로 변경
    for idx, row in df_tmp.iterrows():
        pcode = row['형별성능내역']
        matching_row = model_data["건축부문_외피_형별성능내역"][model_data["건축부문_외피_형별성능내역"]['code'] == pcode].copy()
        df_tmp.at[idx, '형별성능내역'] = matching_row['설명'].iloc[0]

    model_data[section_name] = df_tmp


    section_name = "설비부문_공조기기"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp[df_tmp['설명'] != '(없음)'].reset_index(drop=True)

        # 공조방식이 환기용인 경우 난방급기온도(°C)와 냉방급기온도(°C)를 해당없음으로 변경
        mask = df_tmp['공조방식'].str.contains('환기용', na=False)
        df_tmp.loc[mask, ['난방급기온도(°C)', '냉방급기온도(°C)']] = '해당없음'

        # 열교환기유형이 열회수불가인 경우 난방열회수율(%)와 냉방열회수율(%)를 해당없음으로 변경
        mask = df_tmp['열교환기유형'].str.contains('열회수불가', na=False)
        df_tmp.loc[mask, ['난방열회수율(%)', '냉방열회수율(%)']] = '해당없음'
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp


    section_name = "설비부문_조명기기"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp.reset_index(drop=True)
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp


    section_name = "설비부문_실내단말기"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp.reset_index(drop=True)
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp


    section_name = "건축부문_층별개요"
    df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
    df_tmp.columns = list(model_ontology[section_name]['columns'].values())
    df_tmp = df_tmp.reset_index(drop=True)

    # 허가용도 코드를 실제 허가용도 이름으로 변환
    df_tmp['허가용도'] = df_tmp['허가용도'].apply(lambda x: df_dict['tbl_profile_od'][df_dict['tbl_profile_od']['code'] == x]['설명'].values[0])

    model_data[section_name] = df_tmp


    section_name = "건축부문_기본개요"
    df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
    df_tmp.columns = list(model_ontology[section_name]['columns'].values())
    df_tmp = df_tmp.reset_index(drop=True)

    model_data[section_name] = df_tmp


    section_name = "일반부문"
    df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
    df_tmp.columns = list(model_ontology[section_name]['columns'].values())
    df_tmp = df_tmp.reset_index(drop=True)
    df_tmp['공공민간구분'] = df_tmp['공공민간구분'].map({'1': '공공', '0': '민간'})

    # 지역 코드를 실제 지역 이름으로 변환
    df_dict['weather_group']['지역명'] = df_dict['weather_group']['area'] + '_' + df_dict['weather_group']['name']
    df_tmp['지역'] = df_tmp['지역'].apply(lambda x: df_dict['weather_group'][df_dict['weather_group']['code'] == x]['지역명'].values[0])

    model_data[section_name] = df_tmp


    section_name = "신재생에너지설비부문_태양광"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp.reset_index(drop=True)
        #  모듈종류가 성능치입력이 아닌 경우 모듈효울 해당없음으로 변경
        mask = ~df_tmp['모듈종류'].str.contains('성능치입력', na=False)
        df_tmp.loc[mask, ['모듈효율(%)']] = '해당없음'
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp


    section_name = "신재생에너지설비부문_태양열"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp.reset_index(drop=True)

        # 집열기유형이 성능치입력이 아닌 경우 집열효율을 해당없음으로 변경
        mask = ~df_tmp['집열기유형'].str.contains('성능치입력', na=False)
        df_tmp.loc[mask, ['집열효율(-)']] = '해당없음'
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp


    section_name = "신재생에너지설비부문_지열"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp.reset_index(drop=True)
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp


    section_name = "신재생에너지설비부문_열병합발전"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp.reset_index(drop=True)
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp


    section_name = "기계설비부문_난방기기"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp[df_tmp['설명'] != '(없음)'].reset_index(drop=True)

        df_tmp['연결된신재생'] = df_tmp['연결된신재생'].replace('0', '없음')

        # 연결된신재생 코드를 실제 이름으로 변환
        df_tmp['연결된신재생'] = df_tmp['연결된신재생'].apply(lambda x: '없음' if x == '없음' else df_dict['tbl_new'][df_dict['tbl_new']['code'] == x]['설명'].values[0])

        # 난방방식이 보일러, 지역난방, 전기보일러인 경우 성적계수(COP)를 해당없음으로 변경
        mask = df_tmp['난방방식'].isin(['보일러', '지역난방', '전기보일러'])
        df_tmp.loc[mask, '성적계수(COP)'] = '해당없음'

        # 난방방식이 히트펌프, 지역난방인 경우 기기효율(%)을 해당없음으로 변경
        mask = df_tmp['난방방식'].isin(['히트펌프', '지역난방'])
        df_tmp.loc[mask, '기기효율(%)'] = '해당없음'
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp


    section_name = "기계설비부문_냉방기기"
    if model_ontology[section_name]['key'] in df_dict.keys():
        df_tmp = df_dict[model_ontology[section_name]['key']][list(model_ontology[section_name]['columns'].keys())]
        df_tmp.columns = list(model_ontology[section_name]['columns'].values())
        df_tmp = df_tmp[df_tmp['설명'] != '(없음)'].reset_index(drop=True)

        df_tmp['연결된신재생'] = df_tmp['연결된신재생'].replace('0', '없음')

        # 연결된신재생 코드를 실제 이름으로 변환
        df_tmp['연결된신재생'] = df_tmp['연결된신재생'].apply(lambda x: '없음' if x == '없음' else df_dict['tbl_new'][df_dict['tbl_new']['code'] == x]['설명'].values[0])

        # 냉동기 종류가 히트펌프인 경우 냉각탑종류, 냉각수펌프동력을 해당없음으로 변경
        mask = df_tmp['냉동기종류'] == '히트펌프'
        df_tmp.loc[mask, '냉각탑종류'] = '해당없음'
        df_tmp.loc[mask, '냉각수펌프동력'] = '해당없음'

        # 냉방방식이 흡수식인 경우 냉동기종류를 해당없음으로 변경
        mask = df_tmp['냉방방식'] == '흡수식'
        df_tmp.loc[mask, '냉동기종류'] = '해당없음'
    else:
        df_tmp = pd.DataFrame(columns=list(model_ontology[section_name]['columns'].values()))

    model_data[section_name] = df_tmp

    for key in model_data.keys():
        if 'code' in model_data[key].columns:
            model_data[key] = model_data[key].drop('code', axis=1)

    return model_data


# def get_ontology_description(model_ontology):
#     section_columns = ""
#     for section, config in model_ontology.items():
#         columns = [col for col in config["columns"].values() if col != "code"]
#         section_columns += f"`{section}` dataframe's column headers: {', '.join(columns)}\n"
#     return section_columns


def invoke_graph(
    graph: CompiledStateGraph,
    inputs: dict,
    config: RunnableConfig,
    node_names: List[str] = [],
    callback: Callable = None,
):
    """
    LangGraph 앱의 실행 결과를 예쁘게 스트리밍하여 출력하는 함수입니다.
    출처: https://github.com/teddylee777/langchain-teddynote

    Args:
        graph (CompiledStateGraph): 실행할 컴파일된 LangGraph 객체
        inputs (dict): 그래프에 전달할 입력값 딕셔너리
        config (RunnableConfig): 실행 설정
        node_names (List[str], optional): 출력할 노드 이름 목록. 기본값은 빈 리스트
        callback (Callable, optional): 각 청크 처리를 위한 콜백 함수. 기본값은 None
            콜백 함수는 {"node": str, "content": str} 형태의 딕셔너리를 인자로 받습니다.
        log (bool, optional): True일 경우 print와 동시에 로그도 기록. 기본값은 False
        logger (Logger, optional): log=True일 때 사용할 로거 객체. 기본값은 None

    Returns:
        None: 함수는 스트리밍 결과를 출력만 하고 반환값은 없습니다.
    """

    def format_namespace(namespace):
        return namespace[-1].split(":")[0] if len(namespace) > 0 else "root graph"


    # subgraphs=True 를 통해 서브그래프의 출력도 포함
    for namespace, chunk in graph.stream(
        inputs, config, stream_mode="updates", subgraphs=True
    ):
        for node_name, node_chunk in chunk.items():
            # node_names가 비어있지 않은 경우에만 필터링
            if len(node_names) > 0 and node_name not in node_names:
                continue

            # 콜백 함수가 있는 경우 실행
            if callback is not None:
                callback({"node": node_name, "content": node_chunk})
            # 콜백이 없는 경우 기본 출력
            else:
                print("\n" + "=" * 50)
                formatted_namespace = format_namespace(namespace)
                if formatted_namespace == "root graph":
                    print(f"\n🔄 Node: \033[1;36m{node_name}\033[0m 🔄")
                else:
                    print(
                        f"\n🔄 Node: \033[1;36m{node_name}\033[0m in [\033[1;33m{formatted_namespace}\033[0m] 🔄"
                    )
                print("- " * 25)

                # 노드의 청크 데이터 출력
                if isinstance(node_chunk, dict):
                    for k, v in node_chunk.items():
                        if isinstance(v, BaseMessage):
                            v.pretty_print()
                        elif isinstance(v, list):
                            for list_item in v:
                                if isinstance(list_item, BaseMessage):
                                    list_item.pretty_print()
                                else:
                                    print(str(list_item))
                        elif isinstance(v, dict):
                            for node_chunk_key, node_chunk_value in node_chunk.items():
                                print(f"{node_chunk_key}:\n{node_chunk_value}")
                        else:
                            print(f"\033[1;32m{k}\033[0m:\n{v}")
                else:
                    if node_chunk is not None:
                        for item in node_chunk:
                            print(str(item))
                print("=" * 50)

def display_graph(graph: CompiledStateGraph):
    from PIL import Image
    import io
    png_bytes = graph.get_graph(xray=True).draw_mermaid_png()
    image = Image.open(io.BytesIO(png_bytes))
    image.show()


import requests

def bot_print(message):
    bot_token = getenv('BOT_TOKEN')
    chat_id = getenv('CHAT_ID')
    
    if not bot_token or not chat_id:
        print("Warning: BOT_TOKEN or CHAT_ID not found in environment variables")
        return
    
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage?chat_id={chat_id}&text={message}&parse_mode=HTML"
    requests.get(url)


def encode_image_from_file(image_path):
    """이미지를 base64로 인코딩"""
    import base64
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


class SimpleImageMemory:
    def __init__(self, memory_file: str = None):
        if memory_file is None:
            # Lazy load config when needed
            config = load_config()
            memory_file = config['image_db']['directory']
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


# 전역 메모리 인스턴스 (lazy loading)
_image_memory = None

def get_image_memory():
    """이미지 메모리 인스턴스를 반환 (lazy loading)"""
    global _image_memory
    if _image_memory is None:
        _image_memory = SimpleImageMemory()
    return _image_memory


def perform_initial_image_analysis(config: Dict[str, Any]) -> None:
    """
    메인 그래프 시작 전에 모든 이미지에 대해 초기 분석을 수행하고 image_memory에 저장
    
    Args:
        config: 설정 딕셔너리
    """
    from langchain_core.messages import SystemMessage, HumanMessage
    from utils.prompt import INITIAL_IMAGE_ANALYZER_PROMPT
    
    
    try:
        # 이미지 리스트 로드
        image_list = load_image_list(config)

        # LLM 모델 설정
        llm = get_llm_model("image_analyzer")
        
        images_dir = Path(config["paths"]["images_dir"])
        image_resolution = config["llm"]["image_analyzer"]["image_resolution"]
        
        print(f"초기 이미지 분석 시작 ({len(image_list)}개 이미지)")
        
        for i, image_filename in enumerate(image_list, 1):
            print(f"[{i}/{len(image_list)}] {image_filename} 분석 중...")
            
            try:
                # 이미지 경로
                image_path = images_dir / image_filename
                
                # 이미지 해상도 설정
                if image_resolution == "high":
                    image_request = {
                        "type": "image_url", 
                        "image_url": {
                            "url": f"{encode_image_from_file(image_path)}", 
                            "detail": "high"
                        }
                    }
                else:
                    image_request = {
                        "type": "image_url", 
                        "image_url": {
                            "url": f"{encode_image_from_file(image_path)}"
                        }
                    }
                
                # 메시지 생성
                messages = [
                    SystemMessage(content=INITIAL_IMAGE_ANALYZER_PROMPT),
                    HumanMessage(content=[
                        {"type": "text", "text": f"Analyze this architectural document: {image_filename}"},
                        image_request
                    ])
                ]
                
                # LLM 호출
                response = invoke_llm_with_retry(llm, messages, operation_name=f"Initial Image Analyze LLM ({config['llm']['image_analyzer']['model']})")
                
                # image_memory에 초기 분석 결과 저장
                get_image_memory().add_knowledge(image_filename, "describe about this image", response.content)
            except Exception as e:
                print(f"  → 분석 실패: {e}")
        
        print(f"초기 이미지 분석 결과를 {get_image_memory().memory_file}에 저장했습니다.")
            
    except Exception as e:
        print(f"초기 이미지 분석 중 오류 발생: {e}")