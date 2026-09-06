"""One-off synthetic audio round trip. No database, private memory or raw file save."""
import json
import os
import re
import time
from openai import OpenAI
from core.cognition.voice_input import transcribe_draft


def run():
    client = OpenAI(api_key=os.environ['OPENAI_API_KEY'], timeout=45, max_retries=0)
    phrase = 'Project Cedar is a synthetic test. Please keep my unfinished thought until I choose to send it.'
    started = time.monotonic()
    audio = client.audio.speech.create(model='tts-1', voice='nova', input=phrase, response_format='mp3').content
    result = transcribe_draft(client, audio, 'audio/mpeg')
    text = re.sub(r'[^a-z ]', '', result['text'].lower())
    passed = all(word in text for word in ['cedar', 'synthetic', 'unfinished', 'choose', 'send'])
    print('L_STAGE6_AUDIO_CHECK ' + json.dumps({'passed': passed, 'synthetic_only': True,
          'calls': 2, 'tts_model': 'tts-1', 'receipt': result['receipt'],
          'round_trip_ms': round((time.monotonic()-started)*1000), 'memory_written': result['memory_written']}), flush=True)
    if not passed: raise RuntimeError('Synthetic transcription check failed')


if __name__ == '__main__':
    run()
