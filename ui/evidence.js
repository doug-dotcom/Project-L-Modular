document.addEventListener('DOMContentLoaded', () => {
    const el = id => document.getElementById(id);
    let current = null, busy = false, selection = 0;
    const status = text => { el('evidenceStatus').textContent = text; };
    async function api(path, options) {
        const response = await fetch(path, options);
        const result = await response.json();
        if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Request could not finish.');
        return result;
    }
    async function refresh(selected = '') {
        const result = await api('/evidence/files');
        el('evidenceFiles').replaceChildren(new Option('Choose a saved file', ''));
        for (const file of result.files) el('evidenceFiles').add(new Option(file.filename + ' (' + file.page_count + ' pages)', file.id));
        if (selected) { el('evidenceFiles').value = selected; await choose(); }
    }
    function preview() {
        const page = current?.pages[Number(el('evidencePage').value)-1];
        el('evidencePreview').textContent = page ? (page.text || (page.kind === 'image' ? 'Image saved. Download the original to view it, or ask L about it.' : 'No text extracted on this page. Download the original to inspect it.')) +
            (page.truncated ? '\n[Extraction limited to the first 20,000 characters.]' : '') : '';
    }
    async function choose() {
        const generation = ++selection;
        current = null; el('evidencePreview').textContent = ''; el('evidenceAnswer').textContent = '';
        const id = el('evidenceFiles').value;
        if (!id) return;
        const doc = await api('/evidence/files/' + id);
        if (generation !== selection) return;
        current = doc; el('evidencePage').value = 1; el('evidencePage').max = doc.page_count; preview();
    }
    function show(result) {
        const source = result.evidence;
        el('evidenceAnswer').textContent = result.reply + (source ? '\n\nSource: ' + source.filename + ', physical page ' + source.page +
            '\n' + (source.quotes || []).map(q => '“' + q + '”').join('\n') +
            (source.kind === 'image' ? '\nImage interpretation by the model; inspect the original for confirmation.' : '') : '');
        if (window.lVoice) window.lVoice.onReply(result.reply, !result.error);
    }
    async function recover(id) {
        // One bounded polling window. Returning later uses the durable history.
        for (let n=0; n<60; n++) {
            const result = await api('/evidence/tasks/' + id);
            if (['ready','failed','interrupted'].includes(result.status)) {
                show(result.result || {reply:'This question was interrupted. Review before starting another.'});
                status(result.status === 'ready' ? 'Answer recovered from your account.' : 'Question did not complete.');
                return;
            }
            if (result.status === 'not_found') throw new Error('Saved question not found for this account.');
            await new Promise(resolve => setTimeout(resolve,2000));
        }
        status('Still processing. Use Saved file answers to check later.');
    }
    async function history() {
        const result = await api('/evidence/tasks');
        el('evidenceTasks').replaceChildren();
        for (const task of result.tasks) {
            const button = document.createElement('button');
            button.textContent = task.request.question + ' — ' + task.status;
            button.onclick = () => recover(task.request_id).catch(error => status(error.message));
            el('evidenceTasks').appendChild(button);
        }
    }
    window.lEvidenceUpload = async file => {
        if (!file || busy) return;
        if (window.lVoice && !window.lVoice.canSend()) return;
        el('evidencePanel').open = true;
        if (file.size > 5*1024*1024) { status('Choose a file under 5 MB.'); return; }
        busy = true; status('Saving your original and reading its pages…');
        try {
            const body = new FormData(); body.append('file',file);
            const result = await api('/evidence/files', {method:'POST',body});
            await refresh(result.id);
            status(result.duplicate ? 'This file was already saved. Opened the existing original.' : 'Original and page evidence saved to your account.');
        } catch(error) { status(error.message); }
        finally { busy = false; el('evidenceUpload').value = ''; el('fileInput').value = ''; }
    };
    el('evidenceUpload').onchange = () => window.lEvidenceUpload(el('evidenceUpload').files[0]);
    el('refreshFiles').onclick = () => refresh().catch(error => status(error.message));
    el('evidenceFiles').onchange = () => choose().catch(error => status(error.message));
    el('evidencePage').onchange = preview;
    el('openOriginal').onclick = async () => {
        if (!current) return;
        const doc = current;
        try {
            const response = await fetch('/evidence/files/'+doc.id+'/original');
            if (!response.ok) throw new Error('Original could not be downloaded.');
            const url = URL.createObjectURL(await response.blob());
            const link = document.createElement('a'); link.href=url; link.download=doc.filename;
            document.body.appendChild(link); link.click(); link.remove(); setTimeout(()=>URL.revokeObjectURL(url),60000);
        } catch(error) { status(error.message); }
    };
    el('askEvidence').onclick = async () => {
        const question = el('evidenceQuestion').value.trim();
        if (busy || !current || !question) { status('Choose a file and enter your question.'); return; }
        busy = true; el('askEvidence').disabled = true;
        const candidate = {document_id:current.id, page:Number(el('evidencePage').value), question};
        let pending;
        try { pending = JSON.parse(sessionStorage.getItem('l-evidence-pending') || 'null'); } catch (_) {}
        const same = pending && Object.keys(candidate).every(key => candidate[key] === pending[key]);
        const body = same ? pending : {...candidate, request_id:crypto.randomUUID()};
        const request_id = body.request_id;
        try { sessionStorage.setItem('l-evidence-pending',JSON.stringify(body)); } catch (_) {}
        status('Saving your question…');
        try {
            await api('/evidence/ask', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
            status('L is reading the selected page…'); await recover(request_id);
            try { sessionStorage.removeItem('l-evidence-pending'); } catch (_) {}
        } catch(error) { status(error.message + ' Check Saved file answers before submitting again.'); }
        finally { busy=false; el('askEvidence').disabled=false; }
    };
    el('evidenceHistory').onclick = () => history().catch(error=>status(error.message));
    window.addEventListener('l-account-ready', () => refresh().catch(error=>status(error.message)));
});
