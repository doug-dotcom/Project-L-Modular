/* Stage 6: explicit turns. No silence detection, auto-send or background replay. */
(function (root) {
    'use strict';
    class VoiceSession {
        constructor(env) {
            this.e = env;
            this.state = 'idle';
            this.chunks = [];
            this.bytes = 0;
            this.blob = null;
            this.stream = null;
            this.recorder = null;
            this.generation = 0;
            this.speechGeneration = 0;
            this.sentences = [];
            this.sentence = 0;
            this.speechState = 'idle';
            this.selectedVoice = null;
            this.timer = null;
        }
        set(state, message) { this.state = state; this.e.render(this, message); }
        tracks(enabled) { this.stream?.getTracks().forEach(t => { t.enabled = enabled; }); }
        release() { this.stream?.getTracks().forEach(t => t.stop()); this.stream = null; }
        async start() {
            if (this.state !== 'idle') return;
            this.pauseSpeech();
            const generation = ++this.generation;
            this.set('requesting', 'Allow microphone access to record. Nothing is sent while you speak.');
            try {
                const stream = await this.e.media.getUserMedia({audio: true});
                if (generation !== this.generation || this.e.hidden()) {
                    stream.getTracks().forEach(t => t.stop());
                    if (generation === this.generation) this.set('idle', 'Recording not started. Tap Record when ready.');
                    return;
                }
                this.stream = stream;
                this.transcribeOnStop = false; this.stopMessage = '';
                const mime = ['audio/mp4', 'audio/webm;codecs=opus', 'audio/webm']
                    .find(type => this.e.Recorder.isTypeSupported(type));
                if (!mime) throw new Error('format');
                this.chunks = []; this.bytes = 0; this.blob = null;
                const recorder = new this.e.Recorder(stream, {mimeType: mime, audioBitsPerSecond: 64000});
                this.recorder = recorder;
                recorder.ondataavailable = event => {
                    if (generation !== this.generation || !event.data?.size) return;
                    this.bytes += event.data.size;
                    this.chunks.push(event.data);
                    if (this.bytes > 10 * 1024 * 1024) this.finish(false, 'Recording limit reached. Download it or discard and make a shorter recording.');
                };
                recorder.onstop = () => {
                    if (generation !== this.generation) return;
                    this.e.clearTimer(this.timer);
                    this.blob = new this.e.Blob(this.chunks, {type: recorder.mimeType || mime});
                    this.release();
                    this.set('ready', this.stopMessage || 'Recording ready. Transcribe it, or download a copy before leaving.');
                    if (this.transcribeOnStop && !this.e.hidden()) this.transcribe();
                };
                recorder.onerror = () => this.finish(false, 'Recording interrupted. Any captured audio is kept for review.');
                stream.getTracks().forEach(track => {
                    track.onended = () => this.finish(false, 'Microphone disconnected. Review the captured recording.');
                });
                recorder.start(1000);
                this.set('recording', 'Recording — take your time. Silence does not send your thought.');
                this.timer = this.e.setTimer(() => this.finish(false, 'Three-minute recording limit reached. Your recording is ready to transcribe.'), 180000);
            } catch (_) {
                if (generation !== this.generation) return;
                this.release();
                this.set('idle', 'Microphone unavailable. Check browser permission, or keep typing to L.');
            }
        }
        pause() {
            if (this.state !== 'recording') return;
            try {
                this.recorder.pause(); this.tracks(false);
                this.set('paused', 'Paused. Your unfinished thought is kept here. Tap Resume when ready.');
            } catch (_) { this.finish(false, 'Recording interrupted. Review the captured audio.'); }
        }
        resume() {
            if (this.state !== 'paused' || this.e.hidden()) return;
            if (!this.stream?.getTracks().every(t => t.readyState === 'live')) {
                this.finish(false, 'Microphone stopped. Transcribe this part, then record the rest.'); return;
            }
            try {
                this.tracks(true); this.recorder.resume();
                this.set('recording', 'Recording again — your earlier words are retained.');
            } catch (_) { this.finish(false, 'Could not resume. Review the captured audio.'); }
        }
        finish(transcribe = false, message = '') {
            if (!['recording', 'paused'].includes(this.state)) return;
            this.transcribeOnStop = transcribe; this.stopMessage = message;
            this.set('stopping', 'Finishing recording…');
            this.tracks(false);
            if (this.recorder.state !== 'inactive') this.recorder.stop();
        }
        async transcribe() {
            if (this.state !== 'ready' || !this.blob) return;
            if (!this.blob.size || this.blob.size > 10 * 1024 * 1024) {
                this.set('ready', 'Recording is empty or over 10 MB. Download it or discard and try a shorter recording.'); return;
            }
            const generation = this.generation;
            this.set('transcribing', 'Transcribing with OpenAI. Your message will not be sent to L yet.');
            const abort = new this.e.AbortController();
            const timer = this.e.setTimer(() => abort.abort(), 60000);
            try {
                const form = new this.e.FormData();
                form.append('file', this.blob, this.blob.type.includes('mp4') ? 'recording.mp4' : 'recording.webm');
                const response = await this.e.fetch('/voice/transcribe', {method: 'POST', body: form, signal: abort.signal});
                const result = await response.json();
                if (!response.ok || !result.draft || typeof result.text !== 'string' || !result.text.trim()) throw new Error('transcription');
                if (generation !== this.generation) return;
                // Append to the CURRENT draft, preserving edits made during the request.
                this.e.input.value = [this.e.input.value.trim(), result.text.trim()].filter(Boolean).join('\n');
                this.e.saveDraft();
                this.chunks = []; this.blob = null;
                this.set('idle', 'Transcript ready below. Check the wording, then Send when your thought is complete.');
            } catch (_) {
                if (generation === this.generation) this.set('ready', 'Transcription did not finish. Recording retained here; retry or download it. Nothing was sent to L.');
            } finally { this.e.clearTimer(timer); }
        }
        discard() {
            if (this.state === 'transcribing') return;
            ++this.generation;
            this.e.clearTimer(this.timer);
            if (this.recorder && this.recorder.state !== 'inactive') this.recorder.stop();
            this.release(); this.chunks = []; this.blob = null;
            this.set('idle', 'Recording discarded. Your typed draft is unchanged.');
        }
        canSend() {
            if (this.state !== 'idle') {
                this.e.render(this, 'Finish and transcribe, or discard the recording before sending.'); return false;
            }
            this.pauseSpeech(); return true;
        }
        background() {
            this.pause(); this.pauseSpeech(); this.e.saveDraft();
        }
        speak(text) {
            if (!this.e.synth || this.e.hidden() || this.state !== 'idle') return;
            this.stopSpeech();
            this.sentences = String(text).match(/[^.!?\n]+[.!?\n]*|[.!?\n]+/g)?.flatMap(s => s.match(/[\s\S]{1,220}/g) || []) || [];
            this.sentence = 0;
            this.selectedVoice = this.selectedVoice || this.e.synth.getVoices().find(v => v.lang === 'en-AU') ||
                this.e.synth.getVoices().find(v => v.lang.startsWith('en')) || null;
            this.speechState = 'speaking'; this.nextSentence();
        }
        nextSentence() {
            if (this.speechState !== 'speaking') return;
            if (this.sentence >= this.sentences.length) { this.stopSpeech(); return; }
            const generation = this.speechGeneration;
            const utterance = new this.e.Utterance(this.sentences[this.sentence]);
            utterance.lang = 'en-AU'; utterance.voice = this.selectedVoice;
            utterance.onend = () => {
                if (generation !== this.speechGeneration || this.speechState !== 'speaking') return;
                this.sentence++; this.nextSentence();
            };
            utterance.onerror = () => { if (generation === this.speechGeneration) this.pauseSpeech(); };
            this.e.synth.speak(utterance); this.e.render(this);
        }
        pauseSpeech() {
            if (this.speechState !== 'speaking') return;
            ++this.speechGeneration; this.speechState = 'paused';
            this.e.synth?.cancel(); this.e.render(this);
        }
        resumeSpeech() {
            if (this.speechState !== 'paused' || this.e.hidden() || this.state !== 'idle') return;
            this.speechState = 'speaking'; this.nextSentence();
        }
        stopSpeech() {
            ++this.speechGeneration; this.speechState = 'idle';
            this.e.synth?.cancel(); this.e.render(this);
        }
    }
    root.LVoiceSession = VoiceSession;
    if (typeof module !== 'undefined') module.exports = {VoiceSession};
})(typeof window !== 'undefined' ? window : globalThis);
