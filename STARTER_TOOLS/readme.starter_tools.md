# Starter Tools of LlamaIndex

- [LlamaIndex Starter Tools](https://docs.llamaindex.ai/en/stable/getting_started/starter_tools/)
- [npm create llama](https://www.npmjs.com/package/create-llama)
- [RAC CLI](https://docs.llamaindex.ai/en/stable/getting_started/starter_tools/rag_cli/)

# Create LlamaIndex Applications 
___________________________________________________________________________________________________________________________________________________________

```bash
# Install commands:
npx create-llama@latest         # or
npm create llama@latest         # or
llamaindex-cli rag --create-llama
```

- Different ways of running the app:
    - **Next.js backend**: 
        - To index your data: `npm run generate`
        - To run the server: `npm run dev`,  access with: **http://localhost:3000**
    
    - **Python backend**:
        - By the dev-container
        - By UV: uv commands, on *APP*/.venv/ virtual environment
        - By python directly: Bernard's CONDA virtual environment

- Check the parameters in *APP*/.env file: APP_PORT / OPENAI_API_KEY / ...

## Getting Started by UV

1. Setup the environment with uv: `uv sync`
2. Generate the embeddings of the documents in the `./data` directory: `uv run generate`

3. Run the server, and access URL: http://localhost:8000
    - Development server: `uv run fastapi dev`
    - Production  server: `uv run fastapi run`

## Getting Started by Bernard's PVENV

- Generate the embeddings of the documents in the `./data` directory: `python generate.ocr_reader.py`, with env:
    - OCR_READER :  EasyOCR | LlamaParse | GeminiAI | AzureAI | NvidiaAI | Tesseract | GoogleVision
    - OCR_LLM_MODEL: specific LLM models for GeminiAI | AzureAI | NvidiaAI, respectively
        - NvidiaAI: nvidia/llama-3.2-nemoretriever-1b-vlm-embed-v1

```
export BXU_DEBUG=2      # 0 ~ 2
#-------- generate index data with different parser
                                                           OCR_READER=LlamaParse  python generate.ocr_reader.py;
                                                           OCR_READER=EasyOCR     python generate.ocr_reader.py;
export OCR_LLM_MODEL=gemini-2.0-flash;                     OCR_READER=GeminiAI    python generate.ocr_reader.py;
export OCR_LLM_MODEL=microsoft/Phi-4-multimodal-instruct;  OCR_READER=AzureAI     python generate.ocr_reader.py;
export OCR_LLM_MODEL=microsoft/phi-3.5-vision-instruct;    OCR_READER=NvidiaAI    python generate.ocr_reader.py;

#-------- generate index data by starter tools original way
python -c "from generate import generate_index;           generate_index()"              # To index your data
python -c "from generate import generate_ui_for_workflow; generate_ui_for_workflow()"    # To customize UI
```

- Run the FastAPI Web Server HTTP with HTTP / HTTPS
```
python -m uvicorn main:app --reload --host 0.0.0.0
python -m uvicorn main:app --reload --host 0.0.0.0 --ssl-keyfile=../SSL_KEY/key.pem --ssl-certfile=../SSL_KEY/cert.pem  --port 8443
```

# Applicable LLM models for Indexing
___________________________________________________________________________________________________________________________________________________________

- LLM models verification:  FAILED / Poor / Fair / OK / Good / Excellent
- Test dataset:
    - LI-DATA: `BERNARD_SPACE/DATA.starter_tools/` from Llama-index starter_tools
    - TN-DATA: `BERNARD_SPACE/DATA.Tina/CASE.test1/`
    - BS-DATA: `BERNARD_SPACE/DATA.Bernard/CodeGen.test1/`

```
export MY_AI_MODEL=google_GenAI--gemini-1.5-flash                         # 
export MY_AI_MODEL=google_GenAI--gemini-2.0-flash-lite                    # 
export MY_AI_MODEL=google_GenAI--gemini-2.0-flash                         # Good
export MY_AI_MODEL=google_GenAI--gemini-2.5-flash-lite                    # Good
export MY_AI_MODEL=google_GenAI--gemini-2.5-flash                         # OK
export MY_AI_MODEL=google_GenAI--gemini-2.5-pro                           # Good

export MY_AI_MODEL=azureAI--ai21-labs/AI21-Jamba-1.5-Large                # Good
export MY_AI_MODEL=azureAI--cohere/cohere-command-a                       # Good
export MY_AI_MODEL=azureAI--cohere/Cohere-command-r-08-2024               # 
export MY_AI_MODEL=azureAI--cohere/Cohere-command-r-plus-08-2024          # OK (tokens_limit_reached. Max size: 8000 tokens)
export MY_AI_MODEL=azureAI--deepseek/DeepSeek-R1                          # Fair (RateLimitReached)
export MY_AI_MODEL=azureAI--deepseek/DeepSeek-R1-0528                     # Fair (RateLimitReached)
export MY_AI_MODEL=azureAI--deepseek/DeepSeek-V3-0324                     # Poor (RateLimitReached)
export MY_AI_MODEL=azureAI--microsoft/MAI-DS-R1                           # Good (RateLimitReached)
export MY_AI_MODEL=azureAI--microsoft/Phi-4                               # Good (context length: 16384. *deep_research* requested 16848)
export MY_AI_MODEL=azureAI--microsoft/Phi-4-Reasoning                     # Poor (repeat sentences)
export MY_AI_MODEL=azureAI--microsoft/Phi-4-multimodal-instruct           # 
export MY_AI_MODEL=azureAI--microsoft/Phi-3.5-vision-instruct             # 
export MY_AI_MODEL=azureAI--microsoft/Phi-3.5-moe-instruct                # Good
export MY_AI_MODEL=azureAI--microsoft/Phi-3-medium-128k-instruct          # 
export MY_AI_MODEL=azureAI--mistral-ai/Codestral-2501                     # 
export MY_AI_MODEL=azureAI--mistral-ai/Mistral-Large-2411                 # Good (tokens_limit_reached. Max size: 8000 tokens)
export MY_AI_MODEL=azureAI--mistral-ai/mistral-medium-2505                # Good
export MY_AI_MODEL=azureAI--meta/Llama-4-Scout-17B-16E-Instruct           # Good (Max iterations reached)
export MY_AI_MODEL=azureAI--meta/Llama-4-Maverick-17B-128E-Instruct-FP8   # Good
export MY_AI_MODEL=azureAI--openai/gpt-4.1                                # Good
export MY_AI_MODEL=azureAI--openai/gpt-4o                                 # Good
export MY_AI_MODEL=azureAI--openai/o3                                     # FAILED (Operation Forbidden)
export MY_AI_MODEL=azureAI--openai/o3-mini                                # FAILED (Operation Forbidden)
export MY_AI_MODEL=azureAI--openai/o4-mini                                # FAILED (Unavailable model)
export MY_AI_MODEL=azureAI--xai/grok-3                                    # FAILED (RateLimitReached)

export MY_AI_MODEL=OpenRouter--agentica-org/deepcoder-14b-preview:free    # FAILED (No endpoints found)
export MY_AI_MODEL=OpenRouter--deepseek/deepseek-v3-base:free             # FAILED (No endpoints found)
export MY_AI_MODEL=OpenRouter--deepseek/deepseek-chat-v3-0324:free        # Good
export MY_AI_MODEL=OpenRouter--deepseek/deepseek-r1:free                  # FAILED (Got empty message)
export MY_AI_MODEL=OpenRouter--deepseek/deepseek-r1-0528:free             # FAILED (Got empty message)
export MY_AI_MODEL=OpenRouter--deepseek/deepseek-r1-distill-llama-70b     # FAILED (Got empty message)
export MY_AI_MODEL=OpenRouter--google/gemini-2.0-flash-exp:free           # Good (RateLimitError 429)
export MY_AI_MODEL=OpenRouter--meta-llama/llama-4-scout                   # OK (Max iterations reached)
export MY_AI_MODEL=OpenRouter--meta-llama/llama-4-maverick                # Good
export MY_AI_MODEL=OpenRouter--openai/gpt-4.1                             # OK (imcomplete)
export MY_AI_MODEL=OpenRouter--openai/o3-mini                             # FAILED (Got empty message)
export MY_AI_MODEL=OpenRouter--qwen/qwen3-235b-a22b-07-25                 # OK (limited to 5 requests per minute.)
export MY_AI_MODEL=OpenRouter--x-ai/grok-3                                # OK (imcomplete)

export MY_AI_MODEL=nvidia--meta/llama-3.1-405b-instruct                   # Fair (llama_index.core.llms.function_calling:tool_required is not supported)
export MY_AI_MODEL=nvidia--meta/llama-3.1-70b-instruct                    # Fair (works on LI-DATA, failed on TN-DATA)
export MY_AI_MODEL=nvidia--meta/llama-3.3-70b-instruct                    # Fair (RateLimitError 429)
export MY_AI_MODEL=nvidia--meta/llama-4-maverick-17b-128e-instruct        # Good
export MY_AI_MODEL=nvidia--meta/llama-4-scout-17b-16e-instruct            # OK (Max iterations reached)
export MY_AI_MODEL=nvidia--mistralai/mistral-medium-3-instruct            # Good
export MY_AI_MODEL=nvidia--mistralai/mistral-large-2-instruct             # FAILED (Error code: 404)
export MY_AI_MODEL=nvidia--writer/palmyra-creative-122b                   # Fair (can NOT handle Chinese)
export MY_AI_MODEL=nvidia--writer/palmyra-fin-70b-32k                     # Fair (can NOT handle Chinese)
export MY_AI_MODEL=nvidia--qwen/qwen3-235b-a22b                           # OK
export MY_AI_MODEL=nvidia--deepseek-ai/deepseek-r1-0528                   # OK (long time)
export MY_AI_MODEL=nvidia--microsoft/phi-4-multimodal-instruct            # Fair (repeat sentences)
export MY_AI_MODEL=nvidia--nvidia/llama-3.1-nemotron-ultra-253b-v1        # OK
export MY_AI_MODEL=nvidia--nvidia/nemotron-4-340b-instruct                # FAILED (Error code: 404)
export MY_AI_MODEL=nvidia--nvidia/nemotron-4-340b-reward                  # FAILED (Error code: 404)
export MY_AI_MODEL=nvidia--igenius/colosseum_355b_instruct_16k            # OK  (long time)

##FAILURE## Error code: 404
>>>  workflows.errors.WorkflowRuntimeError: Error in step 'run_agent_step': Error code: 404 -
     {'status': 404, 'title': 'Not Found', 'detail': "Function 'c53ee0e9-bad9-4e09-b365-52c9d6b71254': Not found for account 'Vr96ks3Z4Qf8BKjEkgWm7YOnnKip7wNwB7QTg9J1AM4'"}

##FAILURE## RateLimitError 429
>>> openai.RateLimitError: Error code: 429 - {'error': {'message': 'Provider returned error', 'code': 429, 'metadata': {'raw': 'google/gemini-2.0-flash-exp:free is temporarily rate-limited upstream. Please retry shortly, or add your own key to accumulate your rate limits: https://openrouter.ai/settings/integrations', 'provider_name': 'Google'}}, 'user_id': 'user_2wJKJwlcaJcDPHkoivAkLNRNePu'}

##FAILURE## RateLimitReached
>>> workflows.errors.WorkflowRuntimeError: Error in step 'run_agent_step': (RateLimitReached) Rate limit of 1 per 0s exceeded for UserConcurrentRequests. Please wait 0 seconds before retrying.

##FAILURE## Max iterations reached
>>> workflows.errors.WorkflowRuntimeError: Error in step 'parse_agent_output': Max iterations of 20 reached! Either something went wrong, or you can increase the max iterations with `.run(.., max_iterations=...)`

##FAILURE## Operation Forbidden
>>> workflows.errors.WorkflowRuntimeError: Error in step 'run_agent_step': Operation returned an invalid status 'Forbidden'

##FAILURE## Unavailable model
>>> workflows.errors.WorkflowRuntimeError: Error in step 'run_agent_step': (unavailable_model) Unavailable model: o4-mini

##FAILURE## Got empty message
>>> workflows.errors.WorkflowRuntimeError: Error in step 'run_agent_step': Got empty message

##FAILURE## No endpoints found 
>>> workflows.errors.WorkflowRuntimeError: Error in step 'run_agent_step': Error code: 404 - {'error': {'message': 'No endpoints found for deepseek/deepseek-v3-base.', 'code': 404}, 'user_id': 'user_30FpScMUGq5Gv3rXMcvmt0fOXS5'}

```

# Applicable LLM models for OCR Image Parsing
___________________________________________________________________________________________________________________________________________________________

## Working READER and Models

```
                                                                    date; time OCR_READER=LlamaParse python generate.ocr_reader.py; date
                                                                    date; time OCR_READER=EasyOCR    python generate.ocr_reader.py; date

export OCR_LLM_MODEL=gemini-1.5-flash;                              date; time OCR_READER=GeminiAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=gemini-2.0-flash;                              date; time OCR_READER=GeminiAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=gemini-2.0-flash-lite;                         date; time OCR_READER=GeminiAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=gemini-2.5-flash;                              date; time OCR_READER=GeminiAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=gemini-2.5-flash-lite;                         date; time OCR_READER=GeminiAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=gemini-2.5-pro;                                date; time OCR_READER=GeminiAI   python generate.ocr_reader.py |tee log-OCR.ignore; date

export OCR_LLM_MODEL=microsoft/phi-4-multimodal-instruct;           date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=microsoft/phi-3.5-vision-instruct;             date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=mistralai/mistral-small-3.1-24b-instruct-2503  date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=meta/llama-4-scout-17b-16e-instruct;           date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=meta/llama-4-maverick-17b-128e-instruct        date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=nvidia/llama-3.1-nemotron-nano-vl-8b-v1        date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=google/gemma-3-27b-it                          date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=google/gemma-3n-e4b-it                         date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
export OCR_LLM_MODEL=google/gemma-3n-e2b-it                         date; time OCR_READER=NvidiaAI   python generate.ocr_reader.py |tee log-OCR.ignore; date
```

- TODO: more READER and Models to verify
    - OCR_READER=AzureAI
        - microsoft/phi-4-multimodal-instruct  microsoft/phi-3.5-vision-instruct  openai/gpt-4.1
    - OCR_READER=ORoutAI
        - OpenRouter--meta-llama/llama-4-scout  OpenRouter--meta-llama/llama-4-maverick  OpenRouter--openai/gpt-4.1

## batch generation script

```
bvenv ai8;   cd llama_index/bernard.campus/super_starter_suite/HELPER_TOOLS;  source gen_ocr_reader.sh

#----------------------------------------------------------------------------------------------------
export OCR_READER=GeminiAI   
export OCR_models="gemini-1.5-flash  gemini-2.0-flash  gemini-2.0-flash-lite "   # gemini-2.5-flash gemini-2.5-flash-lite gemini-2.5-pro

export OCR_READER=NvidiaAI
export OCR_models="microsoft/phi-4-multimodal-instruct  microsoft/phi-3.5-vision-instruct  mistralai/mistral-small-3.1-24b-instruct-2503
       meta/llama-4-scout-17b-16e-instruct  meta/llama-4-maverick-17b-128e-instruct  nvidia/llama-3.1-nemotron-nano-vl-8b-v1
       google/gemma-3n-e4b-it google/gemma-3n-e2b-it"  # google/gemma-3-27b-it 

#----------------------------------------------------------------------------------------------------
for r in LlamaParse EasyOCR; do
    export OCR_READER=$r
    do_generate_ocr_reader $OCR_READER
done

#----------------------------------------------------------------------------------------------------
for om in $OCR_models; do
    export OCR_LLM_MODEL=$om
    do_generate_ocr_reader $OCR_READER.$om
done
```

## Benchmark result

| OCR_READER  | Model                                             | Elapsed Time |
|-------------|---------------------------------------------------|--------------|
| LlamaParse  |                                                   | 22m 29s      |
| EasyOCR     |                                                   |  5m 12s      |
| GeminiAI    |                                                   |  ??          |
| NvidiaAI    |                                                   |  ??          |


___________________________________________________________________________________________________________________________________________________________
# cheat sheet
___________________________________________________________________________________________________________________________________________________________

```
export MY_AI_MODEL=nvidia--meta/llama-4-maverick-17b-128e-instruct
export MY_AI_MODEL=nvidia--qwen/qwen3-235b-a22b
python -m uvicorn main:app --reload --host 0.0.0.0

#----------------------------------------------------------------------------------------------------
# general indexing
python -c "from generate import generate_index; generate_index()"
OCR_READER=LlamaParse python generate.ocr_reader.py;
```
