const assert = require('node:assert/strict');
const {VoiceSession} = require('../ui/voice.js');

function fixture() {
    let hidden = false, saved = 0, networkCalls = 0, micCalls = 0;
    const track = {enabled: true, readyState: 'live', stop() {this.readyState = 'ended';}};
    const stream = {getTracks: () => [track]};
    const timers = new Map(); let timerID = 0;
    class Recorder {
        static isTypeSupported(type) { return type === 'audio/mp4'; }
        constructor() { this.state = 'inactive'; this.mimeType = 'audio/mp4'; }
        start() {this.state = 'recording';}
        pause() {this.state = 'paused';}
        resume() {this.state = 'recording';}
        stop() {
            this.state = 'inactive';
            queueMicrotask(() => { this.ondataavailable({data: new Blob(['audio'])}); this.onstop(); });
        }
    }
    const utterances = [];
    const synth = {cancel() {}, getVoices: () => [{lang: 'en-AU', name: 'selected'}], speak(u) {utterances.push(u);}};
    const env = {media: {getUserMedia: async () => {micCalls++; return stream;}}, Recorder,
        Blob, FormData, AbortController, input: {value: ''}, render() {}, saveDraft() {saved++;},
        hidden: () => hidden, setTimer(fn) {timers.set(++timerID, fn); return timerID;}, clearTimer(id) {timers.delete(id);},
        synth, Utterance: class {constructor(text) {this.text = text;}},
        fetch: async () => {networkCalls++; return {ok: true, json: async () => ({draft: true, text: 'finished thought'})};}};
    const voice = new VoiceSession(env);
    return {voice, env, track, stream, timers, utterances, hide: () => {hidden = true;}, show: () => {hidden = false;},
        counts: () => ({saved, networkCalls, micCalls})};
}
const settle = () => new Promise(resolve => setImmediate(resolve));

(async () => {
    // No permission request before explicit start; pauses preserve the same recording.
    let f = fixture();
    assert.equal(f.counts().micCalls, 0);
    await f.voice.start();
    const recorder = f.voice.recorder;
    f.voice.pause(); assert.equal(f.voice.state, 'paused'); assert.equal(f.track.enabled, false);
    assert.equal(f.counts().networkCalls, 0); assert.equal(f.voice.canSend(), false);
    f.voice.resume(); assert.equal(f.voice.recorder, recorder); assert.equal(f.track.enabled, true);
    f.voice.finish(false); await settle();
    assert.equal(f.voice.state, 'ready'); assert.equal(f.track.readyState, 'ended');
    assert.equal(f.counts().networkCalls, 0);
    f.env.input.value = 'existing draft';
    await f.voice.transcribe();
    assert.equal(f.env.input.value, 'existing draft\nfinished thought');
    assert.equal(f.voice.state, 'idle'); assert.equal(f.counts().saved, 1);
    assert.equal(f.counts().networkCalls, 1); // No chat/start call exists in voice layer.

    // Denial and discarded permission requests release late-arriving tracks.
    f = fixture(); f.env.media.getUserMedia = async () => {throw new Error('denied');};
    await f.voice.start(); assert.equal(f.voice.state, 'idle');
    f = fixture(); let permission;
    f.env.media.getUserMedia = () => new Promise(resolve => {permission = resolve;});
    const starting = f.voice.start(); f.voice.discard(); permission(f.stream); await starting;
    assert.equal(f.track.readyState, 'ended'); assert.equal(f.voice.state, 'idle');

    // Background pauses, never submits or automatically resumes.
    f = fixture(); await f.voice.start(); f.hide(); f.voice.background();
    assert.equal(f.voice.state, 'paused'); assert.equal(f.counts().networkCalls, 0);
    f.voice.resume(); assert.equal(f.voice.state, 'paused');
    f.show(); assert.equal(f.voice.state, 'paused'); f.voice.resume(); assert.equal(f.voice.state, 'recording');
    f.track.readyState = 'ended'; f.voice.pause(); f.voice.resume(); await settle();
    assert.equal(f.voice.state, 'ready'); assert.equal(f.counts().networkCalls, 0);

    // Network failure retains audio and text; late transcription appends current edits.
    f = fixture(); await f.voice.start(); f.voice.finish(false); await settle();
    const blob = f.voice.blob; f.env.fetch = async () => {throw new Error('offline');};
    await f.voice.transcribe(); assert.equal(f.voice.blob, blob); assert.equal(f.voice.state, 'ready');
    let response;
    f.env.fetch = () => new Promise(resolve => {response = resolve;});
    const pending = f.voice.transcribe(); f.env.input.value = 'edited while waiting';
    response({ok: true, json: async () => ({draft: true, text: 'more words'})}); await pending;
    assert.equal(f.env.input.value, 'edited while waiting\nmore words');

    // Explicit Finish can transcribe, but a stop in background cannot upload audio.
    f = fixture(); await f.voice.start(); f.voice.finish(true); f.hide(); await settle();
    assert.equal(f.counts().networkCalls, 0); assert.equal(f.voice.state, 'ready');

    // Late speech completion cannot advance a paused/interrupted reply.
    f = fixture(); f.voice.speak('First sentence. Second sentence.');
    const first = f.utterances[0]; f.voice.pauseSpeech(); first.onend();
    assert.equal(f.voice.sentence, 0); assert.equal(f.utterances.length, 1);
    f.voice.resumeSpeech(); assert.equal(f.utterances.length, 2);
    assert.equal(f.utterances[1].text, first.text);
    f.utterances[1].onend(); assert.equal(f.voice.sentence, 1);
    await f.voice.start(); assert.equal(f.voice.speechState, 'paused');
    assert.equal(f.utterances.every(u => u.voice.name === 'selected'), true);
    console.log('Stage 6 voice state checks passed: permission, pause/resume, interruption, drafts, retry, background.');
})().catch(error => {console.error(error); process.exitCode = 1;});
