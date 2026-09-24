import base64
import logging

from botocore.exceptions import ClientError, BotoCoreError

from config import AWS_REGION, AWS_PROFILE, BEDROCK_MODEL, MAX_TOKENS

logger = logging.getLogger(__name__)

_KNOWN_PREFIXES = ("anthropic.claude", "us.anthropic.claude", "eu.anthropic.claude", "global.anthropic.claude")
if not BEDROCK_MODEL.startswith(_KNOWN_PREFIXES):
    logger.warning(
        "BEDROCK_MODEL '%s' does not start with a known Claude prefix (%s). "
        "Verify the model ID is correct.",
        BEDROCK_MODEL,
        ", ".join(_KNOWN_PREFIXES),
    )

_client = None


def get_client():
    """Create the Bedrock client on first use, so importing this module needs no AWS credentials."""
    global _client
    if _client is None:
        import boto3
        from botocore.config import Config

        session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
        _client = session.client("bedrock-runtime", config=Config(retries={"max_attempts": 3, "mode": "adaptive"}))
    return _client


def _wrap_errors(fn):
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            logger.error("Bedrock API error [%s]: %s", error_code, e)
            raise RuntimeError(f"Bedrock API error ({error_code}): {e}") from e
        except BotoCoreError as e:
            logger.error("AWS SDK error: %s", e)
            raise RuntimeError(f"AWS SDK error: {e}") from e
    return wrapper


@_wrap_errors
def test_connection() -> bool:
    """Make a minimal API call. Returns True on success, raises RuntimeError on failure."""
    get_client().converse(
        modelId=BEDROCK_MODEL,
        messages=[{"role": "user", "content": [{"text": "hi"}]}],
        inferenceConfig={"maxTokens": 1},
    )
    return True


@_wrap_errors
def stream(system_prompt: str, messages: list, on_token) -> str:
    """
    Send a conversation to Claude and call on_token for each streamed text chunk.

    Args:
        system_prompt: the system prompt text
        messages: list of Bedrock message dicts (role + content)
        on_token: callback called with each streamed token (str)

    Returns:
        The full reply text.
    """
    response = get_client().converse_stream(
        modelId=BEDROCK_MODEL,
        system=[{"text": system_prompt}],
        messages=messages,
        inferenceConfig={"maxTokens": MAX_TOKENS},
    )
    parts = []
    for event in response["stream"]:
        delta = event.get("contentBlockDelta", {}).get("delta", {})
        if "text" in delta:
            parts.append(delta["text"])
            on_token(delta["text"])
    return "".join(parts)


def image_message(image_b64: str, text: str = "Here is the problem.") -> dict:
    """User message holding a base64 PNG screenshot plus a short instruction."""
    return {
        "role": "user",
        "content": [
            {"image": {"format": "png", "source": {"bytes": base64.standard_b64decode(image_b64)}}},
            {"text": text},
        ],
    }


def text_message(text: str, role: str = "user") -> dict:
    return {"role": role, "content": [{"text": text}]}
