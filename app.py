import logging
import os
import sys
import shutil
from utils.utils import invoke_graph, logging_langsmith, get_openrouter_status, get_openrouter_credits, bot_print, perform_initial_image_analysis
from langgraph.types import RunnableConfig
from datetime import datetime
from utils.prompt import USER_PROMPT_TEMPLATE

from main_graph.graph_builder import build_main_graph
from main_graph import AgentState
from utils import new_uuid, config, TeeOutput


if __name__ == "__main__":
    # 프로그램 시작 시간 기록
    start_time = datetime.now()
    
    date_now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    print(f"\n시작시간: {date_now_str}\n")

    trace_id = date_now_str
    log_project_name = f"log_{trace_id}"
    
    # 로그 파일 설정
    log_dir = os.path.join(config['paths']['logs_dir'])
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = os.path.join(log_dir, f"{log_project_name}.html")
    
    # stdout을 파일과 콘솔에 동시 출력하도록 설정
    log_file = open(log_file_path, 'w', encoding='utf-8')
    original_stdout = sys.stdout
    tee_output = TeeOutput(original_stdout, log_file)
    
    try:
        sys.stdout = tee_output
        
        logging_langsmith(project_name=trace_id)

        print(" Config ".center(80, '='))
        print(f"pdf chunk size: {config['vector_db']['pdf']['chunk_size']}")
        print(f"pdf chunk overlap: {config['vector_db']['pdf']['chunk_overlap']}")
        print(f"embedding: {config['embedding']['model']}")
        print(f"retriever manual top_k: {config['retriever']['manual']['top_k']}")
        print(f"retriever pdf top_k: {config['retriever']['pdf']['top_k']}")
        print(f"supervisor LLM: {config['llm']['supervisor']['model']} (temperature={config['llm']['supervisor'].get('temperature', 'default')})")
        print(f"report_writer LLM: {config['llm']['report_writer']['model']} (temperature={config['llm']['report_writer'].get('temperature', 'default')})")
        print(f"evidence_extractor LLM: {config['llm']['evidence_extractor']['model']} (temperature={config['llm']['evidence_extractor'].get('temperature', 'default')})")
        print(f"manual_analyzer LLM: {config['llm']['manual_analyzer']['model']} (temperature={config['llm']['manual_analyzer'].get('temperature', 'default')})")
        print(f"model_inspector LLM: {config['llm']['model_inspector']['model']} (temperature={config['llm']['model_inspector'].get('temperature', 'default')})")
        print(f"image_analyzer LLM: {config['llm']['image_analyzer']['model']} (temperature={config['llm']['image_analyzer'].get('temperature', 'default')}, image quality={config['llm']['image_analyzer']['image_resolution']})")
        print("=" * 80)
        
        print(" OpenRouter key status ".center(80, '='))
        print(get_openrouter_status())
        credits = get_openrouter_credits()
        print(f"OpenRouter Credits: {credits['total_credits'] - credits['total_usage']}")
        print("=" * 80)

        print(" 초기 이미지 분석 ".center(80, '='))
        perform_initial_image_analysis(config)
        print("=" * 80)

        graph = build_main_graph()

        section_split = ["일반부문, 건축부문_층별개요, 건축부문_기본개요", "벽체, 지붕, 바닥", "창, 문", "기계설비부문_난방기기, 기계설비부문_냉방기기", "기계설비부문_공조기기, 기계설비부문_실내단말기", "기계설비부문_조명기기", "신재생에너지설비부문"]
        numbered_sections = "\n".join([f"{i+1}.{section}" for i, section in enumerate(section_split)])
        
        user_request = USER_PROMPT_TEMPLATE.format(numbered_sections=numbered_sections, review_part=section_split[0])  # 일반부문, 건축부문_층별개요, 건축부문_기본개요
        # user_request = USER_PROMPT_TEMPLATE.format(numbered_sections=numbered_sections, review_part=section_split[1])  # 벽체, 지붕, 바닥
        # user_request = USER_PROMPT_TEMPLATE.format(numbered_sections=numbered_sections, review_part=section_split[2])  # 창, 문
        # user_request = USER_PROMPT_TEMPLATE.format(numbered_sections=numbered_sections, review_part=section_split[3])  # 기계설비부문_난방기기, 기계설비부문_냉방기기
        # user_request = USER_PROMPT_TEMPLATE.format(numbered_sections=numbered_sections, review_part=section_split[4])  # 기계설비부문_공조기기, 기계설비부문_실내단말기
        # user_request = USER_PROMPT_TEMPLATE.format(numbered_sections=numbered_sections, review_part=section_split[5])  # 기계설비부문_조명기기
        # user_request = USER_PROMPT_TEMPLATE.format(numbered_sections=numbered_sections, review_part=section_split[6])  # 신재생에너지설비부문

        print(" 사용자 요청사항 ".center(80, '='))
        print(user_request)
        print("=" * 80)

        initial_state = AgentState(user_request=user_request)

        graph_config = RunnableConfig(recursion_limit=1500, configurable={"thread_id": new_uuid()})
        invoke_graph(graph, initial_state, graph_config)

        states_history = list(reversed(list(graph.get_state_history(graph_config))))

        # 마지막 메시지의 content를 .md 파일로 저장
        report_content = states_history[-1].values["messages"][-1].content
        report_file_path = f"{config['paths']['reports_dir']}/report_{trace_id}.md"
        with open(report_file_path, "w", encoding="utf-8") as f:
            f.write(report_content)
        print(f"리포트가 저장되었습니다: {report_file_path}")
        
    except Exception as e:
        # 에러 발생 시에도 로그에 기록
        print(f"프로그램 실행 중 에러 발생: {e}")
        import traceback
        traceback.print_exc()
        raise  # 에러를 다시 발생시켜서 정상적인 에러 처리 유지
    finally:
        # 에러 발생 여부와 관계없이 항상 실행
        
        # image_memory.yaml 백업
        try:
            source_path = 'data/system/image_memory.yaml'
            if os.path.exists(source_path):
                # 백업 디렉토리 생성
                backup_dir = 'outputs/image_memory'
                os.makedirs(backup_dir, exist_ok=True)
                
                # 백업 파일명 생성 (trace_id 사용)
                backup_filename = f"memory_{trace_id}.yaml"
                backup_path = os.path.join(backup_dir, backup_filename)
                
                # 파일 복사
                shutil.copy2(source_path, backup_path)
                print(f"image_memory.yaml 백업 완료: {backup_path}")
        except Exception as backup_error:
            print(f"image_memory.yaml 백업 중 에러 발생: {backup_error}")

        # 프로그램 종료 시간 기록 및 총 소요 시간 계산
        end_time = datetime.now()
        total_duration = end_time - start_time
        
        # timedelta를 HH:MM:SS 형태로 변환
        total_seconds = int(total_duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        duration_formatted = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
        print("=" * 80)
        print(f"총 실행 시간: {duration_formatted}")
        print("=" * 80)

        print("=" * 80)
        credits_new = get_openrouter_credits()
        print(f"OpenRouter Credit Usage: {credits_new['total_usage'] - credits['total_usage']}")
        print(f"OpenRouter Credit Left: {credits_new['total_credits'] - credits_new['total_usage']}")
        print("=" * 80)

        print("=" * 80)
        print(f"디버그 로그가 저장되었습니다: {log_file_path}")
        print("=" * 80)

        print(" OpenRouter key status ".center(80, '='))
        print(get_openrouter_status())
        print("=" * 80)

        sys.stdout = original_stdout
        tee_output.close()  # HTML 푸터 작성하고 파일 닫기

        bot_print(f"{trace_id} 작업 완료")