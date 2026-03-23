# BEM Semantic Debugging

A retrieval-augmented generation (RAG)-based multi-agent system for semantic error debugging in building energy models.

## Overview

This system automatically detects semantic errors in building energy model (BEM) files and suggests corrective measures by leveraging modeling manuals as a knowledge base and multimodal processing for building drawing analysis.

The system employs a multi-agent architecture where specialized agents collaborate under a Supervisor:
- **Supervisor**: Orchestrates the workflow and assigns tasks to subordinate agents
- **Manual Analyzer**: Retrieves modeling guidelines from the knowledge base
- **Model Inspector**: Extracts and analyzes input values from BEM files using Python
- **Evidence Extractor**: Extracts ground truth from building drawings and regulatory documents
- **Report Writer**: Generates structured debugging reports with corrections and evidence

LLM API calls are routed through [OpenRouter](https://openrouter.ai/), which provides unified access to various commercial LLM providers. Execution traces can be monitored via [LangSmith](https://smith.langchain.com/) for debugging and performance analysis.

## Installation

1. Clone the repository:

       git clone https://github.com/woo-seung/BEM-semantic-debugging.git
       cd BEM-semantic-debugging

2. Install dependencies:

       pip install -r requirements.txt

3. Set up environment variables:

       cp .env.example .env

   Edit .env with your API keys:

   - `OPENROUTER_API_KEY`: Required. API key from [OpenRouter](https://openrouter.ai/) for LLM access.
   - `OPENROUTER_BASE_URL`: Required. Set to `https://openrouter.ai/api/v1`.
   - `LANGCHAIN_API_KEY`: Optional. API key from [LangSmith](https://smith.langchain.com/) for execution tracing and logging.

## Getting Started

### Step 1: Configure the system

Review config.yaml and adjust settings if needed. Key settings include LLM model selection for each agent, retrieval top-k values, and the model file extension.

### Step 2: Prepare your data

Place your input files in the appropriate directories:

| Directory | Contents | Format |
|-----------|----------|--------|
| data/user/model/ | BEM simulation model file | XML-based (e.g., .ecl2) |
| data/user/images/ | Architectural drawings | JPG or PNG (high resolution) |
| data/user/pdfs/ | Building energy codes | PDF |
| data/system/manuals/ | Modeling guidelines | Markdown (.md) |

### Step 3: Build the knowledge base

The vector database is built automatically on first run. Modeling manuals are split by section headers and regulatory PDFs are chunked into 1,000-character segments, both embedded using OpenAI text-embedding-3-large.

### Step 4: Build the initial image memory (first run only)

The first run performs initial image analysis alongside the first section review. Image analysis results are saved to `data/system/image_memory.yaml` and reused in all subsequent runs.

    python app.py

After the first run, comment out the `perform_initial_image_analysis` block in app.py to prevent duplicate memory entries:

    # print(" 초기 이미지 분석 ".center(80, '='))
    # perform_initial_image_analysis(config)
    # print("=" * 80)

### Step 5: Write the debugging request

The system requires an explicit user prompt specifying which section to review. Open app.py and define the sections in the `section_split` list and activate the target section by uncommenting the corresponding `user_request` line. For example, to review the first section:

    user_request = USER_PROMPT_TEMPLATE.format(..., review_part=section_split[0])
    # user_request = USER_PROMPT_TEMPLATE.format(..., review_part=section_split[1])
    # ...

Each run processes exactly one section. To review the next section, comment out the current `user_request` line and uncomment the next one, then run again.

### Step 6: Run the system

    python app.py

Image memory from previous runs is preserved across sections.

### Step 7: View results

- **Debugging reports**: Saved to `outputs/reports/report_{timestamp}.md` with detected errors, suggested corrections, and source references.
- **Execution logs**: Saved to `outputs/logs/` for detailed run information.
- **LangSmith traces**: If configured, full execution traces are available in your LangSmith dashboard for step-by-step agent interaction analysis.

## Input Data Format

### Model Files
BEM model files are not limited to a specific format. The default implementation uses an XML-based format, parsed via the schema definition in utils/model_ontology.py, which maps XML keys to human-readable field names. If your simulation tool uses a different file format, you will need to customize the parsing logic in utils/model_ontology.py and write the modeling manual accordingly to match that tool's structure.

### Modeling Manuals
Write in Markdown with H1/H2 headers. Each section should describe input field names, modeling rules, default values, and common mistakes.

### Building Drawings
Provide as high-resolution JPG/PNG. The system uses a multimodal LLM to extract floor plans, equipment schedules, and specifications.

### Regulatory Documents
Provide as PDF files. Text is extracted and stored in a vector database for retrieval.

## Adapting to Other BEM Tools

To use with a different simulation tool:

1. **Model schema**: Modify utils/model_ontology.py to define your tool's data structure
2. **Modeling guidelines**: Create a Markdown manual in data/system/manuals/
3. **Configuration**: Update config.yaml (file extension, paths, LLM settings)
4. **User data**: Place model files, drawings, and regulations in data/user/

## Configuration Reference

| Key | Description | Default |
|-----|-------------|---------|
| llm.supervisor.model | LLM for Supervisor | google/gemini-2.5-pro |
| llm.evidence_extractor.model | LLM for Evidence Extractor | qwen/qwen3-235b-a22b-2507 |
| llm.manual_analyzer.model | LLM for Manual Analyzer | qwen/qwen3-235b-a22b-2507 |
| llm.model_inspector.model | LLM for Model Inspector | qwen/qwen3-coder |
| llm.report_writer.model | LLM for Report Writer | google/gemini-2.5-pro |
| llm.image_analyzer.model | LLM for image analysis | google/gemini-2.5-pro |
| llm.*.temperature | LLM temperature | 0.1 |
| retriever.manual.top_k | Manual retrieval results | 3 |
| retriever.pdf.top_k | PDF retrieval results | 2 |
| embedding.model | Embedding model | text-embedding-3-large |
| model_file.suffix | Model file extension | ecl2 |

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
