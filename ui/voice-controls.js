document.addEventListener('DOMContentLoaded', () => {
    const el = id => document.getElementById(id);
    const input = el('message');
    const draftKey = 'project-l-unsent-draft';
    let audioURL = null, lastBlob = null;
    function saveDraft() {
        try {
            if (input.value) localStorage.setItem(draftKey, input.value);
            else localStorage.removeItem(draftKey);
        } catch (_) { el('voiceStatus').textContent = 'Browser draft storage unavailable. Copy your text before leaving.'; }
    }
    try { if (!input.value) input.value = localStorage.getItem(draftKey) || ''; } catch (_) {}
    input.addEventListener('input', saveDraft);
    function render(session, message) {
        const state = session.state;
        el('recordVoice').disabled = state !== 'idle' || !navigator.mediaDevices?.getUserMedia || !window.MediaRecorder;
        el('pauseVoice').disabled = state !== 'recording';
        el('resumeVoice').disabled = state !== 'paused';
        el('finishVoice').disabled = !['recording', 'paused'].includes(state);
        el('retryVoice').disabled = state !== 'ready';
        el('discardVoice').disabled = ['idle', 'transcribing', 'stopping'].includes(state);
        el('pauseReply').disabled = session.speechState !== 'speaking';
        el('resumeReply').disabled = session.speechState !== 'paused';
        el('voiceToggle').textContent = session.speechState === 'speaking' ? '⏸️' : session.speechState === 'paused' ? '▶️' : '🔊';
        if (message) el('voiceStatus').textContent = message;
        if (lastBlob !== session.blob) {
            if (audioURL) URL.revokeObjectURL(audioURL);
            lastBlob = session.blob;
            audioURL = lastBlob?.size ? URL.createObjectURL(lastBlob) : null;
            el('downloadVoice').hidden = !audioURL;
            if (audioURL) {
                el('downloadVoice').href = audioURL;
                el('downloadVoice').download = lastBlob.type.includes('mp4') ? 'L-recording.mp4' : 'L-recording.webm';
            }
        }
    }
    const voice = new window.LVoiceSession({media: navigator.mediaDevices, Recorder: window.MediaRecorder,
        Blob, FormData, AbortController, fetch: window.fetch.bind(window), input, render, saveDraft,
        hidden: () => document.hidden, setTimer: setTimeout, clearTimer: clearTimeout,
        synth: window.speechSynthesis, Utterance: window.SpeechSynthesisUtterance});
    voice.saveDraft = saveDraft;
    voice.onReply = (text, successful) => {
        if (successful && el('readVoiceReplies').checked && !document.hidden && voice.state === 'idle') voice.speak(text);
    };
    window.lVoice = voice;
    el('recordVoice').onclick = () => voice.start();
    el('pauseVoice').onclick = () => voice.pause();
    el('resumeVoice').onclick = () => voice.resume();
    el('finishVoice').onclick = () => voice.finish(true);
    el('retryVoice').onclick = () => voice.transcribe();
    el('discardVoice').onclick = () => voice.discard();
    el('pauseReply').onclick = () => voice.pauseSpeech();
    el('resumeReply').onclick = () => voice.resumeSpeech();
    el('voiceToggle').title = 'Read, pause or resume L’s latest reply. Resume repeats the interrupted sentence.';
    el('voiceToggle').setAttribute('aria-label', 'Read, pause or resume reply');
    el('voiceToggle').disabled = !window.speechSynthesis;
    el('voiceToggle').onclick = () => {
        if (voice.speechState === 'speaking') voice.pauseSpeech();
        else if (voice.speechState === 'paused') voice.resumeSpeech();
        else if (lastAssistantText) voice.speak(lastAssistantText);
    };
    el('readVoiceReplies').onchange = () => { if (!el('readVoiceReplies').checked) voice.pauseSpeech(); };
    el('clearVoiceDraft').onclick = () => { input.value = ''; saveDraft(); };
    document.addEventListener('visibilitychange', () => { if (document.hidden) voice.background(); });
    window.addEventListener('pagehide', () => voice.background());
    window.addEventListener('offline', () => {
        voice.background();
        el('voiceStatus').textContent = 'Offline. Voice paused; your draft remains here. Resume or retry when connected.';
    });
    window.addEventListener('beforeunload', event => {
        if (voice.state !== 'idle') { event.preventDefault(); event.returnValue = ''; }
    });
    render(voice, (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder)
        ? 'Microphone recording is unavailable in this browser. You can still type to L.' : null);
});
