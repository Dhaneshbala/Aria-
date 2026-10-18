"""Think-flag regression: think=True must not 400 non-thinking models.

Probes /api/show capabilities (mocked); think is sent only when supported.
"""

import httpx
import respx

from services import ollama_service


def _show(caps):
    return httpx.Response(200, json={"capabilities": caps})


async def test_think_dropped_for_non_thinking_model():
    ollama_service._think_support.clear()
    with respx.mock(base_url="http://127.0.0.1:11434") as router:
        router.post("/api/show").mock(return_value=_show(["completion", "vision"]))
        assert await ollama_service._model_supports_thinking("gemma3:12b") is False
        # second call served from cache: exactly one probe request
        assert await ollama_service._model_supports_thinking("gemma3:12b") is False
        assert router.calls.call_count == 1


async def test_think_kept_for_thinking_model():
    ollama_service._think_support.clear()
    with respx.mock(base_url="http://127.0.0.1:11434") as router:
        router.post("/api/show").mock(return_value=_show(["completion", "thinking"]))
        assert await ollama_service._model_supports_thinking("deepseek-r1:14b") is True


async def test_probe_failure_is_fail_open():
    ollama_service._think_support.clear()
    with respx.mock(base_url="http://127.0.0.1:11434") as router:
        router.post("/api/show").mock(side_effect=httpx.ConnectError("down"))
        assert await ollama_service._model_supports_thinking("x") is True
