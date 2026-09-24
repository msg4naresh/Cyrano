import base64
import os
import subprocess
import sys

import pytest
from botocore.exceptions import ClientError

import bedrock


class FakeClient:
    def __init__(self, events=None, error=None):
        self.events = events or []
        self.error = error
        self.calls = []

    def converse_stream(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return {"stream": iter(self.events)}


def delta(text):
    return {"contentBlockDelta": {"delta": {"text": text}}}


@pytest.fixture
def fake(monkeypatch):
    def install(**kw):
        client = FakeClient(**kw)
        monkeypatch.setattr(bedrock, "_client", client)
        return client
    return install


def test_stream_forwards_tokens_and_returns_full_reply(fake):
    client = fake(events=[{"messageStart": {}}, delta("Hel"), delta("lo"), {"messageStop": {}}])
    tokens = []
    reply = bedrock.stream("sys", [bedrock.text_message("hi")], tokens.append)
    assert tokens == ["Hel", "lo"]
    assert reply == "Hello"
    call = client.calls[0]
    assert call["system"] == [{"text": "sys"}]
    assert call["messages"] == [{"role": "user", "content": [{"text": "hi"}]}]


def test_client_error_becomes_runtime_error(fake):
    err = ClientError({"Error": {"Code": "ThrottlingException", "Message": "slow down"}}, "ConverseStream")
    fake(error=err)
    with pytest.raises(RuntimeError, match="ThrottlingException"):
        bedrock.stream("sys", [], lambda t: None)


def test_image_message_decodes_base64():
    png = b"\x89PNG fake"
    msg = bedrock.image_message(base64.standard_b64encode(png).decode())
    assert msg["content"][0]["image"]["source"]["bytes"] == png


def test_import_does_not_create_client():
    # Fresh interpreter: importing must not touch AWS (no credentials in CI).
    code = "import bedrock; assert bedrock._client is None"
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    subprocess.run([sys.executable, "-c", code], cwd=root, check=True)
