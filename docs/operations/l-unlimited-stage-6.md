# Stage 6 — Spoken conversation

6 September 2026. Chained voice pilot: recorded audio → editable transcript →
existing durable text task → the same L cognition/evidence gates → browser speech.
Real-phone acceptance remains required before calling mobile audio certified.

## User controls

Open Spoken conversation and tap Record to request microphone permission.
Recording does not stream to OpenAI, detect silence as a completed turn, or submit
a task. Pause disables audio tracks and pauses the same MediaRecorder; Resume
continues the same recording. Finish & transcribe explicitly uploads the audio
to OpenAI, returning an editable draft. Only Send creates the normal durable task.
The draft is appended to current text so edits made during transcription survive.
No audio-derived emotion, diagnosis or mental-state fact enters cognition.

Read replies is opt-in for the current page. Playback uses one selected browser
voice, preferring en-AU. The speaker button and Pause reply interrupt immediately;
Resume reply repeats the interrupted sentence. Recording also interrupts speech.
L remains the sole response voice. No audio from the Railway server is played by
default; the old host-speaker path requires L_SERVER_SPEAKER=true.

Changing apps or losing the connection pauses voice and saves the text draft
locally. Returning does not automatically resume recording, speech or submission.
If a browser ends the microphone stream, captured audio is offered for review;
the user can transcribe it and record a continuation. Transcription failures retain
the current recording in page memory with explicit retry/download controls.
Unsent text survives reload in localStorage and can be cleared. Untranscribed
audio is not durable across page closure, browser termination or device restart.
There is an unload warning where supported and a download link once recording
finishes. Submitted tasks retain the existing recovery handles and same-owner
saved-answer behaviour; neither reconnect nor playback restart resubmits chat.

## API and storage boundary

POST /voice/transcribe accepts explicit multipart uploads. It returns text and a
draft receipt only; no raw/short-term memory, task, model reasoning or database
write. Audio is transient in upload handling/provider request and closed after
processing; it is not stored in L's database. The model is
gpt-4o-mini-transcribe, English, JSON output, 45-second provider timeout and no
automatic retries. Logs contain no transcript or audio. Provider data handling
continues under the existing OpenAI account terms; no claim of provider deletion.

Client recording limit: three minutes wall time, including pauses. Upload limit:
10 MB. Two simultaneous transcriptions per process; excess returns 429. Request
formats: MP4/M4A/WebM/WAV/MP3. Browser capture chooses a supported MP4 or WebM MIME.
The route uses the existing application's access boundary, not a new auth system;
the concurrency limit is not identity-based rate limiting or a global spend cap.
There are no new credentials, public client keys, tables or background jobs.

## Architecture comparison

| Concern | Chained path deployed here | Realtime speech-to-speech alternative |
|---|---|---|
| Grounding | Reviewed transcript enters unchanged text-task/citation gates | Requires explicit integration of tools, evidence and publication checks into a realtime session |
| Interruption | User pause/record cancels browser playback; answer/task remains saved | Can support low-latency turn interruption, with session/audio truncation handling |
| Unfinished thought | Silence never submits; explicit Finish and Send | Turn detection must be configured carefully to avoid cutting off pauses |
| Reconnect | Existing durable text recovery plus local draft | Requires realtime session lifecycle and reconnection policy |
| Trade-off | Extra transcription/review latency; deterministic text checkpoint | More fluid audio interaction; more integration work to preserve these controls |

This is a documented architectural comparison, not an empirical head-to-head
benchmark. Realtime speech-to-speech is not enabled. Browser playback and recording
capabilities, interruption timing, accents, and permissions require device tests.

References: [OpenAI voice agents](https://developers.openai.com/api/docs/guides/voice-agents),
[transcription](https://developers.openai.com/api/docs/guides/speech-to-text),
[MediaRecorder pause](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/pause),
[audio data events](https://developer.mozilla.org/en-US/docs/Web/API/MediaRecorder/dataavailable_event).

## Verification and acceptance

Python tests exercise upload limits, formats, concurrency, provider failure,
file closure and the no-memory-write boundary. Executable JavaScript tests cover
permission denial, permission arriving after discard, recording pause/resume,
background/foreground, microphone loss, failed transcription, concurrent draft
edits, no auto-submit, and stale speech-completion events after interruption.
The voice UI uses the same sendMessage and /chat/start path as text, so the same
reviewed text uses the same retrieval rules; transcription mistakes must be edited.

scripts/check_l_voice_models.py runs one synthetic speech-generation/transcription
round trip (two provider calls) without database access. It is a one-off check,
never a recurring pre-deploy dependency. It does not establish real microphone
quality, human speech accuracy, Safari support or end-to-end personal recall.

Phone acceptance after deployment: allow/deny the mic prompt; speak half a
sentence, Pause, Resume and finish it; review/edit and Send; compare a personal
recall request with identical typed wording; interrupt/read-resume a reply; switch
apps mid-recording and mid-answer; briefly disconnect and recover the saved task.
Check that no unfinished thought is submitted and no duplicate task is created.

Rollback the Stage 6 application changes through GitHub. No schema rollback or
memory deletion is required. Preserve existing saved tasks and text workflow.
