import os
import json
import time
import logging
from typing import Dict, Any

# Try importing google.genai, fallback to mock for local testing if not configured
try:
    from google import genai
    from google.genai.types import HttpOptions, GenerateContentConfig
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    logging.warning("google-genai library not found. Vertex AI will not work.")

# google-auth is required for explicit service account credentials
try:
    from google.oauth2 import service_account
    AUTH_AVAILABLE = True
except ImportError:
    AUTH_AVAILABLE = False
    logging.warning("google-auth library not found. Install with: pip install google-auth")

logger = logging.getLogger("LLMProvider")

# Vertex AI scopes required for Generative AI
_VERTEX_SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]


def _load_service_account_credentials():
    """Load Google Cloud credentials with explicit priority.

    Priority:
      1. GOOGLE_APPLICATION_CREDENTIALS — path to a .json key file on disk.
      2. GCP_SERVICE_ACCOUNT_KEY — raw JSON string (for serverless envs).
      3. Fallback — Application Default Credentials (gcloud auth).

    Returns:
        google.oauth2.service_account.Credentials or None
    """
    if not AUTH_AVAILABLE:
        logger.info("google-auth not installed; falling back to ADC.")
        return None

    # ── Priority 1: File-based credentials ──────────────────────────
    cred_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path:
        # Resolve relative paths from project root
        if not os.path.isabs(cred_path):
            cred_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), cred_path)

        if os.path.isfile(cred_path):
            logger.info(f"Loading service account from file: {cred_path}")
            credentials = service_account.Credentials.from_service_account_file(
                cred_path, scopes=_VERTEX_SCOPES
            )
            return credentials
        else:
            logger.warning(f"GOOGLE_APPLICATION_CREDENTIALS points to missing file: {cred_path}")

    # ── Priority 2: Inline JSON string ──────────────────────────────
    key_json_str = os.environ.get("GCP_SERVICE_ACCOUNT_KEY")
    if key_json_str:
        logger.info("Loading service account from GCP_SERVICE_ACCOUNT_KEY env var.")
        try:
            key_data = json.loads(key_json_str)
            credentials = service_account.Credentials.from_service_account_info(
                key_data, scopes=_VERTEX_SCOPES
            )
            return credentials
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse GCP_SERVICE_ACCOUNT_KEY: {e}")

    # ── No credentials found — fail explicitly ─────────────────────
    raise RuntimeError(
        "No service account credentials found.\n"
        "Set one of:\n"
        "  1. GOOGLE_APPLICATION_CREDENTIALS env var → path to .json key file\n"
        "  2. GCP_SERVICE_ACCOUNT_KEY env var → JSON key as a string"
    )


class VertexAIProvider:
    """Vertex AI provider with explicit service account support and built-in rate limiting."""

    def __init__(
        self,
        project_id: str = None,
        location: str = None,
        model_name: str = "gemini-2.5-flash",
        base_delay_seconds: float = 1.0,
    ):
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT", "gen-lang-client-0841388254")
        self.location = location or os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        self.model_name = model_name
        self.base_delay_seconds = base_delay_seconds
        self.client = None

        if not GENAI_AVAILABLE:
            raise RuntimeError("google-genai library not found. Install with: pip install google-genai")

        if not self.project_id:
            logger.warning("GOOGLE_CLOUD_PROJECT not set. Relying on ADC default project.")

        # ── Load credentials ────────────────────────────────────────
        credentials = _load_service_account_credentials()

        try:
            self.client = genai.Client(
                vertexai=True,
                project=self.project_id,
                location=self.location,
                credentials=credentials,
                http_options=HttpOptions(api_version="v1"),
            )
            logger.info(f"✅ Vertex AI Provider ready — model={self.model_name}, project={self.project_id}, location={self.location}")

        except Exception as e:
            logger.error(f"Failed to initialize Vertex AI client: {e}")
            raise RuntimeError(
                f"Vertex AI authentication failed: {e}\n"
                "Ensure one of the following:\n"
                "  1. GOOGLE_APPLICATION_CREDENTIALS env var points to a valid .json key file\n"
                "  2. GCP_SERVICE_ACCOUNT_KEY env var contains the JSON key as a string"
            ) from e

    def generate_structured(self, system_prompt: str, user_prompt: str, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Generate structured output from Vertex AI.

        Returns the parsed JSON result merged with a 'usage' key containing token counts:
            result['usage']['input_tokens']
            result['usage']['output_tokens']
            result['usage']['total_tokens']
        """
        if not self.client:
            raise RuntimeError("Vertex AI client is not initialized.")

        config = GenerateContentConfig(
            system_instruction=system_prompt,
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,  # Fully deterministic for structured lexical extraction
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=user_prompt,
                config=config
            )

            # Extract token usage from response metadata
            usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                um = response.usage_metadata
                usage["input_tokens"] = getattr(um, 'prompt_token_count', 0) or 0
                usage["output_tokens"] = getattr(um, 'candidates_token_count', 0) or 0
                usage["total_tokens"] = getattr(um, 'total_token_count', 0) or 0
                logger.info(
                    f"Token usage: in={usage['input_tokens']}, "
                    f"out={usage['output_tokens']}, "
                    f"total={usage['total_tokens']}"
                )

            result = json.loads(response.text)
            result['usage'] = usage

            # ── Rate-limit safety: mandatory base delay between calls ──
            if self.base_delay_seconds > 0:
                time.sleep(self.base_delay_seconds)

            return result

        except Exception as e:
            logger.error(f"Vertex AI API error: {e}")
            raise
