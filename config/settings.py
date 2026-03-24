"""
Application Configuration Settings
Centralizes all configuration for the Agentic Document Processor
"""
import os
from pathlib import Path
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent


class LLMProviderConfig(BaseModel):
    """Configuration for LLM providers"""
    # Default provider
    default_provider: str = Field(
        default=os.getenv("DEFAULT_LLM_PROVIDER", "ollama"),
        description="Default LLM provider (bedrock, groq, ollama)"
    )

    # AWS Bedrock Configuration
    bedrock_region: str = Field(
        default=os.getenv("AWS_REGION", "us-east-1"),
        description="AWS region for Bedrock"
    )
    bedrock_model: str = Field(
        default=os.getenv(
            "BEDROCK_MODEL", "anthropic.claude-3-haiku-20240307-v1:0"),
        description="Bedrock model ID"
    )
    bedrock_fallback_model: str = Field(
        default=os.getenv("BEDROCK_FALLBACK_MODEL",
                          "amazon.titan-text-express-v1"),
        description="Bedrock fallback model"
    )

    # Groq Configuration
    groq_api_key: Optional[str] = Field(
        default=os.getenv("GROQ_API_KEY"),
        description="Groq API key"
    )
    groq_model: str = Field(
        default=os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"),
        description="Groq model name"
    )

    # Ollama Configuration
    ollama_base_url: str = Field(
        default=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        description="Ollama API base URL"
    )
    ollama_model: str = Field(
        default=os.getenv("OLLAMA_MODEL", "llama3.1"),
        description="Ollama model name"
    )

    # General LLM Settings
    temperature: float = Field(
        default=float(os.getenv("LLM_TEMPERATURE", "0.0")),
        description="LLM temperature for generation"
    )
    max_tokens: int = Field(
        default=int(os.getenv("LLM_MAX_TOKENS", "4000")),
        description="Maximum tokens for LLM responses"
    )
    timeout: int = Field(
        default=int(os.getenv("LLM_TIMEOUT", "30")),
        description="LLM request timeout in seconds"
    )
    max_retries: int = Field(
        default=int(os.getenv("LLM_MAX_RETRIES", "3")),
        description="Maximum retry attempts for LLM calls"
    )


class APIConfig(BaseModel):
    """API Server Configuration"""
    host: str = Field(
        default=os.getenv("API_HOST", "0.0.0.0"),
        description="API server host"
    )
    port: int = Field(
        default=int(os.getenv("API_PORT", "8000")),
        description="API server port"
    )
    reload: bool = Field(
        default=os.getenv("API_RELOAD", "true").lower() == "true",
        description="Enable auto-reload for development"
    )
    workers: int = Field(
        default=int(os.getenv("API_WORKERS", "1")),
        description="Number of worker processes"
    )
    cors_origins: List[str] = Field(
        default=["*"],
        description="CORS allowed origins"
    )


class StreamlitConfig(BaseModel):
    """Streamlit UI Configuration"""
    host: str = Field(
        default=os.getenv("STREAMLIT_HOST", "localhost"),
        description="Streamlit server host"
    )
    port: int = Field(
        default=int(os.getenv("STREAMLIT_PORT", "8501")),
        description="Streamlit server port"
    )
    theme: str = Field(
        default=os.getenv("STREAMLIT_THEME", "dark"),
        description="UI theme (dark/light)"
    )


