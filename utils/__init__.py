"""
Utils 패키지

공통 유틸리티 함수들과 설정 관리를 제공합니다.
"""

from .utils import (
    load_config, 
    load_environment, 
    get_llm_model,
    new_uuid,
    parse_eco2od,
    load_image_list,
    load_pdf_metadata,
    invoke_llm_with_retry,
    ansi_to_html,
    TeeOutput,
    get_openrouter_status,
    get_openrouter_credits,
    bot_print
)
from .model_ontology import model_ontology
from .prompt import *

# 애플리케이션 시작 시 로드
load_environment()
config = load_config()
image_list = load_image_list(config)
pdf_metadata = load_pdf_metadata(config)

__all__ = [
    "load_config",
    "load_environment", 
    "get_llm_model",
    "new_uuid",
    "parse_eco2od",
    "load_image_list",
    "load_pdf_metadata",
    "invoke_llm_with_retry",
    "ansi_to_html",
    "TeeOutput",
    "get_openrouter_status",
    "get_openrouter_credits",
    "model_ontology",
    "bot_print",
    "config",  # 전역 config 객체 추가
    "image_list",  # 전역 image_list 객체 추가
    "pdf_metadata"  # 전역 pdf_metadata 객체 추가
] 
