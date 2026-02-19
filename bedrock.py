import base64
import logging
import boto3
from botocore.config import Config
from botocore.exceptions import ClientError, BotoCoreError
from config import AWS_REGION, AWS_PROFILE, BEDROCK_MODEL, PROMPT, TEXT_PROMPT, FOLLOWUP_PROMPT

logger = logging.getLogger(__name__)

_KNOWN_PREFIXES = ("anthropic.claude", "us.anthropic.claude")
if not BEDROCK_MODEL.startswith(_KNOWN_PREFIXES):
    logger.warning(
        "BEDROCK_MODEL '%s' does not start with a known Claude prefix (%s). "
        "Verify the model ID is correct.",
        BEDROCK_MODEL,
        ", ".join(_KNOWN_PREFIXES),
    )

retry_config = Config(retries={"max_attempts": 3, "mode": "adaptive"})
session = boto3.Session(profile_name=AWS_PROFILE, region_name=AWS_REGION)
client = session.client("bedrock-runtime", config=retry_config)


def test_connection() -> bool:
    """
    Test Bedrock connection by making a minimal API call.
    Returns True if successful, raises exception on failure.
    """
    try:
        response = client.converse(
            modelId=BEDROCK_MODEL,
            messages=[{"role": "user", "content": [{"text": "hi"}]}],
            inferenceConfig={"maxTokens": 1},
        )
        return True
    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        raise RuntimeError(f"Bedrock connection failed ({error_code}): {e}") from e
    except BotoCoreError as e:
        raise RuntimeError(f"AWS SDK error: {e}") from e


def _stream(system: list, messages: list, on_token):
    """Send messages to Bedrock and call on_token for each streamed text chunk."""
    try:
        response = client.converse_stream(
            modelId=BEDROCK_MODEL,
            system=system,
            messages=messages,
            inferenceConfig={"maxTokens": 2048},
        )

        for event in response["stream"]:
            if "contentBlockDelta" in event:
                delta = event["contentBlockDelta"]["delta"]
                if "text" in delta:
                    on_token(delta["text"])

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("Bedrock API error [%s]: %s", error_code, e)
        raise RuntimeError(f"Bedrock API error ({error_code}): {e}") from e
    except BotoCoreError as e:
        logger.error("AWS SDK error: %s", e)
        raise RuntimeError(f"AWS SDK error: {e}") from e


def ask_claude(image_b64: str, on_token, prompt: str = None):
    """
    Sends base64 screenshot to Claude via AWS Bedrock and streams the response.

    Args:
        image_b64: base64-encoded PNG string from capture.py
        on_token: callback function called with each streamed token (str)
        prompt: optional system prompt (defaults to PROMPT from config)
    """
    image_bytes = base64.standard_b64decode(image_b64)
    _stream(
        system=[{"text": prompt or PROMPT}],
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": "png", "source": {"bytes": image_bytes}}},
                {"text": "Solve this problem."},
            ],
        }],
        on_token=on_token,
    )


def ask_claude_followup(conversation: list, on_token):
    """
    Sends multi-turn conversation to Claude via AWS Bedrock and streams the response.

    Args:
        conversation: list of Bedrock message dicts (role + content)
        on_token: callback function called with each streamed token (str)
    """
    _stream(
        system=[{"text": FOLLOWUP_PROMPT}],
        messages=conversation,
        on_token=on_token,
    )


def ask_claude_text(text: str, on_token, prompt: str = None):
    """
    Sends plain text to Claude via AWS Bedrock and streams the response.

    Args:
        text: the clipboard text to analyze
        on_token: callback function called with each streamed token (str)
        prompt: optional system prompt (defaults to TEXT_PROMPT from config)
    """
    _stream(
        system=[{"text": prompt or TEXT_PROMPT}],
        messages=[{
            "role": "user",
            "content": [{"text": text}],
        }],
        on_token=on_token,
    )
