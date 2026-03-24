# Configuration Guide

## Overview

The application uses a centralized configuration system in [`config/settings.py`](../config/settings.py) that manages all application settings through environment variables with sensible defaults.

## Quick Start

1. **Copy the example environment file:**
   ```bash
   cp .env.example .env
   ```

2. **Edit `.env` with your settings:**
   ```bash
   # Set your LLM provider
   DEFAULT_LLM_PROVIDER=groq
   GROQ_API_KEY=your_api_key_here
   
   # Or use Ollama locally
   DEFAULT_LLM_PROVIDER=ollama
   OLLAMA_BASE_URL=http://localhost:11434
   ```

3. **Verify configuration:**
   ```bash
   python config/settings.py
   ```

## Using Configuration in Code

### Import Settings

```python
from config.settings import settings, get_settings

# Access settings
llm_provider = settings.llm.default_provider
api_port = settings.api.port
reports_dir = settings.processing.reports_dir

# Or use getter functions
from config.settings import get_llm_provider, get_reports_dir, is_debug_mode

provider = get_llm_provider()
reports = get_reports_dir()
debug = is_debug_mode()
```

### Example Usage in Agents

```python
from config.settings import settings

class MyAgent:
    def __init__(self):
        self.max_retries = settings.llm.max_retries
        self.temperature = settings.llm.temperature
        self.timeout = settings.llm.timeout
    
    def process(self):
        if settings.processing.enable_human_review:
            # Pause for human review
            pass
```

## Configuration Sections

### 1. LLM Provider Configuration

Controls which LLM provider to use and their specific settings.

**Environment Variables:**
- `DEFAULT_LLM_PROVIDER` - Default: `ollama`
- `BEDROCK_MODEL` - AWS Bedrock model ID
- `GROQ_API_KEY` - Groq API key
- `OLLAMA_BASE_URL` - Ollama server URL
- `LLM_TEMPERATURE` - Temperature for generation (0.0-1.0)
- `LLM_MAX_TOKENS` - Maximum tokens per response
- `LLM_TIMEOUT` - Request timeout in seconds
- `LLM_MAX_RETRIES` - Retry attempts on failure

**Code Access:**
```python
settings.llm.default_provider
settings.llm.groq_api_key
settings.llm.temperature
settings.llm.max_retries
```

### 2. API Configuration

FastAPI server settings.

**Environment Variables:**
- `API_HOST` - Default: `0.0.0.0`
- `API_PORT` - Default: `8000`
- `API_RELOAD` - Auto-reload for dev (true/false)
- `API_WORKERS` - Number of worker processes

**Code Access:**
```python
settings.api.host
settings.api.port
settings.api.reload
```

### 3. Streamlit UI Configuration

Streamlit application settings.

**Environment Variables:**
- `STREAMLIT_HOST` - Default: `localhost`
- `STREAMLIT_PORT` - Default: `8501`
- `STREAMLIT_THEME` - UI theme (dark/light)

**Code Access:**
```python
settings.streamlit.port
settings.streamlit.theme
```

### 4. Processing Configuration

Document processing behavior and file paths.

**Environment Variables:**
- `MAX_REPAIR_ATTEMPTS` - Default: `3`
- `ENABLE_HUMAN_REVIEW` - Enable human-in-the-loop (true/false)
- `MAX_FILE_SIZE_MB` - Maximum upload size
- `MIN_TEXT_LENGTH` - Minimum extracted text length
- `STRICT_VALIDATION` - Enable strict validation (true/false)

**Code Access:**
```python
settings.processing.max_repair_attempts
settings.processing.enable_human_review
settings.processing.reports_dir
settings.processing.labreports_dir
```

**File Paths:**
```python
# Automatically set based on project structure
settings.processing.data_dir          # data/
settings.processing.labreports_dir    # data/labreports/
settings.processing.prescriptions_dir # data/prescriptions/
settings.processing.reports_dir       # data/reports/
```

### 5. Logging Configuration

Application logging settings.

**Environment Variables:**
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- `LOG_TO_FILE` - Enable file logging (true/false)
- `LOG_MAX_SIZE_MB` - Max log file size
- `LOG_BACKUP_COUNT` - Number of backup files

**Code Access:**
```python
settings.logging.level
settings.logging.file_path
settings.logging.format
```

### 6. LangSmith Configuration

LangSmith tracing and monitoring.

**Environment Variables:**
- `LANGCHAIN_TRACING_V2` - Enable tracing (true/false)
- `LANGCHAIN_API_KEY` - LangSmith API key
- `LANGCHAIN_PROJECT` - Project name
- `LANGCHAIN_ENDPOINT` - API endpoint

**Code Access:**
```python
settings.langsmith.enabled
settings.langsmith.api_key
settings.langsmith.project
```

### 7. Metrics Configuration

Performance metrics and monitoring.

