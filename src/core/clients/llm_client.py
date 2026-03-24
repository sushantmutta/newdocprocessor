import os
import boto3
from langchain_groq import ChatGroq
from langchain_ollama import ChatOllama
from langchain_aws import ChatBedrock
from tenacity import retry, stop_after_attempt, wait_exponential
from botocore.exceptions import ClientError
from dotenv import load_dotenv
load_dotenv()


class UnifiedLLMManager:
    """
    Unified LLM Manager supporting multiple providers (Ollama, Groq, Bedrock).
    Provider can be selected via constructor parameter or LLM_PROVIDER environment variable.
    """

    def __init__(self, provider: str = None):
        # Allow runtime provider override, fallback to environment variable
        self.provider = (provider or os.getenv(
            "LLM_PROVIDER", "ollama")).lower()
        self.provider_name = self.provider  # For logging
        self.last_fallback_used = False

        if self.provider == "ollama":
            self._setup_ollama()
        elif self.provider == "groq":
            self._setup_groq()
        elif self.provider == "bedrock":
            self._setup_bedrock()
        else:
            raise ValueError(
                f"Unsupported LLM provider: '{self.provider}'. "
                f"Supported providers: 'ollama', 'groq', 'bedrock'"
            )

    def _setup_ollama(self):
        """Configure Ollama (local) LLM provider"""
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        primary_model = os.getenv("OLLAMA_PRIMARY_MODEL", "llama3.1:8b")
        fallback_model = os.getenv("OLLAMA_FALLBACK_MODEL", "llama3.1:8b")

        print(f"🤖 Initializing Ollama provider: {primary_model}")

        self.primary_llm = ChatOllama(
            model=primary_model,
            base_url=base_url,
            temperature=0,
            num_predict=2048  # Limit response length for faster inference
        )

        self.fallback_llm = ChatOllama(
            model=fallback_model,
            base_url=base_url,
            temperature=0,
            num_predict=2048
        )

        self.model_name = primary_model

    def _setup_groq(self):
        """Configure Groq (cloud) LLM provider"""
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError(
                "GROQ_API_KEY not found in .env. "
                "Get your key from: https://console.groq.com"
            )

        primary_model = os.getenv(
            "GROQ_PRIMARY_MODEL", "llama-3.3-70b-versatile")
        fallback_model = os.getenv(
            "GROQ_FALLBACK_MODEL", "llama-3.1-8b-instant")

        print(f"🤖 Initializing Groq provider: {primary_model}")

        self.primary_llm = ChatGroq(
            model=primary_model,
            temperature=0,
            groq_api_key=api_key,
            max_tokens=2048  # Limit for faster response
        )

        self.fallback_llm = ChatGroq(
            model=fallback_model,
            temperature=0,
            groq_api_key=api_key,
            max_tokens=2048
        )

        self.model_name = primary_model

    def _setup_bedrock(self):
        """Configure AWS Bedrock (cloud) LLM provider"""
        region = os.getenv("AWS_REGION", "us-east-1")
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not aws_access_key or not aws_secret_key:
            raise ValueError(
                "AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY not found in .env. "
                "Required for Bedrock provider."
            )

        primary_model = os.getenv(
            "BEDROCK_PRIMARY_MODEL", "anthropic.claude-3-haiku-20240307-v1:0")
        fallback_model = os.getenv(
            "BEDROCK_FALLBACK_MODEL", "amazon.titan-text-express-v1")

        print(f"🤖 Initializing Bedrock provider: {primary_model}")

        # Initialize the session-aware runtime client
        runtime_client = boto3.client(
            "bedrock-runtime",
            region_name=region,
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key
        )

        self.primary_llm = ChatBedrock(
            model_id=primary_model,
            client=runtime_client,
            model_kwargs={
                "temperature": 0,
                "max_tokens": 2048  # Limit for faster response
            }
        )

        self.fallback_llm = ChatBedrock(
            model_id=fallback_model,
            client=runtime_client,
            model_kwargs={
                "temperature": 0,
                "max_tokens": 2048
            }
        )

        self.model_name = primary_model

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=6))
    def invoke_with_fallback(self, messages):
        """
        Invoke LLM with automatic fallback on failure.

        Args:
            messages: List of LangChain messages (SystemMessage, HumanMessage, etc.)

        Returns:
            LLM response object with .content attribute

        Raises:
            Exception: If both primary and fallback models fail
        """
        self.last_fallback_used = False
        try:
            response = self.primary_llm.invoke(messages)
            self.last_fallback_used = False
            return response
        except Exception as e:
            error_msg = str(e)
            is_rate_limit = "rate_limit" in error_msg.lower() or "429" in error_msg

            if is_rate_limit:
                print(
                    f"⚠️ {self.provider.capitalize()} Rate limit reached. Trying fallback model...")
            else:
                print(
                    f"⚠️ {self.provider.capitalize()} Primary failed: {e}. Trying fallback...")

            try:
                response = self.fallback_llm.invoke(messages)
                self.last_fallback_used = True
                return response
            except Exception as fallback_error:
                fallback_msg = str(fallback_error)

                # Provide specific error messages for common issues
                if "rate_limit" in fallback_msg.lower() or "429" in fallback_msg:
                    print(
                        f"❌ Both models rate limited. Please wait or upgrade your {self.provider.capitalize()} plan.")
                    raise Exception(
                        f"Rate limit exceeded for {self.provider}. Both primary and fallback models are rate limited. "
                        f"Please wait a few minutes or upgrade your API plan."
                    ) from fallback_error
                elif "decommissioned" in fallback_msg.lower() or "model_decommissioned" in fallback_msg:
                    print(f"❌ Fallback model decommissioned: {fallback_error}")
                    raise Exception(
                        f"Fallback model is no longer supported. Please update GROQ_FALLBACK_MODEL in .env file."
                    ) from fallback_error
                else:
                    print(f"❌ Fallback also failed: {fallback_error}")
                    raise Exception(
                        f"Both primary and fallback LLMs failed for provider '{self.provider}'"
                    ) from fallback_error

    def fallback_was_used(self) -> bool:
        """Return whether the most recent invocation used fallback model."""
        return bool(self.last_fallback_used)


# Backward compatibility: Keep GroqManager as alias
# This allows existing code to work without changes
GroqManager = UnifiedLLMManager
