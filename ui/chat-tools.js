/* One compact, keyboard-accessible tray. Closing it preserves files and voice state. */
document.addEventListener('DOMContentLoaded', () => {
    const el = id => document.getElementById(id);
    const tray = el('chatTools'), toggle = el('uploadBtn');
    const files = el('evidencePanel'), voice = el('voicePanel');
    function close() {
        tray.hidden = true;
        toggle.setAttribute('aria-expanded', 'false');
        toggle.setAttribute('aria-label', 'Open chat tools');
        toggle.focus();
    }
    function show(section) {
        tray.hidden = false;
        toggle.setAttribute('aria-expanded', 'true');
        toggle.setAttribute('aria-label', 'Close chat tools');
        files.hidden = section !== 'files';
        voice.hidden = section !== 'voice';
        files.open = section === 'files';
        voice.open = section === 'voice';
        el('privateFilesAction').setAttribute('aria-expanded', String(section === 'files'));
        el('spokenAction').setAttribute('aria-expanded', String(section === 'voice'));
    }
    toggle.onclick = () => {
        if (!tray.hidden) close();
        else { show(); el('attachFileAction').focus(); }
    };
    el('attachFileAction').onclick = () => el('fileInput').click();
    el('privateFilesAction').onclick = () => show('files');
    el('spokenAction').onclick = () => show('voice');
    el('closeChatTools').onclick = close;
    tray.addEventListener('keydown', event => {
        if (event.key === 'Escape') { event.preventDefault(); close(); }
    });
    window.lChatTools = {show, close};
});