class ProcessingConfig(BaseModel):
    """Document Processing Configuration"""
    # File paths
    data_dir: Path = Field(
        default=PROJECT_ROOT / "data",
        description="Base data directory"
    )
    labreports_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "labreports",
        description="Lab reports directory"
    )
    prescriptions_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "prescriptions",
        description="Prescriptions directory"
    )
    reports_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "reports",
        description="Output reports directory"
    )

    # Processing settings
    max_repair_attempts: int = Field(
        default=int(os.getenv("MAX_REPAIR_ATTEMPTS", "3")),
        description="Maximum repair attempts before aborting"
    )
    enable_human_review: bool = Field(
        default=os.getenv("ENABLE_HUMAN_REVIEW", "false").lower() == "true",
        description="Enable human-in-the-loop review mode"
    )
    confidence_threshold: float = Field(
        default=float(os.getenv("CONFIDENCE_THRESHOLD", "0.70")),
        description="Minimum extraction confidence before requiring human review"
    )
    review_flag_severities: List[str] = Field(
        default=["HIGH", "CRITICAL"],
        description="Validation severities that should trigger human review"
    )
    review_timeout_hours: int = Field(
        default=int(os.getenv("REVIEW_TIMEOUT_HOURS", "4")),
        description="Hours before pending reviews are auto-escalated or auto-approved"
    )
    interrupt_before_repair: bool = Field(
        default=os.getenv("INTERRUPT_BEFORE_REPAIR",
                          "false").lower() == "true",
        description="Interrupt before repair node in HITL review graph"
    )
    timeout_action: str = Field(
        default=os.getenv("REVIEW_TIMEOUT_ACTION", "escalate"),
        description="Action on review timeout: escalate or auto_approve"
    )
    review_poll_interval_seconds: int = Field(
        default=int(os.getenv("REVIEW_POLL_INTERVAL_SECONDS", "300")),
        description="Background review timeout worker interval in seconds"
    )
    reviews_db_path: Path = Field(
        default=PROJECT_ROOT / "data" / "reviews.db",
        description="SQLite file for LangGraph checkpoints and review queue metadata"
    )
    enable_knowledge_lookup: bool = Field(
        default=os.getenv("ENABLE_KNOWLEDGE_LOOKUP",
                          "false").lower() == "true",
        description="Enable exact-match knowledge validation between validator and supervisor"
    )
    knowledge_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "knowledge",
        description="Curated knowledge base directory (JSON/CSV)"
    )

    # Document settings
    supported_formats: List[str] = Field(
        default=["pdf", "txt"],
        description="Supported document formats"
    )
    max_file_size_mb: int = Field(
        default=int(os.getenv("MAX_FILE_SIZE_MB", "10")),
        description="Maximum file size in MB"
    )
    min_text_length: int = Field(
        default=int(os.getenv("MIN_TEXT_LENGTH", "10")),
        description="Minimum extracted text length"
    )

    # Validation settings
    strict_validation: bool = Field(
        default=os.getenv("STRICT_VALIDATION", "true").lower() == "true",
        description="Enable strict schema validation"
    )


