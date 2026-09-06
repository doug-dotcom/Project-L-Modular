import asyncio
from io import BytesIO
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest
from starlette.datastructures import Headers, UploadFile
from fastapi import HTTPException
from core.cognition.voice_input import audio_format, transcribe_draft, MAX_AUDIO_BYTES, _slots


class Client:
    def __init__(self, text='A synthetic thought.', fail=False):
        self.text, self.fail, self.calls = text, fail, []
        self.audio = SimpleNamespace(transcriptions=SimpleNamespace(create=self.create))
    def with_options(self, **options):
        assert options == {'timeout': 45, 'max_retries': 0}
        return self
    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail: raise RuntimeError('private upstream information')
        return SimpleNamespace(text=self.text)


@pytest.mark.parametrize('mime,ext', [('audio/mp4','mp4'), ('audio/webm;codecs=opus','webm'),
                                     ('audio/x-m4a','m4a'), ('audio/wav','wav'), ('audio/mpeg','mp3')])
def test_supported_formats(mime, ext):
    assert audio_format(mime)[1] == ext


@pytest.mark.parametrize('data,mime', [(b'', 'audio/mp4'), (b'x' * (MAX_AUDIO_BYTES+1), 'audio/mp4'),
                                      (b'x', 'text/plain')])
def test_bad_upload_never_calls_provider(data, mime):
    client = Client()
    with pytest.raises(ValueError): transcribe_draft(client, data, mime)
    assert not client.calls


def test_transcript_is_only_a_draft_and_uses_no_personal_prompt():
    client = Client()
    result = transcribe_draft(client, b'synthetic audio', 'audio/mp4')
    assert result['draft'] and not result['memory_written']
    assert result['receipt']['requires_send']
    assert not result['receipt']['audio_retained_by_l']
    assert client.calls[0]['model'] == 'gpt-4o-mini-transcribe'
    assert 'prompt' not in client.calls[0]


def test_provider_failure_releases_concurrency_slot():
    with pytest.raises(RuntimeError): transcribe_draft(Client(fail=True), b'audio', 'audio/mp4')
    assert _slots.acquire(blocking=False) and _slots.acquire(blocking=False)
    _slots.release(); _slots.release()


def test_concurrency_cap_blocks_provider():
    _slots.acquire(); _slots.acquire()
    client = Client()
    try:
        with pytest.raises(BlockingIOError): transcribe_draft(client, b'audio', 'audio/mp4')
        assert not client.calls
    finally:
        _slots.release(); _slots.release()


@pytest.mark.parametrize('fail', [False, True])
def test_endpoint_closes_upload_and_never_writes_memory(monkeypatch, fail):
    from api import server
    monkeypatch.setattr(server, 'client', Client(fail=fail))
    monkeypatch.setattr(server, 'write_raw_catchall', lambda *a, **kw: pytest.fail('memory write'))
    monkeypatch.setattr(server, 'start_chat', lambda *a, **kw: pytest.fail('task started'))
    upload = UploadFile(BytesIO(b'audio'), filename='recording.mp4', headers=Headers({'content-type':'audio/mp4'}))
    if fail:
        with pytest.raises(HTTPException) as error: asyncio.run(server.transcribe_voice(upload))
        assert error.value.status_code == 503 and 'private' not in error.value.detail
    else:
        result = asyncio.run(server.transcribe_voice(upload))
        assert result['text'] == 'A synthetic thought.'
    assert upload.file.closed


def test_browser_state_machine():
    subprocess.run(['node', 'tests/voice_session.test.cjs'], check=True, capture_output=True, text=True)


def test_voice_uses_the_existing_text_submission_path():
    html = Path('ui/index.html').read_text()
    voice = Path('ui/voice.js').read_text()
    assert "'/voice/transcribe'" in voice and '/chat/start' not in voice
    assert 'window.lVoice.canSend()' in html
    assert 'window.lVoice?.saveDraft()' in html
    assert 'request_id: requestId' in html and '...recoveryHeaders()' in html
