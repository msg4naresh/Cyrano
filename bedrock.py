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


def _text_stream(system: list, messages: list):
    """
    Generator that yields text tokens from a Bedrock streaming response.

    Follows the textstream pattern: callers iterate with `for token in _text_stream(...):`
    instead of providing a callback. This makes composition, testing, and error
    propagation cleaner — the generator raises on failure, consumers handle it.
    """
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
                    yield delta["text"]

    except ClientError as e:
        error_code = e.response["Error"]["Code"]
        logger.error("Bedrock API error [%s]: %s", error_code, e)
        raise RuntimeError(f"Bedrock API error ({error_code}): {e}") from e
    except BotoCoreError as e:
        logger.error("AWS SDK error: %s", e)
        raise RuntimeError(f"AWS SDK error: {e}") from e


def ask_claude(image_b64: str, prompt: str = None):
    """
    Yields text tokens from Claude's response to a screenshot.

    Args:
        image_b64: base64-encoded PNG string from capture.py
        prompt: optional system prompt (defaults to PROMPT from config)

    Yields:
        str: individual text tokens from the streaming response
    """
    image_bytes = base64.standard_b64decode(image_b64)
    yield from _text_stream(
        system=[{"text": prompt or PROMPT}],
        messages=[{
            "role": "user",
            "content": [
                {"image": {"format": "png", "source": {"bytes": image_bytes}}},
                {"text": "Solve this problem."},
            ],
        }],
    )


def ask_claude_followup(conversation: list):
    """
    Yields text tokens from Claude's response to a multi-turn conversation.

    Args:
        conversation: list of Bedrock message dicts (role + content)

    Yields:
        str: individual text tokens from the streaming response
    """
    yield from _text_stream(
        system=[{"text": FOLLOWUP_PROMPT}],
        messages=conversation,
    )


def ask_claude_text(text: str, prompt: str = None):
    """
    Yields text tokens from Claude's response to plain text input.

    Args:
        text: the clipboard text to analyze
        prompt: optional system prompt (defaults to TEXT_PROMPT from config)

    Yields:
        str: individual text tokens from the streaming response
    """
    yield from _text_stream(
        system=[{"text": prompt or TEXT_PROMPT}],
        messages=[{
            "role": "user",
            "content": [{"text": text}],
        }],
    )
