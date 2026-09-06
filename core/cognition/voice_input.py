"""Stage 6 transcription boundary: audio is a draft, never a memory write."""
import hashlib
import threading
import time

MAX_AUDIO_BYTES = 10 * 1024 * 1024
TRANSCRIBE_MODEL = 'gpt-4o-mini-transcribe'
MIME_EXTENSIONS = {'audio/mp4': 'mp4', 'audio/m4a': 'm4a', 'audio/x-m4a': 'm4a',
                   'audio/webm': 'webm', 'audio/wav': 'wav', 'audio/x-wav': 'wav',
                   'audio/mpeg': 'mp3'}
_slots = threading.BoundedSemaphore(2)


def audio_format(content_type):
    mime = str(content_type or '').split(';', 1)[0].strip().lower()
    if mime not in MIME_EXTENSIONS:
        raise ValueError('Use an MP4, M4A, WebM, WAV or MP3 recording.')
    return mime, MIME_EXTENSIONS[mime]


def transcribe_draft(client, data, content_type):
    mime, ext = audio_format(content_type)
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise ValueError('Use a non-empty recording under 10 MB.')
    if client is None:
        raise RuntimeError('Transcription is unavailable.')
    if not _slots.acquire(blocking=False):
        raise BlockingIOError('Transcription is busy. Your recording can be retried.')
    started = time.monotonic()
    try:
        result = client.with_options(timeout=45, max_retries=0).audio.transcriptions.create(
            model=TRANSCRIBE_MODEL, file=('recording.' + ext, data, mime),
            language='en', response_format='json')
        text = str(result.text or '').strip()
        if not text or len(text) > 100000:
            raise ValueError('No usable transcript returned. Try a shorter, clearer recording.')
        return {'text': text, 'draft': True, 'memory_written': False,
                'receipt': {'stage': 6, 'model': TRANSCRIBE_MODEL,
                            'duration_ms': round((time.monotonic() - started) * 1000),
                            'audio_bytes': len(data), 'transcript_sha256': hashlib.sha256(text.encode()).hexdigest(),
                            'audio_retained_by_l': False, 'requires_send': True}}
    finally:
        _slots.release()


def voice_manifest():
    return {'stage': 6, 'mode': 'transcript_then_existing_text_cognition',
            'transcription_model': TRANSCRIBE_MODEL, 'silence_submits': False,
            'audio_memory_writes': False, 'tone_inference': False,
            'playback': 'browser_speech_single_selected_voice',
            'mobile_acceptance': 'requires_real_device_test',
            'realtime_speech_to_speech': 'comparison_only_not_enabled'}
