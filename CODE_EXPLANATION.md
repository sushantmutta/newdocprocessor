# Complete Code Explanation - Medical Document Processing System

## Table of Contents
1. [State Management](#state-management)
2. [LLM Client](#llm-client)
3. [Agents](#agents)
   - [Classifier Agent](#classifier-agent)
   - [Extractor Agent](#extractor-agent)
   - [Validator Agent](#validator-agent)
   - [Repair Agent](#repair-agent) ⭐ NEW
   - [Redactor Agent](#redactor-agent)
   - [Reporter Agent](#reporter-agent)
4. [Schemas](#schemas)
   - [Prescription Schema](#prescription-schema)
   - [Lab Report Schema](#lab-report-schema)
5. [Graph Architecture](#graph-architecture) ⭐ NEW
   - [Dual Graph System](#dual-graph-system)
   - [Workflow Routing](#workflow-routing)
6. [API Endpoints](#api-endpoints) ⭐ NEW
   - [Standard Processing](#standard-processing)
   - [Human-in-the-Loop](#human-in-the-loop-api)
7. [Frontend Interface](#frontend-interface) ⭐ NEW
   - [Human Review UI](#human-review-ui)
   - [Decision Options](#decision-options)
8. [Contextual Knowledge](#contextual-knowledge) ⭐ NEW
   - [Medical Domain Context](#medical-domain-context)
   - [Design Philosophy](#design-philosophy)

---

## State Management

**File:** `app/state.py`

### Line-by-Line Explanation

```python
from typing import TypedDict, List, Optional, Any
```
- **`from typing import`**: Import Python's type hinting module
- **`TypedDict`**: Special class that defines a dictionary with specific key types (like a schema for dictionaries)
- **`List`**: Type hint for list/array types
- **`Optional`**: Indicates a value can be the specified type OR `None`
- **`Any`**: Accepts any type (use sparingly - reduces type safety)

```python
class DocState(TypedDict):
```
- **`class DocState`**: Defines a new class named `DocState`
- **`TypedDict`**: Base class - makes this a typed dictionary (enforces structure but allows dict-like access)
- **Purpose**: Central data structure that flows through the entire pipeline
- All agents read from and write to this shared state

```python
    raw_text: str
```
- **Field name**: `raw_text`
- **Type**: `str` (string - required, not Optional)
- **Purpose**: Stores the OCR-extracted text from PDF/image
- **Example**: `"Dr. House\n Patient: John Doe\n Rx: Amoxicillin 500mg..."`

```python
    file_path: str
```
- **Type**: `str` (required)
- **Purpose**: Path to the original document file
- **Example**: `"C:/medical_docs/prescription_001.pdf"`

```python
    doc_type: Optional[str]
```
- **Type**: `Optional[str]` means `str | None`
- **Purpose**: Classified document type set by Classifier agent
- **Values**: `"prescription"`, `"lab_report"`, or `"unknown"`
- **Initially**: `None` (before classification)

```python
    extracted_data: Optional[dict]
```
- **Type**: `Optional[dict]` - can be dictionary or None
- **Purpose**: Structured data extracted by Extractor agent
- **Example (prescription)**:
  ```json
  {
    "doctor": {"name": "Dr. House", "license_number": "CA-12345"},
    "patient": {"name": "John Doe", "age": 45},
    "medications": [{"name": "Amoxicillin", "dosage": "500mg"}]
  }
  ```

```python
    validated_data: Optional[dict]
```
- **Type**: `Optional[dict]`
- **Purpose**: Data after Pydantic schema validation (cleaned & validated)
- **Difference from extracted_data**: May have default values applied, types converted

```python
    validation_flags: List[dict]
```
- **Type**: `List[dict]` - list of dictionaries (not Optional - always exists, can be empty `[]`)
- **Purpose**: Clinical safety alerts and data quality issues
- **Example**:
  ```json
  [
    {
      "code": "INVALID_DOSAGE_UNIT",
      "message": "Invalid unit 'liters' in Amoxicillin: 7 liters",
      "severity": "HIGH"
    }
  ]
  ```

```python
    redacted_text: Optional[str]
```
- **Type**: `Optional[str]`
- **Purpose**: Text with PII/PHI removed by Redactor agent
- **Example**: `"Dr. [NAME_REDACTED]\n Patient: [NAME_REDACTED]\n MRN: [MRN_REDACTED]"`

```python
    errors: List[str]
```
- **Type**: `List[str]` - list of error message strings
- **Purpose**: Technical errors encountered during processing
- **Example**: `["Extraction parse error: No valid JSON found"]`

```python
    trace_log: List[dict]
```
- **Type**: `List[dict]` - audit trail of agent actions
- **Purpose**: Debugging, monitoring, responsible AI tracking
- **Example**:
  ```json
  [
    {"agent": "classifier", "output": "PRESCRIPTION", "confidence": 0.95},
    {"agent": "extractor_prescription", "status": "success", "fields_found": ["doctor", "patient"]}
  ]
  ```

```python
    repair_attempts: int
```
- **Type**: `int` (integer, not Optional - must always have a value)
- **Purpose**: Count of how many times auto-repair was attempted
- **Currently**: Always 0 (auto-repair feature removed per user requirement)

```python
    llm_provider: Optional[str]
```
- **Type**: `Optional[str]`
- **Purpose**: Which LLM provider to use (runtime selection)
- **Values**: `"ollama"` (local), `"groq"` (cloud), `"bedrock"` (AWS)
- **Default**: From `LLM_PROVIDER` environment variable

```python
    llm_model_name: Optional[str]
```
- **Type**: `Optional[str]`
- **Purpose**: Track which specific model was used
- **Example**: `"llama-3.3-70b-versatile"` or `"llama-3.1-8b-instant"`

```python
    confidence_score: float
```
- **Type**: `float` (decimal number)
- **Purpose**: AI confidence in extraction accuracy
- **Range**: 0.0 (no confidence) to 1.0 (complete confidence)
- **Example**: `0.85` means 85% confident

---

## LLM Client

**File:** `app/llm_client.py`

### Import Section

```python
import os
```
- **Purpose**: Access operating system functions (environment variables, file paths)

```python
import boto3
```
- **Purpose**: AWS SDK for Python (used for Bedrock integration)

```python
import hashlib
```
- **Purpose**: Generate hash keys for caching (MD5 hashes of prompts)

```python
import json
```
- **Purpose**: Parse and serialize JSON data

```python
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_aws import ChatBedrock
```
- **LangChain**: Framework for LLM applications
- **ChatGroq**: Groq cloud LLM provider wrapper
- **ChatOllama**: Local Ollama LLM provider wrapper
- **ChatBedrock**: AWS Bedrock LLM provider wrapper

```python
from tenacity import retry, stop_after_attempt, wait_exponential
```
- **tenacity**: Retry logic library
- **@retry**: Decorator for automatic retry on failure
- **stop_after_attempt(3)**: Stop after 3 failed attempts
- **wait_exponential**: Wait 2s, 4s, 8s between retries (exponential backoff)

```python
from botocore.exceptions import ClientError
```
- **botocore**: AWS SDK core exceptions
- **ClientError**: AWS API errors (404, 403, etc.)

```python
from dotenv import load_dotenv
```
- **dotenv**: Load environment variables from `.env` file
- **load_dotenv()**: Reads `.env` and sets variables in `os.environ`

```python
from functools import lru_cache
```
- **lru_cache**: Least Recently Used cache decorator (not currently used)

```python
load_dotenv()
```
- **Execute immediately**: Load `.env` file when module is imported

```python
_response_cache = {}
```
- **Module-level variable**: In-memory cache dictionary
- **Underscore prefix `_`**: Convention for "private" module variable
- **Purpose**: Store LLM responses to avoid duplicate API calls

### Class Definition

```python
class UnifiedLLMManager:
```
- **Class name**: `UnifiedLLMManager`
- **Purpose**: Single interface to manage multiple LLM providers
- **Design Pattern**: Strategy pattern (switch providers at runtime)

```python
    """
    Unified LLM Manager supporting multiple providers (Ollama, Groq, Bedrock).
    Provider can be selected via constructor parameter or LLM_PROVIDER environment variable.
    """
```
- **Docstring**: Multi-line comment explaining class purpose
- **Triple quotes `"""`**: Python convention for documentation

```python
    def __init__(self, provider: str = None):
```
- **`def`**: Define a function/method
- **`__init__`**: Special method called when creating class instance (constructor)
- **`self`**: Reference to the instance itself (like `this` in JavaScript)
- **`provider: str = None`**: 
  - Parameter named `provider`
  - Type hint `: str`
  - Default value `= None` (optional parameter)

```python
        self.provider = (provider or os.getenv("LLM_PROVIDER", "ollama")).lower()
```
- **`provider or os.getenv(...)`**: If provider is None/empty, get from environment
- **`os.getenv("LLM_PROVIDER", "ollama")`**: Get env var, default to "ollama" if not set
- **`.lower()`**: Convert to lowercase (normalize input)
- **`self.provider =`**: Store as instance variable

```python
        self.provider_name = self.provider
```
- **Store original value**: For logging purposes

```python
        if self.provider == "ollama":
            self._setup_ollama()
        elif self.provider == "groq":
            self._setup_groq()
        elif self.provider == "bedrock":
            self._setup_bedrock()
```
- **Conditional routing**: Call different setup method based on provider
- **`if/elif/else`**: Python's conditional statements
- **`_setup_*` methods**: Private methods (underscore prefix convention)

```python
        else:
            raise ValueError(
                f"Unsupported LLM provider: '{self.provider}'. "
                f"Supported providers: 'ollama', 'groq', 'bedrock'"
            )
```
- **`raise ValueError`**: Throw an exception (error) to stop execution
- **`f"..."`**: F-string (formatted string) - can embed variables with `{}`
- **Multi-line string**: Parentheses allow string to span lines

### Ollama Setup

```python
    def _setup_ollama(self):
        """Configure Ollama (local) LLM provider"""
```
- **Method definition**: Private method for Ollama configuration
- **Docstring**: Single-line documentation

```python
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
```
- **Environment variable**: Get Ollama server URL
- **Default**: Local server at port 11434

```python
        primary_model = os.getenv("OLLAMA_PRIMARY_MODEL", "llama3.1:8b")
        fallback_model = os.getenv("OLLAMA_FALLBACK_MODEL", "llama3.1:8b")
```
- **Two models**: Primary (first try) and fallback (if primary fails)
- **Default**: Same model for both (llama3.1:8b)

```python
        print(f"🤖 Initializing Ollama provider: {primary_model}")
```
- **Console output**: Log initialization (emoji for visibility)

```python
        self.primary_llm = ChatOllama(
            model=primary_model,
            base_url=base_url,
            temperature=0,
            num_predict=2048
        )
```
- **Create LangChain wrapper**: 
  - **`model`**: Which Ollama model to use
  - **`base_url`**: Where Ollama server is running
  - **`temperature=0`**: Deterministic output (no randomness)
    - 0 = always same output for same input
    - 1 = maximum creativity/randomness
  - **`num_predict=2048`**: Limit response to 2048 tokens (faster inference)

### Groq Setup

```python
    def _setup_groq(self):
        """Configure Groq (cloud) LLM provider"""
        api_key = os.getenv("GROQ_API_KEY")
```
- **Get API key**: From environment variable (never hardcode secrets!)

```python
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found in .env. "
                "Get your key from: https://console.groq.com"
            )
```
- **Validation**: Fail fast if API key is missing
- **Helpful error message**: Tells user where to get key

```python
        primary_model = os.getenv("GROQ_PRIMARY_MODEL", "llama-3.3-70b-versatile")
        fallback_model = os.getenv("GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")
```
- **Default models**: 
  - Primary: Large model (70B parameters) - more capable
  - Fallback: Smaller model (8B parameters) - faster, cheaper

```python
        self.primary_llm = ChatGroq(
            model=primary_model,
            temperature=0,
            groq_api_key=api_key,
            max_tokens=2048
        )
```
- **ChatGroq instance**: 
  - **`groq_api_key`**: Authentication
  - **`max_tokens`**: Limit response length (controls cost)

### Bedrock Setup

```python
    def _setup_bedrock(self):
        """Configure AWS Bedrock (cloud) LLM provider"""
        region = os.getenv("AWS_REGION", "us-east-1")
```
- **AWS Region**: Where Bedrock service is located
- **Default**: us-east-1 (Virginia)

```python
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not aws_access_key or not aws_secret_key:
            raise ValueError(
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY not found in .env. "
                "Required for Bedrock provider."
            )
```
- **AWS Credentials**: Two-part authentication
- **Validation**: Both required or fail

```python
        runtime_client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )
```
- **boto3.client**: Create AWS service client
- **`"bedrock-runtime"`**: Service name for model invocation
- **Credentials passed**: For authentication

```python
        self.primary_llm = ChatBedrock(
            model_id=primary_model,
            client=runtime_client,
            model_kwargs={
                "temperature": 0,
                "max_tokens": 2048
            }
        )
```
- **ChatBedrock**: LangChain wrapper for AWS Bedrock
- **`model_kwargs`**: Model-specific parameters passed as dictionary

### Invoke with Fallback

```python
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6))
```
- **Decorator**: Modifies function behavior
- **`@retry`**: Automatically retry on exception
- **`stop_after_attempt(3)`**: Try 3 times total (1 initial + 2 retries)
- **`wait_exponential`**: 
  - First retry: wait 2 seconds
  - Second retry: wait 4 seconds
  - Max wait: 6 seconds

```python
    def invoke_with_fallback(self, messages, use_cache=True):
```
- **Method**: Core function to call LLM
- **`messages`**: List of LangChain message objects
- **`use_cache=True`**: Default to using cache (can disable)

```python
        cache_key = None
        if use_cache:
            cache_key = self._generate_cache_key(messages)
```
- **Generate unique key**: Hash of messages content

```python
            if cache_key in _response_cache:
                print(f"💾 Cache hit for {self.provider}")
                return _response_cache[cache_key]
```
- **Check cache**: If we've seen this exact prompt before, return cached response
- **`in` operator**: Check dictionary key existence
- **Early return**: Skip LLM call entirely

```python
        try:
            response = self.primary_llm.invoke(messages)
```
- **`try` block**: Attempt code that might fail
- **`.invoke(messages)`**: LangChain method to call LLM

```python
            if use_cache and cache_key:
                _response_cache[cache_key] = response
```
- **Store in cache**: Save for future use

```python
            return response
```
- **Return LLM response**: Object with `.content` attribute

```python
        except Exception as e:
```
- **`except`**: Catch any error that occurs in try block
- **`Exception`**: Base class for all errors
- **`as e`**: Store error object in variable `e`

```python
            error_msg = str(e)
```
- **Convert to string**: Get error message text

```python
            is_rate_limit = "rate_limit" in error_msg.lower() or "429" in error_msg
```
- **Error detection**:
  - **`"rate_limit" in error_msg.lower()`**: Check if text contains "rate_limit" (case-insensitive)
  - **`"429" in error_msg`**: HTTP status code for "Too Many Requests"
  - **`or`**: True if either condition is true

```python
            if is_rate_limit:
                print(f"⚠️ {self.provider.capitalize()} Rate limit reached. Trying fallback model...")
```
- **`.capitalize()`**: Convert first letter to uppercase ("groq" → "Groq")

```python
            else:
                print(f"⚠️ {self.provider.capitalize()} Primary failed: {e}. Trying fallback...")
```
- **Generic error**: Not rate limit, some other failure

```python
            try:
                response = self.fallback_llm.invoke(messages)
```
- **Nested try**: Attempt fallback model
- **Same messages**: Retry with identical prompt

```python
                if use_cache and cache_key:
                    _response_cache[cache_key] = response
                return response
```
- **Success**: Cache and return fallback response

```python
            except Exception as fallback_error:
```
- **Fallback also failed**: Both models are down/failing

```python
                fallback_msg = str(fallback_error)

                if "rate_limit" in fallback_msg.lower() or "429" in fallback_msg:
                    print(f"❌ Both models rate limited. Please wait or upgrade your {self.provider.capitalize()} plan.")
                    raise Exception(
                        f"Rate limit exceeded for {self.provider}. Both primary and fallback models are rate limited. "
                        f"Please wait a few minutes or upgrade your API plan."
                    ) from fallback_error
```
- **Specific error handling**: Provide helpful message for rate limits
- **`raise Exception(...) from fallback_error`**: 
  - Create new exception with custom message
  - Chain from original error (preserves stack trace)

```python
                elif "decommissioned" in fallback_msg.lower() or "model_decommissioned" in fallback_msg:
                    print(f"❌ Fallback model decommissioned: {fallback_error}")
                    raise Exception(
                        f"Fallback model is no longer supported. Please update GROQ_FALLBACK_MODEL in .env file."
                    ) from fallback_error
```
- **Model deprecation**: Groq removed the model from service

```python
                else:
                    print(f"❌ Fallback also failed: {fallback_error}")
                    raise Exception(
                        f"Both primary and fallback LLMs failed for provider '{self.provider}'"
                    ) from fallback_error
```
- **Generic failure**: Both models failed for unknown reason

```python
    def _generate_cache_key(self, messages):
        """Generate a hash key for caching based on message content."""
        msg_str = json.dumps(
            [{"type": type(m).__name__, "content": str(m.content)[:500]} for m in messages])
```
- **List comprehension**: `[... for m in messages]` - create list by iterating
- **`type(m).__name__`**: Get class name ("HumanMessage", "SystemMessage")
- **`str(m.content)[:500]`**: First 500 characters of message content
  - **`[:500]`**: String slicing - characters 0 to 499
- **`json.dumps(...)`**: Convert Python object to JSON string

```python
        return hashlib.md5(f"{self.provider}:{msg_str}".encode()).hexdigest()
```
- **`.encode()`**: Convert string to bytes (required for hashing)
- **`hashlib.md5(...)`**: Create MD5 hash object
- **`.hexdigest()`**: Get hash as hex string (e.g., "a4f3b2c1...")
- **`f"{self.provider}:{msg_str}"`**: Include provider in cache key

```python
GroqManager = UnifiedLLMManager
```
- **Backward compatibility**: Alias for old code that used `GroqManager`

---

## Agents

### Classifier Agent

**File:** `app/agents/classifier.py`

#### Import Section

```python
from langchain_core.messages import HumanMessage, SystemMessage
```
- **LangChain message types**:
  - **SystemMessage**: Instructions/context for AI (like "You are a medical expert")
  - **HumanMessage**: User's question/input

```python
from langchain_core.output_parsers import PydanticOutputParser
```
- **PydanticOutputParser**: Converts LLM text output to structured Pydantic models
- **Purpose**: Force LLM to return JSON matching our schema

```python
from pydantic import BaseModel, Field
```
- **Pydantic**: Data validation library using Python type hints
- **BaseModel**: Base class for data models
- **Field**: Define field metadata (description, constraints)

```python
from app.llm_client import UnifiedLLMManager
from app.state import DocState
```
- **Local imports**: Our custom modules

#### DocumentClassification Model

```python
class DocumentClassification(BaseModel):
```
- **Pydantic model**: Defines structure for LLM output

```python
    """Structured output for document classification."""
```
- **Docstring**: Explains class purpose

```python
    document_type: str = Field(
        description="The classified document type: PRESCRIPTION, LAB_REPORT, or UNKNOWN"
    )
```
- **Field definition**:
  - **`document_type`**: Field name
  - **`: str`**: Type hint (must be string)
  - **`= Field(...)`**: Pydantic field configuration
  - **`description`**: Used by LLM to understand what to output

```python
    confidence: float = Field(
        description="Confidence score between 0.0 and 1.0",
        ge=0.0,
        le=1.0
    )
```
- **Field with constraints**:
  - **`ge=0.0`**: Greater than or equal to 0.0
  - **`le=1.0`**: Less than or equal to 1.0
  - **Validation**: Pydantic will reject values outside this range

```python
    reasoning: str = Field(
        description="Brief explanation of the classification decision"
    )
```
- **Reasoning field**: Helps with debugging and transparency

#### Classification Function

```python
def classify_doc(state: DocState) -> DocState:
```
- **Function signature**:
  - **`state: DocState`**: Input parameter with type hint
  - **`-> DocState`**: Return type annotation
  - **Pattern**: Agent functions take state, modify it, return it

```python
    """
    Determines document type using LLM with enhanced prompting and structured output parsing.
    Routes to: [prescription, lab_report, unknown]
    """
```
- **Docstring**: Explains routing logic

```python
    llm_manager = UnifiedLLMManager(provider=state.get("llm_provider"))
```
- **Initialize LLM**: Use provider from state (or default)
- **`.get("llm_provider")`**: Dictionary method - returns None if key doesn't exist

```python
    print(f"--- 🔍 Agent: Classifier ({llm_manager.provider_name}) ---")
```
- **Console logging**: Visual separator for debugging

```python
    active_model = getattr(llm_manager, 'model_name', 'unknown')
```
- **`getattr(object, 'attribute', default)`**: Safely get object attribute
  - Returns `llm_manager.model_name` if it exists
  - Returns `'unknown'` if attribute doesn't exist
- **Purpose**: Handle different LLM providers gracefully

```python
    parser = PydanticOutputParser(pydantic_object=DocumentClassification)
```
- **Create parser**: Will convert LLM text to DocumentClassification object
- **How it works**: Tells LLM to output JSON matching the schema

```python
    system_prompt = f"""You are an advanced Medical Document Intelligence Agent. Your goal is to accurately classify documents.

### CLASSIFICATION TASK
Analyze the document structure to determine its type EXACTLY as one of the following:

- **PRESCRIPTION**: Contains "Rx" symbol, doctor details (Name, License), and medication list.
- **LAB_REPORT**: Contains "Test Results", reference ranges, and lab accreditation.
- **UNKNOWN**: If neither pattern matches.

CLASSIFICATION RULES:
1. Look for key indicators:
   - Prescription: "Rx" symbol (☤), "Doctor Name", "License Number", "Patient Name", "Medication List", "Dosage", "Sig"
   - Lab Report: "Test Results", "Reference Range", "Lab Name", "Collection Date", "Report Date", "Analyte", "Specimen"
2. If uncertain or ambiguous, default to "UNKNOWN".

{parser.get_format_instructions()}"""
```
- **F-string with triple quotes**: Multi-line formatted string
- **Prompt engineering**:
  - **Role assignment**: "You are an advanced Medical Document Intelligence Agent"
  - **Clear options**: List exact classification values
  - **Examples**: Show key indicators for each type
  - **Fallback rule**: Default to UNKNOWN if unsure
- **`{parser.get_format_instructions()}`**: Inserts JSON schema instructions
  - Example output: "Output as JSON: {\"document_type\": \"PRESCRIPTION\", \"confidence\": 0.95, \"reasoning\": \"...\"}"

```python
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Classify this document text:\n\n{state['raw_text'][:2000]}")
    ]
```
- **Message array**: LangChain format for LLM input
- **SystemMessage first**: Sets context/instructions
- **HumanMessage second**: The actual task
- **`state['raw_text'][:2000]`**: First 2000 characters only
  - **Why**: Classification doesn't need full document
  - **Benefit**: Faster, cheaper, stays within token limits

```python
    try:
        response = llm_manager.invoke_with_fallback(messages)
```
- **Call LLM**: Try primary, fall back if needed

```python
        content = response.content.strip()
```
- **Extract text**: `.content` is the LLM's text response
- **`.strip()`**: Remove leading/trailing whitespace

```python
        try:
            classification = parser.parse(content)
```
- **Try structured parsing**: Convert JSON string to DocumentClassification object

```python
            doc_type = classification.document_type.upper()
            confidence = classification.confidence
```
- **Extract fields**: From validated Pydantic object
- **`.upper()`**: Convert to uppercase for normalization

```python
        except Exception:
            # Fallback: Check if response is just a simple text classification
            content_upper = content.upper()
            if content_upper in ['PRESCRIPTION', 'LAB_REPORT', 'UNKNOWN']:
                doc_type = content_upper
                confidence = 0.8
```
- **Parsing fallback**: LLM might return just "PRESCRIPTION" instead of full JSON
- **`if content_upper in [...]`**: Check if response is one of valid values
- **Default confidence**: 0.8 (lower because not from structured output)

```python
            elif 'PRESCRIPTION' in content_upper:
                doc_type = 'PRESCRIPTION'
                confidence = 0.75
```
- **Partial match**: If word "PRESCRIPTION" appears anywhere

```python
            elif 'LAB_REPORT' in content_upper or 'LAB REPORT' in content_upper:
                doc_type = 'LAB_REPORT'
                confidence = 0.75
```
- **Two variants**: Handle with/without underscore

```python
            else:
                doc_type = 'UNKNOWN'
                confidence = 0.5
```
- **Ultimate fallback**: Can't determine type

```python
        if doc_type not in ['PRESCRIPTION', 'LAB_REPORT', 'UNKNOWN']:
            print(f"⚠️ Invalid classification '{doc_type}', defaulting to 'UNKNOWN'")
            doc_type = 'UNKNOWN'
            confidence = 0.5
```
- **Validation**: Ensure output is one of allowed values
- **Safety net**: LLM might hallucinate invalid types

```python
    except Exception as e:
        print(f"⚠️ Classification failed: {e}, defaulting to 'UNKNOWN'")
        doc_type = 'UNKNOWN'
        confidence = 0.3
```
- **Outer exception handler**: LLM call itself failed (API error, network, etc.)
- **Very low confidence**: 0.3 because we're just guessing

```python
    state["doc_type"] = doc_type.lower()
    state["confidence_score"] = confidence
```
- **Update state**: Modify dictionary in-place
- **`.lower()`**: Store as lowercase ("prescription" not "PRESCRIPTION")

```python
    state["trace_log"].append({
        "agent": "classifier",
        "output": doc_type,
        "confidence": confidence,
        "model": active_model,
        "provider": llm_manager.provider_name
    })
```
- **Audit trail**: Record what happened for debugging
- **`.append(...)`**: Add to end of list

```python
    return state
```
- **Return modified state**: Passes to next agent in pipeline

---

### Extractor Agent

**File:** `app/agents/extractor.py`

#### Import Section

```python
import json
import re
```
- **json**: Parse JSON strings from LLM
- **re**: Regular expressions for pattern matching

```python
from typing import Optional, Dict, Any, List
```
- **More type hints**: For complex types

#### Prompt Templates

```python
PROMPT_TEMPLATES = {
    "prescription": """...""",
    "lab_report": """..."""
}
```
- **Dictionary of prompts**: Key by document type
- **Design**: Each document type has specialized extraction instructions

**Prescription Prompt Analysis:**

```python
REQUIRED FIELDS:
1. doctor (object):
   - name: doctor's full name (e.g., "Dr. Gregory House")
   - license_number: Medical license (Format: StateCode-Digits e.g., "MH-12345")
```
- **Explicit structure**: Tell LLM exact format expected
- **Examples**: Show desired output format

```python
VALID DOSAGE UNITS (Use ONLY these):
For ORAL medications (tablets, capsules, liquid): mg, ml, g, mcg, ug, iu, u, tablet, tablets, capsule, capsules, pill, pills
For IV/IM injections: mg, ml, mcg, ug, iu, units
```
- **Unit standards**: Prevent LLM from making up units
- **Context-specific**: Different units for different routes

```python
INVALID units for oral medications: liters, kg, cm, inches, %volume, dL, L
```
- **Negative examples**: Explicitly forbid common errors

```python
EXAMPLES OF CORRECT DOSAGES:
✓ Amoxicillin 500mg (not "7 liters")
✓ Paracetamol 500mg or 1 tablet (not "27 liters")
```
- **Concrete examples**: Show right vs wrong
- **User's bug**: Address specific issue (liters for oral meds)

```python
SPECIAL ATTENTION:
- CRITICAL: Never assign "liters" to oral medications like Amoxicillin or Paracetamol. These should be mg, tablets, or ml.
```
- **Emphasis**: Reinforce critical requirement
- **Direct instruction**: Clear prohibition

```python
{format_instructions}
```
- **Placeholder**: Will be replaced with Pydantic schema JSON format

#### Extract Function

```python
def extract_data(state: DocState) -> DocState:
```
- **Agent function**: Takes state, returns modified state

```python
    llm_manager = UnifiedLLMManager(provider=state.get("llm_provider"))
    doc_type = (state.get("doc_type") or "other").lower().strip()
```
- **Safe access**: `.get()` returns None if key missing
- **Chaining**: `or "other"` provides default
- **Normalization**: `.lower().strip()` for consistent comparison

```python
    if doc_type not in PROMPT_TEMPLATES:
        state["errors"].append(f"Unsupported document type for extraction: {doc_type}")
        state["trace_log"].append({"agent": "extractor", "status": "skipped", "reason": "unsupported_type"})
        return state
```
- **Early exit**: If we can't handle this doc type, skip gracefully
- **Error recording**: Add to errors list
- **Trace**: Log why we skipped

```python
    if doc_type == "prescription":
        parser = PydanticOutputParser(pydantic_object=PrescriptionSchema)
    elif doc_type == "lab_report":
        parser = PydanticOutputParser(pydantic_object=LabReportSchema)
```
- **Conditional parser**: Use correct schema for doc type
- **Dynamic dispatch**: Different schema = different validation rules

```python
    system_prompt = PROMPT_TEMPLATES[doc_type].format(
        format_instructions=parser.get_format_instructions()
    )
```
- **String formatting**: Replace `{format_instructions}` placeholder
- **`.format()`**: Python string method (older style, but works)
- **`parser.get_format_instructions()`**: Returns JSON schema as text

```python
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"Document Text:\n\n{state['raw_text']}")
    ]
```
- **Full text**: Unlike classifier, extractor needs complete document

```python
    try:
        response = llm_manager.invoke_with_fallback(messages)
        content = response.content.strip()
```
- **LLM call**: Get structured extraction

```python
        data_to_parse = content
        start = content.find('{')
        end = content.rfind('}')
```
- **`.find('{')`**: Find first occurrence of `{` (returns index or -1)
- **`.rfind('}')`**: Find LAST occurrence of `}` (reverse find)
- **Purpose**: Extract JSON from text that might have extra explanation

```python
        if start != -1 and end != -1:
            clean_content = content[start:end+1]
```
- **Slice**: `[start:end+1]` - from first `{` to last `}` (inclusive)
- **Example**: `"Here's the data: {\"name\": \"test\"} hope it helps"` → `{\"name\": \"test\"}`

```python
            try:
                json_data = json.loads(clean_content)
```
- **Parse JSON**: Convert string to Python dict

```python
                if "data" in json_data and isinstance(json_data["data"], dict):
                    data_to_parse = json.dumps(json_data["data"])
                    stored_confidence = float(json_data.get("confidence_score", 0.7))
```
- **Wrapped format**: LLM might return `{"data": {...}, "confidence_score": 0.9}`
- **Unwrap**: Extract just the data part
- **`isinstance(..., dict)`**: Type checking - ensure data is a dictionary

```python
                else:
                    stored_confidence = None
            except json.JSONDecodeError:
                stored_confidence = None
```
- **JSON error**: If parsing fails, continue with original content

```python
        parsed_data = parser.parse(data_to_parse)
```
- **Pydantic parsing**: Convert to PrescriptionSchema or LabReportSchema object

```python
        state["extracted_data"] = parsed_data.model_dump(exclude_none=False)
```
- **`.model_dump()`**: Pydantic method to convert model to dictionary
- **`exclude_none=False`**: Include fields that are None (don't skip them)

```python
        if stored_confidence is not None:
            state["confidence_score"] = stored_confidence
        else:
            total_fields = len(parsed_data.model_dump())
            filled_fields = len([v for v in parsed_data.model_dump().values()
                if v is not None and v != "" and v != [] and v != {}])
            state["confidence_score"] = round(filled_fields / total_fields, 2) if total_fields > 0 else 0.5
```
- **Confidence calculation**:
  - **If LLM provided**: Use that
  - **Otherwise**: Calculate from completeness
- **List comprehension**: `[v for v in ... if ...]` - filter values
- **Conditions**: Count only non-empty values
  - `v is not None` - not missing
  - `v != ""` - not empty string
  - `v != []` - not empty list
  - `v != {}` - not empty dict
- **`round(..., 2)`**: Round to 2 decimal places (0.8571... → 0.86)

```python
    except Exception as e:
        print(f"⚠️ Structured parsing failed: {e}, trying manual JSON extraction...")
```
- **Fallback parsing**: If Pydantic fails, try simpler approach

```python
        try:
            content = response.content.strip()
            start = content.find('{')
            end = content.rfind('}')

            if start != -1 and end != -1:
                clean_content = content[start:end+1]
                extracted_resp = json.loads(clean_content)
```
- **Manual JSON extraction**: Same pattern as before

```python
                if "data" in extracted_resp:
                    state["extracted_data"] = extracted_resp["data"]
                    state["confidence_score"] = float(extracted_resp.get("confidence_score", 0.7))
                else:
                    state["extracted_data"] = extracted_resp
                    state["confidence_score"] = 0.6
```
- **Handle both formats**: Wrapped or direct

```python
        except Exception as fallback_error:
            error_msg = f"Extraction parse error: {str(e)}, Fallback error: {str(fallback_error)}"
            state["errors"].append(error_msg)
```
- **Complete failure**: Record both errors

```python
    return state
```
- **Return state**: Pass to validator

---

### Validator Agent

**File:** `app/agents/validator.py`

#### Schema Mapping

```python
SCHEMA_MAP = {
    "prescription": PrescriptionSchema,
    "lab_report": LabReportSchema
}
```
- **Dictionary**: Maps doc type string to Pydantic class
- **Purpose**: Dynamic schema selection

#### Validation Function

```python
def validate_data(state: DocState) -> DocState:
```
- **Agent function**: Standard signature

```python
    if "validation_flags" not in state:
        state["validation_flags"] = []
```
- **Initialize**: Ensure list exists before appending

```python
    if not data:
        error_msg = "No data extracted to validate."
        state["errors"].append(error_msg)
        state["trace_log"].append({
            "agent": "validator",
            "status": "skipped",
            "reason": "no_data"
        })
        return state
```
- **Defensive programming**: Handle missing data gracefully
- **Early return**: Don't continue if nothing to validate

```python
    schema_class = SCHEMA_MAP.get(doc_type)
    if not schema_class:
        error_msg = f"No validation schema for document type: {doc_type}"
        state["errors"].append(error_msg)
        ...
        return state
```
- **Schema lookup**: Get Pydantic class for this doc type
- **Unsupported**: If no schema, can't validate

```python
    try:
        validated_obj = schema_class(**data)
```
- **`**data`**: Unpacking operator - `{"name": "test"}` becomes `name="test"`
- **Pydantic validation**: Create instance, automatically validates types/constraints

```python
        state["validated_data"] = validated_obj.model_dump()
```
- **Store validated**: Pydantic may have applied defaults, type coercion

```python
        flags = []

        if doc_type == "prescription":
            flags.extend(validated_obj.check_extreme_dosage())
            flags.extend(validated_obj.check_controlled_substances())
            flags.extend(validated_obj.check_pediatric_dosing())
            flags.extend(validated_obj.check_polypharmacy())
            flags.extend(validated_obj.check_geriatric_polypharmacy())
            flags.extend(validated_obj.check_missing_dosage())
            flags.extend(validated_obj.check_unit_standards())
            flags.extend(validated_obj.check_mandatory_fields())
```
- **Method chaining**: Call all validation methods
- **`.extend(...)`**: Add all items from returned list to flags list
  - Different from `.append()` which adds single item
- **8 validation checks**: Each returns `List[dict]` of flags

```python
        elif doc_type == "lab_report":
            flags.extend(validated_obj.check_date_consistency())
            flags.extend(validated_obj.check_amended_status())
            flags.extend(validated_obj.check_critical_values())
            flags.extend(validated_obj.check_extreme_values())
            flags.extend(validated_obj.check_missing_reference_ranges())
            flags.extend(validated_obj.check_pathologist_signature())
            flags.extend(validated_obj.check_unit_standards())
            flags.extend(validated_obj.check_mandatory_fields())
```
- **Lab report checks**: Different validations for different doc type

```python
        state["validation_flags"] = flags
```
- **Replace entire list**: Not append, direct assignment

```python
    except ValidationError as e:
```
- **Pydantic ValidationError**: Schema validation failed before checks

```python
        error_flags = []
        for err in e.errors():
```
- **`.errors()`**: Pydantic method - returns list of error dictionaries

```python
            loc = err['loc']
            field_name = loc[0] if loc else "root"
```
- **`loc`**: Location tuple (e.g., `('medications', 0, 'dosage')`)
- **`loc[0]`**: Get top-level field name

```python
            error_flags.append({
                "code": f"INVALID_{field_name.upper()}",
                "message": f"Validation Error: {field_name} - {err['msg']}",
                "severity": "HIGH"
            })
```
- **Convert to flags**: Turn Pydantic errors into our flag format

---

### Redactor Agent

**File:** `app/agents/redactor.py`

#### Regex Patterns

```python
    patterns = {
        "EMAIL": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
```
- **Regex breakdown**:
  - **`\b`**: Word boundary (start/end of word)
  - **`[A-Za-z0-9._%+-]+`**: One or more alphanumeric or special chars
  - **`@`**: Literal @ symbol
  - **`[A-Za-z0-9.-]+`**: Domain name characters
  - **`\.`**: Literal dot (escaped because . means "any char" in regex)
  - **`[A-Z|a-z]{2,}`**: 2+ letters (TLD like com, org)
  - **`\b`**: End boundary

```python
        "SSN": r"\b\d{3}-\d{2}-\d{4}\b",
```
- **SSN pattern**: 123-45-6789
  - **`\d{3}`**: Exactly 3 digits
  - **`-`**: Literal hyphen
  - **`\d{2}`**: Exactly 2 digits
  - **`-`**: Literal hyphen
  - **`\d{4}`**: Exactly 4 digits

```python
        "PHONE": r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}",
```
- **Phone pattern**: Flexible format
  - **`\+?`**: Optional + (international)
  - **`1?`**: Optional 1 (US country code)
  - **`[-.\s]?`**: Optional separator (hyphen, dot, or space)
  - **`\(?`**: Optional opening parenthesis
  - **`\d{3}`**: 3 digits (area code)
  - **`\)?`**: Optional closing parenthesis
  - **Matches**: +1-555-123-4567, (555) 123-4567, 555.123.4567, etc.

```python
        "MRN": r"\bMRN\s*[:#-]?\s*[A-Z0-9]+\b",
```
- **Medical Record Number**:
  - **`\s*`**: Zero or more whitespace
  - **`[:#-]?`**: Optional separator (colon, hash, or hyphen)
  - **`[A-Z0-9]+`**: One or more uppercase letters or digits
  - **Matches**: MRN: 12345, MRN#ABC123, MRN-98765

#### LLM Redaction

```python
    system_prompt = f"""You are an advanced Privacy Compliance Expert specializing in Medical PII Redaction.
```
- **Role**: Set expertise context

```python
### MANDATORY REDACTION CATEGORIES:
1. PERSONAL IDENTIFIERS:
   - Patient names, relatives, nicknames.
   - Doctor/Provider names.
   - Addresses (Physical and Email).
   - Phone numbers.
   - Replace with: [NAME_REDACTED], [ADDRESS_REDACTED], [EMAIL_REDACTED], [PHONE_REDACTED]
```
- **Explicit instructions**: What to redact and replacement format

```python
### IMPORTANT: DO NOT REDACT THE FOLLOWING:
- **Dates**: Prescription dates, report dates, collection dates, service dates are NOT PHI and should remain visible.
- **Medical Data**: Medication names, dosages, test results, diagnoses, lab values.
- **Ages**: Patient age is allowed and should not be redacted.
```
- **Negative rules**: HIPAA allows certain data (ages, dates)
- **Critical**: Prevents over-redaction that destroys clinical utility

```python
    response = llm_manager.invoke_with_fallback(messages)
    redacted_text = response.content
```
- **LLM redaction**: Contextual - understands names even without patterns

```python
    for label, pattern in patterns.items():
        redacted_text = re.sub(pattern, f"[{label}_REDACTED]", redacted_text)
```
- **`re.sub(pattern, replacement, string)`**: Regular expression substitution
- **`.items()`**: Dictionary method - returns (key, value) pairs
- **Safety net**: Catch anything LLM missed

```python
    all_tags = re.findall(r"\[([A-Z_]+)_REDACTED\]", redacted_text)
```
- **`re.findall()`**: Return all matches as list
- **Regex**: `\[([A-Z_]+)_REDACTED\]`
  - **`\[`**: Literal opening bracket
  - **`([A-Z_]+)`**: Capture group - one or more uppercase letters or underscores
  - **`_REDACTED\]`**: Literal text
- **Example**: `"[NAME_REDACTED] [EMAIL_REDACTED]"` → `["NAME", "EMAIL"]`

```python
    pii_types_found = sorted(list(set(all_tags)))
```
- **`set(all_tags)`**: Remove duplicates (NAME, NAME, EMAIL → NAME, EMAIL)
- **`list(...)`**: Convert set back to list
- **`sorted(...)`**: Alphabetical order

---

### Reporter Agent

**File:** `app/agents/reporter.py`

#### Constants

```python
EXPECTED_FIELDS = {
    "invoice": 4,
    "id_card": 4,
    "prescription": 5,
    "lab_report": 7
}
```
- **Field counts**: For completeness calculation
- **Baseline**: Expected minimum fields per doc type

#### Generate Report

```python
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```
- **`os.path.abspath(__file__)`**: Absolute path to current file
  - Example: `C:/app/agents/reporter.py`
- **`os.path.dirname(...)`**: Get parent directory
  - First call: `C:/app/agents`
  - Second call: `C:/app`
  - Third call: `C:/` (workspace root)

```python
    reports_dir = os.path.join(base_dir, "reports")
    os.makedirs(reports_dir, exist_ok=True)
```
- **`os.path.join()`**: Platform-independent path joining (/ on Linux, \\ on Windows)
- **`os.makedirs()`**: Create directory
- **`exist_ok=True`**: Don't error if directory already exists

```python
    extracted_flat = {}
    if isinstance(extracted_data, dict):
        for k, v in extracted_data.items():
            if isinstance(v, dict):
                extracted_flat.update(v)
            else:
                extracted_flat[k] = v
```
- **Flatten nested dict**: Count all fields recursively
- **`.update(v)`**: Merge dictionary v into extracted_flat

```python
    extracted_count = float(len([v for v in extracted_flat.values() if v is not None]))
```
- **Count non-None values**: Filter out missing fields
- **`float(...)`**: Convert to decimal for division

```python
    extraction_completeness = (extracted_count / float(expected_count) * 100) if expected_count > 0 else 0
```
- **Percentage**: (actual / expected) * 100
- **Guard**: Prevent division by zero

```python
    validation_accuracy = max(0, 100 - (len(flags) * 10)) if extracted_count > 0 else 0
```
- **Penalty system**: Deduct 10 points per flag
- **`max(0, ...)`**: Floor at 0 (can't go negative)

```python
    pipeline_success = len(errors) == 0 and extracted_count > 0
```
- **Boolean**: True only if no errors AND data extracted

```python
    for log_entry in trace_log:
        if log_entry.get("agent") == "redactor":
            pii_types = log_entry.get("pii_types_scrubbed", [])
            pii_redaction_count = sum([
                redacted_text.count(f"[{pii_type}_REDACTED]")
                for pii_type in pii_types
            ])
```
- **Find redactor entry**: Filter trace log
- **`sum([...])`**: Add up all counts
- **`.count(...)`**: String method - count occurrences

```python
    redaction_coverage = (pii_redaction_count / len(raw_text.split())) * 100 if raw_text else 0
```
- **Coverage**: (redacted items / total words) * 100
- **`.split()`**: Split on whitespace into words

```python
    for log_entry in trace_log:
        agent = log_entry.get("agent", "unknown")
        status = log_entry.get("status", "unknown")
        if agent not in agent_performance:
            agent_performance[agent] = {"success": 0, "failed": 0, "skipped": 0}
```
- **Aggregate stats**: Count successes/failures per agent
- **Initialize**: Create dict structure if first time seeing this agent

```python
        if status in ["passed", "success", "completed"]:
            agent_performance[agent]["success"] += 1
        elif status == "failed":
            agent_performance[agent]["failed"] += 1
        elif status == "skipped":
            agent_performance[agent]["skipped"] += 1
```
- **Categorize**: Increment appropriate counter

```python
    with open(trace_path, "w") as f:
        json.dump(report, f, indent=4)
```
- **`with open(...) as f:`**: Context manager - auto-closes file
- **`"w"`**: Write mode (creates or overwrites)
- **`json.dump(report, f, indent=4)`**: Write JSON with 4-space indentation

```python
    import csv
    with open(metrics_csv_path, "a", newline="") as csvfile:
```
- **`"a"`**: Append mode (add to end of file)
- **`newline=""`**: Prevent extra blank lines on Windows

```python
        fieldnames = ["timestamp", "doc_type", "file_path", ...]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
```
- **`DictWriter`**: Write dictionaries as CSV rows
- **`fieldnames`**: Column order

```python
        if not file_exists:
            writer.writeheader()
```
- **Write header**: Only on first row (column names)

```python
        writer.writerow({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            ...
        })
```
- **`time.strftime()`**: Format timestamp
- **`%Y`**: 4-digit year, **`%m`**: month, **`%d`**: day, **`%H`**: hour (24h), **`%M`**: minute, **`%S`**: second

---

## Schemas

### Prescription Schema

**File:** `app/schemas/prescription_schema.py`

#### Pydantic Models

```python
class DoctorInfo(BaseModel):
    name: Optional[str] = Field(None, description="Name of the prescribing doctor")
```
- **`Optional[str]`**: Can be string or None
- **`= Field(None, ...)`**: Default value is None
- **`description`**: Used by PydanticOutputParser to guide LLM

```python
    dea_number: Optional[str] = Field(
        None, description="DEA Number (Required for controlled substances) - Format: 2 letters + 7 digits (e.g., AB1234563)")
```
- **Detailed description**: Includes format specification for LLM

```python
class Medication(BaseModel):
    refills: Optional[int] = Field(0, description="Number of refills allowed")
```
- **Default value**: 0 (not None) - if missing, assume 0 refills

```python
    @field_validator('dosage')
    @classmethod
    def validate_dosage_format(cls, v: Optional[str]) -> Optional[str]:
        """Accept any dosage format - validation flags are generated by validator agent."""
        return v
```
- **`@field_validator('dosage')`**: Decorator - runs this function when validating dosage field
- **`@classmethod`**: Method receives class (cls) not instance (self)
- **`v`**: The value being validated
- **`-> Optional[str]`**: Must return same type
- **Logic**: Just return value unchanged (lenient validation)
- **Why**: User requirement - don't reject data, just flag issues

#### Validation Methods

```python
    def check_extreme_dosage(self) -> List[dict]:
        """Flag dosages > 5000mg as LIFE THREATENING."""
        flags = []
```
- **Return type**: `List[dict]` - list of flag dictionaries
- **Initialize**: Empty list to collect flags

```python
        for med in self.medications:
            if not med.dosage:
                continue
```
- **Loop**: Iterate through all medications
- **`continue`**: Skip to next iteration if dosage is missing

```python
            try:
                match = re.search(r"(\d+(\.\d+)?)", med.dosage)
```
- **Regex**: `(\d+(\.\d+)?)`
  - **`\d+`**: One or more digits
  - **`(\.\d+)?`**: Optional decimal part
    - **`\.`**: Literal dot
    - **`\d+`**: One or more digits
    - **`?`**: Makes entire group optional
  - **Matches**: 500, 500.5, 1000.25
- **`re.search()`**: Find first match (returns Match object or None)

```python
                if match:
                    val = float(match.group(1))
```
- **`.group(1)`**: Get first capture group (the number)
- **`float(...)`**: Convert string to decimal

```python
                    if val > 5000:
                        flags.append({
                            "code": "EXTREME_DOSAGE",
                            "message": f"Life-threatening dosage: {med.dosage} exceeds 5000mg safety limit.",
                            "severity": "CRITICAL"
                        })
```
- **Threshold**: 5000mg is dangerous
- **Flag structure**: code, message, severity

```python
            except (ValueError, TypeError):
                continue
```
- **Error handling**: If conversion fails, skip this medication
- **Tuple of exceptions**: Catch multiple error types

```python
    def check_controlled_substances(self) -> List[dict]:
        controlled_drugs = ["morphine", "oxycodone", "fentanyl", ...]
```
- **Drug list**: Schedule II-V controlled substances

```python
        has_controlled = any(
            any(drug in (med.name.lower() if med.name else "")
                for drug in controlled_drugs)
            for med in self.medications
        )
```
- **Nested `any()`**: 
  - **Outer**: Any medication has controlled substance
  - **Inner**: Any drug name matches this medication
- **Generator expressions**: Lazy evaluation for efficiency
- **`(med.name.lower() if med.name else "")`**: Ternary operator - avoid None.lower() error

```python
        if has_controlled:
            dea = self.doctor.dea_number
            if not dea or dea == "null" or dea == "":
                flags.append({
                    "code": "CONTROLLED_SUBSTANCE_NO_DEA",
                    "message": "Controlled substance detected but Physician DEA Number is MISSING. Federal requirement for Schedule II-V medications.",
                    "severity": "CRITICAL"
                })
```
- **Legal requirement**: DEA number mandatory for controlled substances
- **Multiple checks**: Missing, null string, empty string

```python
            elif not re.match(r"^[A-Z][A-Z9][0-9]{7}$", dea):
```
- **DEA format regex**: `^[A-Z][A-Z9][0-9]{7}$`
  - **`^`**: Start of string
  - **`[A-Z]`**: First character - uppercase letter
  - **`[A-Z9]`**: Second character - uppercase letter or digit 9
  - **`[0-9]{7}`**: Exactly 7 digits
  - **`$`**: End of string
- **`re.match()`**: Check if ENTIRE string matches pattern

```python
    def check_pediatric_dosing(self) -> List[dict]:
        age = self.patient.age
        weight = self.patient.weight

        if age is not None and age < 12:
```
- **Pediatric**: Under 12 years old
- **`is not None`**: Explicit None check (age could be 0)

```python
            if not weight:
                flags.append({
                    "code": "PEDIATRIC_DOSING",
                    "message": f"Pediatric patient (Age {age}) - MISSING WEIGHT for clinical validation.",
                    "severity": "MEDIUM"
                })
```
- **Weight-based dosing**: Critical for children

```python
            weight_ranges = {
                (0, 1): (3, 12),      # Infants: 3-12 kg
                (1, 3): (10, 16),     # Toddlers: 10-16 kg
                (3, 6): (14, 22),     # Preschool: 14-22 kg
                (6, 12): (20, 45)     # School age: 20-45 kg
            }
```
- **Dictionary**: Keys are age ranges (tuples), values are weight ranges
- **Clinical guidelines**: Normal weight by age group

```python
            for (min_age, max_age), (min_weight, max_weight) in weight_ranges.items():
```
- **Tuple unpacking**: Extract both keys and values
- **`(min_age, max_age)`**: Unpack age range tuple
- **`(min_weight, max_weight)`**: Unpack weight range tuple

```python
                if min_age <= age < max_age:
```
- **Range check**: Age between min (inclusive) and max (exclusive)

```python
                    if weight < min_weight or weight > max_weight:
                        flags.append({...})
                    break
```
- **`break`**: Exit loop once correct age range found

```python
            pediatric_contraindicated = {
                "atorvastatin": "Statin typically contraindicated in young children",
                "aspirin": "Risk of Reye's syndrome in children under 12",
                ...
            }
```
- **Dictionary**: Drug → reason for contraindication
- **Medical knowledge**: Age-specific safety concerns

```python
            for med in self.medications:
                med_name_lower = (med.name or "").lower()
                for contraindicated_drug, reason in pediatric_contraindicated.items():
                    if contraindicated_drug in med_name_lower:
                        flags.append({
                            "code": "PEDIATRIC_CONTRAINDICATED_MED",
                            "message": f"Pediatric patient (Age {age}) prescribed {med.name} - {reason}. Clinical review required.",
                            "severity": "HIGH"
                        })
                        break
```
- **Substring match**: "atorvastatin calcium" contains "atorvastatin"
- **`break`**: Don't check other drugs once match found

```python
            if weight:
                for med in self.medications:
                    dosage_str = med.dosage or ""
                    med_name_lower = (med.name or "").lower()

                    match = re.search(r"(\d+(\.\d+)?)", dosage_str)
                    if match:
                        dosage_val = float(match.group(1))
```
- **Extract dosage**: Same regex pattern as before

```python
                        if "paracetamol" in med_name_lower or "acetaminophen" in med_name_lower:
                            if "mg" in dosage_str.lower():
                                max_safe_dose = weight * 15  # 15mg/kg
                                if dosage_val > max_safe_dose:
                                    flags.append({...})
```
- **Weight-based calculation**: 15mg per kilogram
- **Example**: 20kg child → 300mg max safe dose
- **Hepatotoxicity**: Overdose damages liver

```python
    def check_polypharmacy(self) -> List[dict]:
        med_count = len(self.medications) if self.medications else 0

        if med_count >= 10:
            flags.append({
                "code": "EXCESSIVE_POLYPHARMACY",
                "severity": "HIGH"
            })
        elif med_count >= 6:
            flags.append({
                "code": "POLYPHARMACY_RISK",
                "severity": "MEDIUM"
            })
```
- **Polypharmacy**: Multiple medications increase interaction risk
- **Thresholds**: 6-9 = MEDIUM, 10+ = HIGH
- **User requirement**: From earlier conversation

```python
    def check_unit_standards(self) -> List[dict]:
        valid_units = ["mg", "ml", "g", "mcg", ...]
        invalid_critical_units = ["liters", "liter", "l", "kg", "kgs", "cm", "inches"]
```
- **Two lists**: Valid vs invalid units
- **User's bug**: "liters" was being extracted for oral medications

```python
        for med in self.medications:
            dosage_str = med.dosage
            if not dosage_str:
                continue

            match = re.search(r"[0-9\.]+\s*([a-zA-Z/]+)", dosage_str)
```
- **Regex**: `[0-9\.]+\s*([a-zA-Z/]+)`
  - **`[0-9\.]+`**: One or more digits or dots
  - **`\s*`**: Optional whitespace
  - **`([a-zA-Z/]+)`**: Capture group - letters or slashes (the unit)
- **Example**: "500 mg" → captures "mg", "5ml" → captures "ml"

```python
            if match:
                unit = match.group(1).lower()

                if unit in invalid_critical_units:
                    flags.append({
                        "code": "INVALID_DOSAGE_UNIT",
                        "message": f"CRITICAL: Invalid dosage unit '{unit}' in '{med.name}: {dosage_str}'. This unit is inappropriate for medication dosing and requires clinical review.",
                        "severity": "HIGH"
                    })
```
- **Critical flag**: High severity for dangerous units
- **User requirement**: Flag but don't repair

---

### Lab Report Schema

**File:** `app/schemas/lab_report_schema.py`

```python
class LabInfo(BaseModel):
    has_pathologist_signature: bool = Field(
        False, description="Whether a digital or physical signature is present")
```
- **Boolean field**: True/False
- **Default**: False (assume no signature unless found)

```python
class TestResult(BaseModel):
    value: Optional[Union[float, str]] = Field(
        None, description="Result value")
```
- **`Union[float, str]`**: Can be either type
- **Why**: Some results are numeric (14.5), others text ("Positive")

```python
    @field_validator('status')
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v is None:
            return v
        allowed = ["normal", "high", "low", "critical", "extreme", "panic"]
        if v.lower() not in allowed:
            pass  # For now, allow it
        return v
```
- **Lenient validation**: Allow non-standard values
- **`pass`**: Empty statement (do nothing)

```python
    def check_date_consistency(self) -> List[dict]:
        def parse_any_date(date_str: Optional[str]) -> Optional[datetime]:
            if not date_str:
                return None
            formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y/%m/%d', '%b %d, %Y', '%d %b %Y']
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            return None
```
- **Nested function**: Helper function inside method
- **Multiple formats**:
  - **`%Y-%m-%d`**: 2026-02-13 (ISO format)
  - **`%m/%d/%Y`**: 02/13/2026 (US format)
  - **`%d/%m/%Y`**: 13/02/2026 (European format)
  - **`%b %d, %Y`**: Feb 13, 2026 (month name)
- **Try each**: Return first successful parse

```python
        coll = parse_any_date(self.collection_date)
        rep = parse_any_date(self.report_date)

        if coll and rep and rep < coll:
```
- **`and`**: All conditions must be true
- **`rep < coll`**: Report date before collection date (logic error)

```python
    def check_critical_values(self) -> List[dict]:
        for res in self.test_results:
            status_lower = res.status.lower() if res.status else ""
            if any(key in status_lower for key in ["critical", "panic", "immediate"]):
```
- **`any(...)`**: True if at least one condition is true
- **Generator expression**: `key in status_lower for key in [...]`
- **Matches**: "Critical", "CRITICAL HIGH", "Panic value"

```python
    def check_missing_reference_ranges(self) -> List[dict]:
        invalid_ranges = ["n/a", "na", "null", "none", "", "-", "not available", "pending"]
```
- **User requirement**: Flag N/A reference ranges
- **Multiple variants**: Different ways to express "missing"

```python
        for res in self.test_results:
            ref_range = res.reference_range

            if not ref_range or ref_range.lower().strip() in invalid_ranges:
```
- **`.strip()`**: Remove leading/trailing whitespace
- **Two conditions**: Missing OR invalid value

```python
                flags.append({
                    "code": "MISSING_REFERENCE_RANGE",
                    "message": f"Clinical interpretation limited: Test '{res.test_name}' is missing a reference range. Cannot determine if value is normal without comparative range.",
                    "severity": "MEDIUM"
                })
```
- **Clinical impact**: Can't interpret test without reference range

```python
    def check_extreme_values(self) -> List[dict]:
        for res in self.test_results:
            if not res.reference_range or res.value is None:
                continue

            val_str = str(res.value).lower()
            if "pending" in val_str or "tbd" in val_str:
                continue
```
- **Skip pending**: Not yet resulted, can't evaluate

```python
            try:
                val_num = float(res.value) if isinstance(res.value, (int, float, str)) else 0.0
```
- **Type check**: `isinstance(res.value, (int, float, str))`
- **Type conversion**: Ensure numeric for comparison

```python
                ranges = re.findall(r"(\d+(\.\d+)?)", str(res.reference_range))
```
- **`re.findall()`**: Return ALL matches (not just first)
- **Example**: "12.0 - 18.0" → `[('12.0', '.0'), ('18.0', '.0')]`

```python
                if len(ranges) >= 2:
                    upper_bound = float(ranges[-1][0])
```
- **`ranges[-1]`**: Last match (right side of range)
- **`[0]`**: First capture group (the number)

```python
                    if val_num > (3 * upper_bound):
                        flags.append({
                            "code": "EXTREME_VALUE",
                            "message": f"LAB ERROR/RETEST REQUIRED: {res.test_name} value ({val_num}) is >3x normal.",
                            "severity": "HIGH"
                        })
```
- **3x rule**: Value > 3 times upper limit suggests error
- **Clinical**: May indicate pre-analytical error (hemolysis, contamination)

---

## Summary

This medical document processing system uses:

1. **TypedDict State**: Shared data structure flows through pipeline
2. **Multi-Provider LLM**: Ollama (local), Groq (cloud), Bedrock (AWS) with automatic fallback
3. **Agent Pipeline**: Classifier → Extractor → Validator → Redactor → Reporter
4. **Pydantic Schemas**: Type validation with clinical validation methods
5. **Regex + LLM Hybrid**: Structured patterns + contextual understanding
6. **Separation of Concerns**: Schema validates structure, check methods flag clinical issues

**Key Design Decisions:**
- Lenient schema validation (accept any dosage format)
- Clinical validation generates flags (not rejections)
- Defensive programming (early returns, None checks)
- Comprehensive error handling (try/except with fallbacks)
- Audit trail (trace_log for responsible AI)

**Regex Patterns:**
- Email: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b`
- Phone: `\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}`
- Dosage extraction: `(\d+(\.\d+)?)` 
- Unit extraction: `[0-9\.]+\s*([a-zA-Z/]+)`
- DEA validation: `^[A-Z][A-Z9][0-9]{7}$`

---

# NEW FEATURES & ARCHITECTURE (v2.0)

## Repair Agent

**File:** `app/agents/repair.py`

### Purpose
Automatically corrects invalid or non-standard medical units detected by the validator agent using LLM-based intelligent reasoning.

### When It Runs
The repair agent is conditionally triggered when validation flags indicate:
- `INVALID_DOSAGE_UNIT` (HIGH severity) - e.g., "liters" instead of "mg"
- `NON_STANDARD_UNIT` (MEDIUM severity) - e.g., "cc" instead of "ml"

### Core Function: `repair_data(state: DocState) -> DocState`

```python
def repair_data(state: DocState) -> DocState:
```
- **Input**: Current pipeline state with validation flags
- **Output**: Updated state with repaired data and repair summary
- **Side Effects**: Logs repair actions to trace_log

**Key Steps:**

1. **Check if repair needed**:
```python
validation_flags = state.get("validation_flags", [])
flags_to_repair = [
    flag for flag in validation_flags
    if flag.get("code") in ["INVALID_DOSAGE_UNIT", "NON_STANDARD_UNIT"]
]
```
- Filters only repairable unit errors
- Other flags (dosage ranges, drug interactions) not auto-repaired

2. **Initialize LLM**:
```python
llm_provider = state.get("llm_provider", "groq")
manager = UnifiedLLMManager.get_instance()
llm = manager.get_llm(provider=llm_provider)
```
- Uses same provider selection as extraction
- Reuses singleton LLM manager for efficiency

3. **Construct intelligent prompt**:
```python
REPAIR_PROMPT = """
You are a medical data correction specialist...
CRITICAL OUTPUT FORMAT RULES:
1. Output ONLY valid JSON. No markdown, no comments.
2. NEVER include JSON comments like "// Corrected from..."
"""
```
- Instructs LLM on medical unit conversion rules
- Enforces strict JSON output (no comments that break parsing)
- Provides context about medication type to ensure appropriate units

4. **Parse LLM response**:
```python
if "```json" in response_text:
    json_match = re.search(r"```json\s*\n(.*?)\n```", response_text, re.DOTALL)
    if json_match:
        json_str = json_match.group(1)
else:
    json_str = response_text.strip()

repaired = json.loads(json_str)
```
- Handles both raw JSON and markdown-wrapped JSON
- Defensive parsing with fallback

5. **Create repair summary**:
```python
state["repair_summary"] = {
    "flags_repaired": flags_to_repair,
    "original_data": original_data,
    "repaired_data": repaired_data,
    "reasoning": reasoning
}
```
- Stores both original and repaired data for human review
- Captures LLM's reasoning for transparency

### Router Function: `should_repair(state: DocState) -> str`

```python
def should_repair(state: DocState) -> str:
    validation_flags = state.get("validation_flags", [])
    
    for flag in validation_flags:
        if flag.get("code") in ["INVALID_DOSAGE_UNIT", "NON_STANDARD_UNIT"]:
            return "repair"
    
    return "redactor"
```
- **Conditional edge** in graph routing
- Returns `"repair"` if fixable unit errors exist
- Returns `"redactor"` to skip repair if no issues

**Why This Design?**
- **Separation of concerns**: Validation detects, repair fixes
- **Transparency**: LLM explains its reasoning
- **Auditability**: Original data preserved alongside repairs
- **Human-in-the-loop ready**: Repair summary enables review interface

---

## Graph Architecture

**File:** `app/graph.py`

### Dual Graph System

The system now uses **two separate graph compilations** to support both automatic and human-reviewed workflows:

```python
# Standard graph - automatic processing
app = workflow.compile()

# Human-in-the-loop graph - with interrupts and checkpointing
from langgraph.checkpoint.memory import MemorySaver
checkpointer = MemorySaver()

app_with_review = workflow.compile(
    checkpointer=checkpointer,
    interrupt_after=["repair"]
)
```

#### Why Two Graphs?

**Technical Limitation**: LangGraph's interrupt mechanism is a **compile-time configuration**, not runtime. You cannot toggle interrupts on/off for the same graph instance.

**Solution**: Maintain two compiled graphs:
1. **`app`** - No interrupts, runs start-to-finish automatically
2. **`app_with_review`** - Includes checkpointer and pauses after repair node

#### Graph Components

**Nodes (Agents)**:
```python
workflow.add_node("classifier", classify)
workflow.add_node("extractor", extract)
workflow.add_node("validator", validate)
workflow.add_node("repair", repair_data)     # NEW
workflow.add_node("redactor", redact)
workflow.add_node("reporter", report)
```

**Edges (Flow)**:
```python
# Linear flow
workflow.add_edge(START, "classifier")
workflow.add_edge("classifier", "extractor")
workflow.add_edge("extractor", "validator")

# Conditional routing - validator checks if repair needed
workflow.add_conditional_edges(
    "validator",
    should_repair,
    {
        "repair": "repair",
        "redactor": "redactor"
    }
)

# Repair loops back to validator for re-validation
workflow.add_edge("repair", "validator")

# Continue to completion
workflow.add_edge("redactor", "reporter")
workflow.add_edge("reporter", END)
```

**Flow Diagram**:
```
START → classifier → extractor → validator
                                    ↓
                            [should_repair?]
                           /                \
                      YES: repair          NO: redactor
                           ↓                    ↓
                       validator            reporter
                           ↓                    ↓
                    [should_repair?]          END
                      (usually NO)
                           ↓
                      redactor
                           ↓
                      reporter
                           ↓
                         END
```

### Workflow Routing

**Automatic Mode (`app` graph)**:
1. Processes document start-to-finish
2. If repair needed, automatically applies fixes
3. Re-validates to ensure repair worked
4. Continues through redaction and reporting
5. Returns complete result

**Human Review Mode (`app_with_review` graph)**:
1. Processes through validator
2. If repair needed, applies fixes and **PAUSES** (interrupt)
3. Returns `status: "interrupted"` with repair summary
4. Waits for human decision via `/repair/approve` endpoint
5. On approval, resumes from checkpoint and completes pipeline
6. On rejection, reverts to original data and completes pipeline

**Checkpointer Mechanism**:
```python
config = {"configurable": {"thread_id": "thread_12345"}}
```
- **`MemorySaver`**: In-memory state persistence (lost on restart)
- **`thread_id`**: Unique identifier for each processing session
- Enables resuming from exact point of interruption

---

## API Endpoints

**File:** `api.py`

### Standard Processing

#### `POST /process`
**Purpose**: Standard automatic processing without interrupts

```python
@api.post("/process", response_model=ProcessResponse)
async def process_document(
    file: UploadFile = File(...),
    llm_provider: str = "ollama"
):
```

**Uses**: `langgraph_pipeline` (the `app` graph)

**Flow**:
1. Parse PDF
2. Initialize state
3. Run through entire pipeline automatically
4. Return complete results

**Response**:
```json
{
  "doc_type": "prescription",
  "validated_data": {...},
  "redacted_text": "...",
  "latency_ms": 2341.56,
  "trace": [...],
  "errors": [],
  "validation_flags": [...]
}
```

### Human-in-the-Loop API

#### `POST /process/with-review`
**Purpose**: Process with interrupt for human review of repairs

```python
@api.post("/process/with-review", response_model=InterruptResponse)
async def process_with_human_review(
    file: UploadFile = File(...),
    llm_provider: str = "groq"
):
```

**Uses**: `langgraph_pipeline_with_review` (the `app_with_review` graph)

**Flow**:
1. Parse PDF and initialize state
2. Generate unique thread_id for checkpointing
3. Run graph with interrupt config
4. If repair triggered, graph pauses and returns interrupt response
5. Human reviews via frontend
6. Continue via `/repair/approve` endpoint

**Interrupted Response**:
```json
{
  "status": "interrupted",
  "thread_id": "thread_1770976674",
  "interrupted_at": "repair",
  "repair_summary": {
    "flags_repaired": [...],
    "original_data": {...},
    "repaired_data": {...},
    "reasoning": "Converting 'liters' to 'mg' because..."
  },
  "message": "Repair completed. Please review..."
}
```

**Completed Without Repair Response**:
```json
{
  "status": "completed",
  "thread_id": "thread_1770976674",
  "interrupted_at": null,
  "repair_summary": null,
  "current_state": {
    "doc_type": "prescription",
    "validated_data": {...}
  },
  "message": "Processing completed without requiring repairs."
}
```

#### `GET /repair/status/{thread_id}`
**Purpose**: Check current status of an interrupted workflow

**Returns**: Same structure as interrupt response with current state

#### `POST /repair/approve`
**Purpose**: Continue processing after human decision

```python
class ApprovalRequest(BaseModel):
    thread_id: str
    approved: bool
    modified_data: Optional[dict] = None
```

**Three decision paths**:

1. **Approve** (`approved=True`):
   - Use repaired data
   - Continue processing
   - Log approval in trace

2. **Reject** (`approved=False`, no `modified_data`):
   - Revert to original extracted data
   - Continue processing
   - Log rejection in trace

3. **Manual Override** (`approved=False`, with `modified_data`):
   - Use human's custom JSON
   - Continue processing
   - Log manual correction in trace

**Implementation**:
```python
if not request.approved:
    if request.modified_data:
        # Manual override
        current_state["extracted_data"] = request.modified_data
    else:
        # Revert to original
        original_data = repair_summary.get("original_data", {})
        current_state["extracted_data"] = original_data

# Update state and resume
langgraph_pipeline_with_review.update_state(config, current_state)
final_state = langgraph_pipeline_with_review.invoke(None, config)
```

**Why `invoke(None, ...)`?**
- `None` means "resume from checkpoint, don't start over"
- Config contains thread_id pointing to saved state
- Graph continues from interrupt point

### Removed: Streaming Endpoint

**Previously**: `POST /process/stream` with Server-Sent Events (SSE)

**Removed because**:
1. Added complexity without significant benefit
2. Incompatible with interrupt workflow (state snapshot incomplete)
3. Frontend can't display intermediate partial results meaningfully
4. Simpler to use spinner + complete results

---

## Frontend Interface

**File:** `streamlit_app.py`

### Human Review UI

**Toggle Control**:
```python
enable_human_review = st.toggle(
    "Enable Human Review",
    value=False,
    help="Enable manual review and approval of AI-suggested repairs"
)
```

**Visual Feedback**:
```python
if enable_human_review:
    st.success("✅ Human Review ENABLED - You will review all repairs")
else:
    st.info("ℹ️ Auto-Repair Mode - AI will automatically fix issues")
```

**Expandable Help**:
- Explains what human review mode does
- Lists common scenarios that trigger review
- Describes when to use this feature

### Repair Review Screen

**Triggered when**: `result.get("status") == "interrupted"`

**Layout**:

1. **Header Section**:
```python
st.markdown("## ⏸️ PROCESSING PAUSED FOR HUMAN REVIEW")
st.info("🔍 The AI detected issues and applied automatic repairs...")
```

2. **Issues Detected**:
```python
flags_repaired = repair_summary.get("flags_repaired", [])
for flag in flags_repaired:
    severity = flag.get("severity", "UNKNOWN")
    severity_color = {"HIGH": "🟠", "MEDIUM": "🟡"}
    st.markdown(f"{severity_color} **{flag.get('code')}** ({severity})")
```

3.**AI Reasoning**:
```python
reasoning = repair_summary.get("reasoning", "No reasoning provided")
st.markdown(f"""
<div style="padding: 15px; background-color: #1e3a5f; border-left: 4px solid #3b82f6;">
    <p><strong>Why the AI made these changes:</strong></p>
    <p>{reasoning}</p>
</div>
""", unsafe_allow_html=True)
```

4. **Before/After Comparison**:
```python
col1, col2 = st.columns(2)

with col1:
    st.markdown("#### ❌ Original Data")
    st.json(original_data)

with col2:
    st.markdown("#### ✅ AI-Repaired Data")
    st.json(repaired_data)
```

### Decision Options

**Three-column button layout**:

#### Option 1: Approve Repair
```python
st.markdown("**✅ Accept AI Fix**")
st.caption("Use the AI-corrected data and continue processing")
approve_clicked = st.button("Approve Repair", type="primary")

if approve_clicked:
    approval_response = requests.post(
        "http://localhost:8000/repair/approve",
        json={"thread_id": thread_id, "approved": True}
    )
    st.success("✅ Repair approved!")
    st.rerun()  # Refresh to show final results
```

#### Option 2: Reject & Revert
```python
st.markdown("**❌ Keep Original**")
st.caption("Reject AI changes and use original data as-is")
reject_clicked = st.button("Reject & Revert")

if reject_clicked:
    rejection_response = requests.post(
        "http://localhost:8000/repair/approve",
        json={"thread_id": thread_id, "approved": False}
    )
    st.warning("⚠️ Repair rejected. Continued with original data.")
    st.rerun()
```

#### Option 3: Manual Override
```python
st.markdown("**✏️ Custom Edit**")
st.caption("Manually edit the data yourself")
manual_override = st.button("Manual Override")

if manual_override:
    manual_data_str = st.text_area(
        "Edit Medical Data (JSON Format)",
        value=json.dumps(repaired_data, indent=2),
        height=400
    )
    
    if st.button("📤 Submit Override"):
        manual_data = json.loads(manual_data_str)  # Validate JSON
        
        override_response = requests.post(
            "http://localhost:8000/repair/approve",
            json={
                "thread_id": thread_id,
                "approved": False,
                "modified_data": manual_data
            }
        )
        st.success("✅ Manual override applied!")
        st.rerun()
```

**Error Handling**:
```python
except json.JSONDecodeError as e:
    st.error(f"❌ Invalid JSON format: {str(e)}")
    st.warning("💡 Please check your JSON syntax...")
```

**Page Control**:
```python
st.stop()  # Prevent showing results tabs until decision made
```
- Stops Streamlit execution at review screen
- After decision + `st.rerun()`, full results display

---

## Contextual Knowledge

### Medical Domain Context

#### Medication Dosage Units - Why This Matters

**Common Valid Units**:
- **Solid medications**: mg, g, mcg (micrograms), IU (international units)
- **Liquid medications**: ml, L (liters for IV fluids only)
- **Inhaled**: puffs, inhalations
- **Topical**: grams, applications

**Invalid/Dangerous Units**:
- **"liters" for oral tablets**: Physically impossible (would be asking patient to consume solid mass)
- **Why LLMs make this error**: 
  - Training data includes varied contexts (chemistry, cooking, etc.)
  - May confuse liquid formulations with solid doses
  - Lacks medical domain-specific constraints

**Example Error Scenario**:
```json
{
  "medication": "Amoxicillin",
  "dosage": "7",
  "unit": "liters"  // ❌ ERROR - Amoxicillin is a tablet/capsule
}
```

**Correct Repair**:
```json
{
  "medication": "Amoxicillin",
  "dosage": "500",
  "unit": "mg"  // ✅ FIXED - Standard adult dose
}
```

**Repair Agent's Medical Knowledge**:
- Knows common medication forms (Amoxicillin = antibiotic = tablet)
- Applies clinical reasoning: "7 liters is impossible for oral medication"
- Uses dosage magnitude to infer intended unit: "7 liters" → likely "500mg" or "7 ml" depending on formulation

#### Lab Test Reference Ranges

**Why Validation Matters**:
- Lab results outside reference ranges indicate disease
- Extreme values (>3x normal) suggest pre-analytical errors
- False alerts harm patient care (unnecessary treatment)

**Clinical Significance Levels**:
```python
if val_num < lower_bound * 0.5 or val_num > upper_bound * 2:
    severity = "HIGH"  # Clinically significant abnormality
elif val_num < lower_bound or val_num > upper_bound:
    severity = "MEDIUM"  # Mild abnormality, may be normal variant
```

**Why Not Auto-Repair Lab Values?**
- Cannot know if abnormal value is real disease vs. extraction error
- Requires clinical judgment (comparing to patient's prior results)
- Repair agent only fixes **obvious extraction errors** (unit mistakes)

#### HIPAA/PHI Redaction

**Protected Health Information (PHI)**:
- Names (patient, doctor, family)
- Medical Record Numbers (MRN)
- Dates (except year)
- Contact info (phone, email, address)
- License numbers (DEA, state medical license)

**Why Full Redaction Required**:
- HIPAA compliance for data sharing
- De-identification for research/training datasets
- Privacy protection in logs/traces

**Redaction Strategy**:
```python
redacted_text = re.sub(email_pattern, "[EMAIL_REDACTED]", text)
redacted_text = re.sub(phone_pattern, "[PHONE_REDACTED]", text)
```
- Pattern-based replacement (fast, deterministic)
- LLM-based NER would be slower but more accurate
- Trade-off: Speed vs. catching edge cases

### Design Philosophy

#### 1. Extract-Validate-Repair Pipeline

**Why Not Fix During Extraction?**

❌ **Old Approach** (Don't Do This):
```python
# Extractor trying to fix issues inline
if unit == "liters" and medication_type == "tablet":
    unit = "mg"  # Silently "fixing" data
```

**Problems**:
- Hides errors (you don't know extraction was wrong)
- No audit trail
- Cannot offer human review
- Mixes concerns (extraction + validation + correction)

✅ **Current Approach** (Separation of Concerns):
```python
# 1. Extractor: Extract exactly what LLM sees
extracted = {"dosage": "7", "unit": "liters"}

# 2. Validator: Flag the issue
flags.append({"code": "INVALID_DOSAGE_UNIT", "severity": "HIGH"})

# 3. Repair: Fix with reasoning
repaired = {"dosage": "500", "unit": "mg"}
reasoning = "Converted implausible 'liters' to standard oral dose 'mg'"
```

**Benefits**:
- Transparency (can see original vs. repaired)
- Auditability (trace shows what changed and why)
- Human-in-the-loop ready (can show original + suggestion)
- Modularity (can swap repair strategies)

#### 2. Lenient Schema, Strict Validation

**Pydantic Schema**:
```python
dosage: str  # Accepts ANY string
unit: str    # Accepts ANY string
```

**Why Not Use Enums?**
```python
# ❌ Don't do this:
unit: Literal["mg", "g", "ml", "mcg"]  # Rejects unknown units
```

**Problem**: Real-world data is messy
- Typos: "mgg", "ML", "milligrams"
- Abbreviations: "millig", "milliliters"
- Non-standard: "cc", "gtt" (drops)

**Solution**: Accept everything, validate separately
```python
# Schema accepts anything
dosage: str

# Validator checks and flags
if unit.lower() not in STANDARD_UNITS:
    flags.append({
        "code": "NON_STANDARD_UNIT",
        "severity": "MEDIUM",
        "message": f"Unit '{unit}' is non-standard"
    })
```

#### 3. Flags Over Rejections

**Why Generate Flags Instead of Failing?**

❌ **Rejection Approach**:
```python
if dosage_invalid:
    raise ValueError("Invalid dosage")  # Processing stops
```

**Problem**: One field error blocks entire document

✅ **Flag Approach**:
```python
if dosage_invalid:
    flags.append({"code": "INVALID_DOSAGE", "severity": "HIGH"})
    # Processing continues
```

**Benefits**:
- Extract maximum information even from flawed documents
- Clinicians can review flags and decide importance
- Partial data better than no data in healthcare

#### 4. Interrupt-Based Human-in-the-Loop

**Why Not Callback/Webhook?**

❌ **Callback Approach**:
```python
def process_with_callback(data, callback_url):
    result = repair(data)
    requests.post(callback_url, json={"approval_needed": True})
    # Now what? Process blocks waiting for approval
```

**Problems**:
- Requires external queue/task system
- Complex state management
- What if callback fails?

✅ **LangGraph Interrupt Approach**:
```python
app_with_review = workflow.compile(
    checkpointer=MemorySaver(),
    interrupt_after=["repair"]
)
```

**How It Works**:
1. Graph executes to `repair` node
2. Saves current state to checkpointer
3. Returns control to API
4. API sends interrupt response to frontend
5. User makes decision
6. User calls `/repair/approve`
7. API resumes graph from checkpoint: `app_with_review.invoke(None, config)`
8. Graph continues from where it stopped

**Benefits**:
- Clean pause/resume semantics
- State automatically persisted
- Built into LangGraph (no external dependencies)
- Synchronous API design (easier to reason about)

#### 5. Dual Graph Architecture

**Why Not Single Graph with Runtime Toggle?**

❌ **Attempted Approach**:
```python
def process(enable_review: bool):
    if enable_review:
        # Try to enable interrupts somehow?
        graph.interrupt_after = ["repair"]  # ❌ Doesn't exist
```

**Problem**: LangGraph interrupts are **compile-time configuration**
- `interrupt_after` is a parameter to `.compile()`, not runtime
- Cannot change after graph is compiled
- Checkpointer also required at compile time

✅ **Current Solution**:
```python
# Two separately compiled graphs
app = workflow.compile()  # No interrupts
app_with_review = workflow.compile(
    checkpointer=MemorySaver(),
    interrupt_after=["repair"]
)

# API selects which graph to use
if enable_human_review:
    graph = langgraph_pipeline_with_review
else:
    graph = langgraph_pipeline
```

**Trade-offs**:
- **Pro**: Clean separation, easy to understand
- **Pro**: Both modes guaranteed to work independently
- **Con**: Two graph instances in memory (minimal overhead)
- **Con**: Must keep both in sync if workflow changes

#### 6. Defensive Programming

**Real-World Data is Messy - Expect Anything**

**Always Check Types**:
```python
# ❌ Dangerous:
medications = extracted_data["medications"]

# ✅ Safe:
medications = extracted_data.get("medications", [])
if not isinstance(medications, list):
    medications = []
```

**Early Returns**:
```python
if not validation_flags:
    return state  # Nothing to repair, exit early

if doc_type not in ["prescription", "lab_report"]:
    return state  # Can't repair unknown document types
```

**Try/Except Blocks**:
```python
try:
    repaired = json.loads(llm_response)
except json.JSONDecodeError:
    # LLM returned invalid JSON, log and continue
    state["errors"].append("Repair failed: Invalid JSON from LLM")
    return state
```

**Why This Matters in Healthcare**:
- System must degrade gracefully (partial data > crash)
- Errors must be logged for audit
- Process should complete even if one agent fails

---

**Document Version**: 2.0  
**Last Updated**: February 16, 2026  
**Changes**: Added repair agent, dual graphs, HITL workflows, contextual knowledge, removed streaming
