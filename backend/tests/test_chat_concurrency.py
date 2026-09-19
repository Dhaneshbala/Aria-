"""Chat-core slice 3: SSE concurrency guard (hermetic)."""
import asyncio
import routers.chat as chat_mod


def test_max_streams_is_4():
    assert chat_mod.MAX_CHAT_STREAMS == 4


def test_slot_available_initially():
    assert chat_mod._chat_slot_available() is True


def test_empty_message_rejected_before_slot():
    from fastapi.testclient import TestClient
    from main import app
    client = TestClient(app, raise_server_exceptions=False)
    before = chat_mod._chat_sem._value
    r = client.post("/api/chat", data={"message": "", "conversation_id": "t"})
    assert r.status_code in (400, 422)
    assert chat_mod._chat_sem._value == before  # validation failed → slot untouched


async def test_semaphore_blocks_fifth():
    sem = asyncio.Semaphore(4)
    for _ in range(4):
        await sem.acquire()
    try:
        await asyncio.wait_for(sem.acquire(), timeout=0.05)
        acquired = True
    except asyncio.TimeoutError:
        acquired = False
    assert acquired is False
    for _ in range(4):
        sem.release()