**Environment Variables:**
- `ENABLE_METRICS` - Collect metrics (true/false)
- `ENABLE_PERFORMANCE_TRACKING` - Track performance (true/false)
- `P95_LATENCY_THRESHOLD_MS` - P95 latency threshold

**Code Access:**
```python
settings.metrics.enable_metrics
settings.metrics.p95_latency_threshold_ms
settings.metrics.metrics_file
```

## Environment-Specific Configuration

### Development

```bash
ENVIRONMENT=development
DEBUG=true
DEFAULT_LLM_PROVIDER=ollama
API_RELOAD=true
LOG_LEVEL=DEBUG
```

### Staging

```bash
ENVIRONMENT=staging
DEBUG=false
DEFAULT_LLM_PROVIDER=groq
API_RELOAD=false
LOG_LEVEL=INFO
ENABLE_METRICS=true
```

### Production

```bash
ENVIRONMENT=production
DEBUG=false
DEFAULT_LLM_PROVIDER=bedrock
API_RELOAD=false
API_WORKERS=4
LOG_LEVEL=WARNING
LOG_TO_FILE=true
STRICT_VALIDATION=true
ENABLE_METRICS=true
LANGCHAIN_TRACING_V2=true
```

## Configuration Validation

The configuration system includes built-in validation:

```python
from config.settings import settings

# Check for configuration issues
issues = settings.validate_configuration()
if issues:
    for issue in issues:
        print(f"⚠️  {issue}")
```

Common validation checks:
- API keys present for selected provider
- File size limits reasonable
- Required directories exist
- LangSmith configuration complete if enabled

## Helper Functions

```python
from config.settings import (
    get_settings,
    get_llm_provider,
    get_reports_dir,
    is_debug_mode,
    is_production,
    reload_settings
)

# Get settings instance
settings = get_settings()

# Get specific values
provider = get_llm_provider()
reports = get_reports_dir()

# Check environment
if is_debug_mode():
    print("Debug logging enabled")

if is_production():
    # Production-specific behavior
    pass

# Reload settings (useful for tests)
reload_settings()
```

## Directory Management

The configuration automatically creates required directories:

```python
# Called automatically on import
settings.ensure_directories()

# Creates:
# - data/
# - data/labreports/
# - data/prescriptions/
# - data/reports/
# - logs/ (if file logging enabled)
```

## Testing with Configuration

```python
import pytest
from config.settings import reload_settings
import os

def test_with_custom_config():
    # Set test environment variables
    os.environ['DEFAULT_LLM_PROVIDER'] = 'ollama'
    os.environ['MAX_REPAIR_ATTEMPTS'] = '5'
    
    # Reload settings
    settings = reload_settings()
    
    # Assert configuration
    assert settings.llm.default_provider == 'ollama'
    assert settings.processing.max_repair_attempts == 5
```

## Best Practices

1. **Never commit `.env` files** - Contains sensitive API keys
2. **Use `.env.example`** - Document all available options
3. **Validate on startup** - Check configuration before running
4. **Use type hints** - Pydantic provides automatic validation
5. **Environment-specific configs** - Use different settings per environment
6. **Default values** - Provide sensible defaults for all settings
7. **Centralize access** - Import from `config.settings` everywhere

## Troubleshooting

### Configuration not loading

```bash
# Check if .env file exists
ls -la .env

# Verify environment variables are set
python -c "from config.settings import settings; print(settings.llm.default_provider)"
```

### API keys not recognized

```bash
# Ensure .env is in project root
# Check for extra spaces or quotes in .env file
# Reload settings explicitly
python -c "from config.settings import reload_settings; reload_settings()"
```

### Directories not created

```python
# Manually ensure directories
from config.settings import settings
settings.ensure_directories()
```

## Migration from Old Configuration

If you were using hardcoded configuration values:

**Before:**
```python
# Scattered throughout codebase
llm_provider = "groq"
max_retries = 3
reports_dir = "reports/"
```

**After:**
```python
from config.settings import settings

llm_provider = settings.llm.default_provider
max_retries = settings.llm.max_retries
reports_dir = settings.processing.reports_dir
```

## Example: Complete Agent with Configuration

```python
from config.settings import settings
from src.core.clients.llm_client import UnifiedLLMManager

class MyAgent:
    def __init__(self):
        self.llm = UnifiedLLMManager(
            provider=settings.llm.default_provider
        )
        self.max_retries = settings.llm.max_retries
        self.timeout = settings.llm.timeout
        self.reports_dir = settings.processing.reports_dir
        
    def process(self, document):
        # Use human review if enabled
        if settings.processing.enable_human_review:
            result = self._process_with_review(document)
        else:
            result = self._process_auto(document)
        
        # Save to configured reports directory
        output_path = self.reports_dir / f"report_{document.id}.json"
        output_path.write_text(result)
        
        return result
```

---

For more information, see [`config/settings.py`](../config/settings.py) for the complete implementation.
