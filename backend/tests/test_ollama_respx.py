"""respx-based tests — Ollama client paths without a live model.

Mocks httpx at the transport layer, so these run deterministically
in CI where Ollama is down (unlike test_e2e_features.py).
"""

import httpx
import respx

from services.ollama_service import OLLAMA_URL, OllamaService


@respx.mock
async def test_health_ok(respx_mock):
    respx_mock.get(f"{OLLAMA_URL}/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": "gemma3:12b"}]})
    )
    assert await OllamaService().health() == {"ok": True, "models": ["gemma3:12b"]}


@respx.mock
async def test_health_down(respx_mock):
    respx_mock.get(f"{OLLAMA_URL}/api/tags").mock(
        side_effect=httpx.ConnectError("refused")
    )
    assert await OllamaService().health() == {"ok": False, "models": []}


@respx.mock
async def test_list_models_shape(respx_mock):
    respx_mock.get(f"{OLLAMA_URL}/api/tags").mock(
        return_value=httpx.Response(
            200,
            json={"models": [{"name": "m", "size": 1_500_000_000, "modified_at": "t"}]},
        )
    )
    assert await OllamaService().list_models() == [
        {"name": "m", "size_gb": 1.5, "modified": "t"}
    ]
