import os
import boto3
from langchain_aws import ChatBedrock
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load variables from .env into os.environ
load_dotenv()


class BedrockManager:
    def __init__(self):
        # Fetch credentials from environment variables
        self.region = os.getenv("AWS_REGION", "us-east-1")
        self.aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        self.aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not self.aws_access_key or not self.aws_secret_key:
            raise ValueError("AWS Credentials not found in .env file")

        # Initialize the session-aware runtime client
        self.runtime_client = boto3.client(
            "bedrock-runtime",
            region_name=self.region,
            aws_access_key_id=self.aws_access_key,
            aws_secret_access_key=self.aws_secret_key
        )

        # Primary Model: Claude 3 Haiku
        self.primary_llm = ChatBedrock(
            model_id="anthropic.claude-3-haiku-20240307-v1:0",
            client=self.runtime_client,
            model_kwargs={"temperature": 0}
        )

        # Fallback Model: Amazon Titan Text Express
        self.fallback_llm = ChatBedrock(
            model_id="amazon.titan-text-express-v1",
            client=self.runtime_client,
            model_kwargs={"temperature": 0}
        )

    @retry(
        retry=retry_if_exception_type(ClientError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        reraise=True
    )
    def invoke_with_fallback(self, prompt_messages):
        try:
            print("🤖 Attempting with Claude 3 Haiku...")
            return self.primary_llm.invoke(prompt_messages)
        except Exception as e:
            print(f"⚠️ Primary LLM failed: {e}")
            print("🔄 Falling back to Titan Text...")
            return self.fallback_llm.invoke(prompt_messages)