class LoggingConfig(BaseModel):
    """Logging Configuration"""
    level: str = Field(
        default=os.getenv("LOG_LEVEL", "INFO"),
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    format: str = Field(
        default="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        description="Log message format"
    )
    file_path: Optional[Path] = Field(
        default=PROJECT_ROOT / "logs" /
        "app.log" if os.getenv(
            "LOG_TO_FILE", "false").lower() == "true" else None,
        description="Log file path (None for console only)"
    )
    max_file_size_mb: int = Field(
        default=int(os.getenv("LOG_MAX_SIZE_MB", "10")),
        description="Maximum log file size in MB"
    )
    backup_count: int = Field(
        default=int(os.getenv("LOG_BACKUP_COUNT", "5")),
        description="Number of log file backups to keep"
    )


class LangSmithConfig(BaseModel):
    """LangSmith Tracing Configuration"""
    enabled: bool = Field(
        default=os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true",
        description="Enable LangSmith tracing"
    )
    api_key: Optional[str] = Field(
        default=os.getenv("LANGCHAIN_API_KEY"),
        description="LangSmith API key"
    )
    project: str = Field(
        default=os.getenv("LANGCHAIN_PROJECT", "agentic-doc-processor"),
        description="LangSmith project name"
    )
    endpoint: str = Field(
        default=os.getenv("LANGCHAIN_ENDPOINT",
                          "https://api.smith.langchain.com"),
        description="LangSmith API endpoint"
    )


class MetricsConfig(BaseModel):
    """Metrics and Monitoring Configuration"""
    enable_metrics: bool = Field(
        default=os.getenv("ENABLE_METRICS", "true").lower() == "true",
        description="Enable metrics collection"
    )
    metrics_file: Path = Field(
        default=PROJECT_ROOT / "data" / "reports" / "metrics_report.csv",
        description="Metrics CSV file path"
    )
    enable_performance_tracking: bool = Field(
        default=os.getenv("ENABLE_PERFORMANCE_TRACKING",
                          "true").lower() == "true",
        description="Track performance metrics"
    )
    p95_latency_threshold_ms: float = Field(
        default=float(os.getenv("P95_LATENCY_THRESHOLD_MS", "3500")),
        description="P95 latency threshold in milliseconds"
    )


class Settings(BaseModel):
    """Main Application Settings"""
    # Application metadata
    app_name: str = "Agentic Document Processor"
    version: str = "1.0.0"
    description: str = "Multi-agent medical document intelligence pipeline"

    # Component configurations
    llm: LLMProviderConfig = Field(default_factory=LLMProviderConfig)
    api: APIConfig = Field(default_factory=APIConfig)
    streamlit: StreamlitConfig = Field(default_factory=StreamlitConfig)
    processing: ProcessingConfig = Field(default_factory=ProcessingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    langsmith: LangSmithConfig = Field(default_factory=LangSmithConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)

    # Environment
    environment: str = Field(
        default=os.getenv("ENVIRONMENT", "development"),
        description="Application environment (development, staging, production)"
    )
    debug: bool = Field(
        default=os.getenv("DEBUG", "false").lower() == "true",
        description="Enable debug mode"
    )

    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    def ensure_directories(self):
        """Create necessary directories if they don't exist"""
        directories = [
            self.processing.data_dir,
            self.processing.labreports_dir,
            self.processing.prescriptions_dir,
            self.processing.reports_dir,
            self.processing.reviews_db_path.parent,
            self.processing.knowledge_dir,
        ]

        if self.logging.file_path:
            directories.append(self.logging.file_path.parent)

        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)

    def validate_configuration(self) -> List[str]:
        """Validate configuration and return list of warnings/errors"""
        issues = []

        # Check LLM provider API keys
        if self.llm.default_provider == "groq" and not self.llm.groq_api_key:
            issues.append(
                "GROQ_API_KEY not set but Groq is the default provider")

        # Check if LangSmith is enabled but missing API key
        if self.langsmith.enabled and not self.langsmith.api_key:
            issues.append(
                "LangSmith tracing enabled but LANGCHAIN_API_KEY not set")

        # Check file size limits
        if self.processing.max_file_size_mb < 1:
            issues.append("MAX_FILE_SIZE_MB should be at least 1 MB")

        # Check latency threshold
        if self.metrics.p95_latency_threshold_ms < 1000:
            issues.append("P95 latency threshold seems too low (< 1 second)")

        return issues


# Global settings instance
settings = Settings()

# Ensure directories exist on import
settings.ensure_directories()


def get_settings() -> Settings:
    """Get application settings instance"""
    return settings


def reload_settings():
    """Reload settings from environment variables"""
    global settings
    load_dotenv(override=True)
    settings = Settings()
    settings.ensure_directories()
    return settings


# Convenience functions for common settings
def get_llm_provider() -> str:
    """Get the default LLM provider"""
    return settings.llm.default_provider


def get_reports_dir() -> Path:
    """Get the reports directory path"""
    return settings.processing.reports_dir


def get_reviews_db_path() -> Path:
    """Get the review/checkpoint SQLite database path."""
    return settings.processing.reviews_db_path


def is_debug_mode() -> bool:
    """Check if debug mode is enabled"""
    return settings.debug


def is_production() -> bool:
    """Check if running in production environment"""
    return settings.environment == "production"


if __name__ == "__main__":
    # Print configuration for debugging
    print("=" * 60)
    print("Application Configuration")
    print("=" * 60)
    print(f"\nEnvironment: {settings.environment}")
    print(f"Debug Mode: {settings.debug}")
    print(f"\nLLM Provider: {settings.llm.default_provider}")
    print(f"API Port: {settings.api.port}")
    print(f"Streamlit Port: {settings.streamlit.port}")
    print(f"\nData Directory: {settings.processing.data_dir}")
    print(f"Reports Directory: {settings.processing.reports_dir}")
    print(f"\nLangSmith Enabled: {settings.langsmith.enabled}")
    print(f"Metrics Enabled: {settings.metrics.enable_metrics}")

    # Validate configuration
    issues = settings.validate_configuration()
    if issues:
        print("\n⚠️  Configuration Issues:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("\n✅ Configuration valid")
    print("=" * 60)
