document.addEventListener('DOMContentLoaded', () => {
    const el = id => document.getElementById(id);
    let current = null, busy = false, selection = 0, accountVersion = 0, recoveryVersion = 0;
    const status = text => { el('evidenceStatus').textContent = text; };
    const accountCurrent = version => version === accountVersion && document.documentElement.dataset.account === 'ready';
    const recoveryCurrent = (account, version) => accountCurrent(account) && version === recoveryVersion;
    function stopRecovery() {
        recoveryVersion += 1;
        el('evidenceAnswer').textContent = ''; status('');
    }
    function resetAccount() {
        accountVersion += 1; selection += 1; stopRecovery();
        current = null; busy = false; el('askEvidence').disabled = false;
        el('evidenceFiles').replaceChildren(new Option('Choose a saved file', ''));
        el('evidenceFiles').value = ''; el('evidenceTasks').replaceChildren();
        el('evidencePreview').textContent = ''; el('evidenceQuestion').value = '';
        el('evidencePage').value = 1; el('evidencePage').max = 1;
        el('evidenceUpload').value = ''; el('fileInput').value = '';
    }
    function reportFailure(action) {
        const account = accountVersion;
        if (!accountCurrent(account)) return Promise.resolve();
        return action().catch(error => { if (accountCurrent(account)) status(error.message); });
    }
    async function fileRequest(path, options, read, timeoutMs = 15000) {
        const controller = new AbortController();
        let timer;
        try {
            const timeout = new Promise((_, reject) => {
                timer = setTimeout(() => {
                    const error = new Error('File request timed out. Please try again.');
                    error.code = 'file_timeout'; reject(error); controller.abort();
                }, timeoutMs);
            });
            // Include body reads and transports that do not honour abort.
            const request = (async () => read(await fetch(path, {...options, signal: controller.signal})))();
            return await Promise.race([request, timeout]);
        } finally { clearTimeout(timer); }
    }
    async function api(path, options, timeoutMs) {
        return fileRequest(path, options, async response => {
            const result = await response.json();
            if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'Request could not finish.');
            return result;
        }, timeoutMs);
    }
    async function refresh(selected = '') {
        const account = accountVersion, chosen = selection;
        if (!accountCurrent(account)) return false;
        let result;
        try { result = await api('/evidence/files'); }
        catch (error) {
            if (accountCurrent(account) && chosen === selection) status(error.message);
            return false;
        }
        if (!accountCurrent(account) || chosen !== selection) return false;
        el('evidenceFiles').replaceChildren(new Option('Choose a saved file', ''));
        for (const file of result.files) el('evidenceFiles').add(new Option(file.filename + ' (' + file.page_count + ' pages)', file.id));
        el('evidenceFiles').value = selected;
        return choose();
    }
    function preview() {
        const page = current?.pages[Number(el('evidencePage').value)-1];
        el('evidencePreview').textContent = page ? (page.text || (page.kind === 'image' ? 'Image saved. Download the original to view it, or ask L about it.' : 'No text extracted on this page. Download the original to inspect it.')) +
            (page.truncated ? '\n[Extraction limited to the first 20,000 characters.]' : '') : '';
    }
    async function choose() {
        const generation = ++selection, account = accountVersion;
        stopRecovery(); current = null; el('evidencePreview').textContent = '';
        if (!accountCurrent(account)) return false;
        const id = el('evidenceFiles').value;
        if (!id) return true;
        try {
            const doc = await api('/evidence/files/' + id);
            if (generation !== selection || !accountCurrent(account)) return false;
            current = doc; el('evidencePage').value = 1; el('evidencePage').max = doc.page_count; preview();
            return true;
        } catch (error) {
            if (generation === selection && accountCurrent(account)) status(error.message);
            return false;
        }
    }
    function show(result) {
        const source = result.evidence;
        el('evidenceAnswer').textContent = result.reply + (source ? '\n\nSource: ' + source.filename + ', physical page ' + source.page +
            '\n' + (source.quotes || []).map(q => '“' + q + '”').join('\n') +
            (source.kind === 'image' ? '\nImage interpretation by the model; inspect the original for confirmation.' : '') : '');
        try { window.lVoice?.onReply(result.reply, !result.error); } catch (_) {}
    }
    function clearPendingQuestion(id) {
        try {
            const pending = JSON.parse(sessionStorage.getItem('l-evidence-pending') || 'null');
            if (pending?.request_id === id) sessionStorage.removeItem('l-evidence-pending');
        } catch (_) {}
    }
    async function recover(id, generation, account) {
        // One bounded polling window. Returning later uses the durable history.
        const deadline = performance.now() + 120000;
        for (let n=0; n<60; n++) {
            if (!recoveryCurrent(account, generation)) return false;
            const remaining = deadline - performance.now();
            if (remaining <= 0) break;
            let result;
            try {
                result = await fetchChatJson('/evidence/tasks/' + encodeURIComponent(id),
                    {cache:'no-store'}, Math.min(15000, remaining));
            } catch (_) {
                // A transient read failure can recover within this same window.
            }
            if (!recoveryCurrent(account, generation)) return false;
            if (['ready','failed','interrupted'].includes(result?.status)) {
                show(result.result || {reply:'This question was interrupted. Review before starting another.'});
                if (!recoveryCurrent(account, generation)) return false;
                clearPendingQuestion(id);
                status(result.status === 'ready' ? 'Answer recovered from your account.' : 'Question did not complete.');
                return true;
            }
            if (result?.status === 'not_found') throw new Error('Saved question not found for this account.');
            const delay = Math.min(2000, deadline - performance.now());
            if (delay > 0) await new Promise(resolve => setTimeout(resolve, delay));
        }
        if (recoveryCurrent(account, generation))
            status('I stopped waiting for this file answer. L may still be working. Use Saved file answers to check before submitting again.');
        return false;
    }
    async function history() {
        const account = accountVersion;
        if (!accountCurrent(account)) return;
        const result = await api('/evidence/tasks');
        if (!accountCurrent(account)) return;
        el('evidenceTasks').replaceChildren();
        for (const task of result.tasks) {
            const button = document.createElement('button');
            button.textContent = task.request.question + ' — ' + task.status;
            button.onclick = () => {
                if (!accountCurrent(account)) return;
                stopRecovery(); const generation = recoveryVersion;
                status('Checking this saved file answer…');
                return recover(task.request_id, generation, account).catch(error => {
                    if (recoveryCurrent(account, generation)) status(error.message);
                });
            };
            el('evidenceTasks').appendChild(button);
        }
    }
    window.lEvidenceUpload = async file => {
        const account = accountVersion;
        if (!accountCurrent(account) || !file || busy) return;
        if (window.lVoice && !window.lVoice.canSend()) return;
        if (window.lChatTools) window.lChatTools.show('files');
        else el('evidencePanel').open = true;
        if (file.size > 5*1024*1024) { status('Choose a file under 5 MB.'); return; }
        busy = true; status('Saving your original and reading its pages…');
        try {
            const body = new FormData(); body.append('file',file);
            const result = await api('/evidence/files', {method:'POST',body}, 60000);
            if (!accountCurrent(account)) return;
            const opened = await refresh(result.id);
            if (!accountCurrent(account) || !opened) return;
            status(result.duplicate ? 'This file was already saved. Opened the existing original.' : 'Original and page evidence saved to your account.');
        } catch(error) {
            if (accountCurrent(account)) status(error.code === 'file_timeout'
                ? 'I stopped waiting for this upload. It may still finish saving. Refresh your saved files before uploading again.'
                : error.message + ' Refresh your saved files before uploading again.');
        }
        finally { if (accountCurrent(account)) { busy = false; el('evidenceUpload').value = ''; el('fileInput').value = ''; } }
    };
    el('evidenceUpload').onchange = () => window.lEvidenceUpload(el('evidenceUpload').files[0]);
    el('refreshFiles').onclick = () => reportFailure(() => refresh());
    el('evidenceFiles').onchange = choose;
    el('evidencePage').onchange = () => { stopRecovery(); preview(); };
    el('openOriginal').onclick = async () => {
        const account = accountVersion;
        if (!accountCurrent(account) || !current) return;
        const doc = current;
        try {
            const blob = await fileRequest('/evidence/files/'+doc.id+'/original', {}, async response => {
                if (!response.ok) throw new Error('Original could not be downloaded.');
                return response.blob();
            }, 30000);
            if (!accountCurrent(account)) return;
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a'); link.href=url; link.download=doc.filename;
            document.body.appendChild(link); link.click(); link.remove(); setTimeout(()=>URL.revokeObjectURL(url),60000);
        } catch(error) { if (accountCurrent(account)) status(error.message); }
    };
    el('askEvidence').onclick = async () => {
        const account = accountVersion;
        if (!accountCurrent(account)) return;
        const question = el('evidenceQuestion').value.trim();
        if (busy || !current || !question) { status('Choose a file and enter your question.'); return; }
        const candidate = {document_id:current.id, page:Number(el('evidencePage').value), question};
        const validId = id => typeof id === 'string' && /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id);
        let body;
        try {
            const raw = sessionStorage.getItem('l-evidence-pending');
            const pending = raw === null ? null : JSON.parse(raw);
            if (raw !== null && (!pending || typeof pending !== 'object' || Array.isArray(pending) || !validId(pending.request_id)))
                throw new Error('Invalid saved recovery details');
            const same = pending && Object.keys(candidate).every(key => candidate[key] === pending[key]);
            body = {...candidate, request_id:same ? pending.request_id : crypto.randomUUID()};
            if (!validId(body.request_id)) throw new Error('Invalid request identifier');
            // Save the recovery handle before changing the view or submitting.
            sessionStorage.setItem('l-evidence-pending', JSON.stringify(body));
        } catch (_) {
            status('This question was not sent because its recovery details could not be prepared. Your question is still here. Check Saved file answers before trying again.');
            return;
        }
        const request_id = body.request_id;
        stopRecovery(); const generation = recoveryVersion;
        busy = true; el('askEvidence').disabled = true;
        status('Saving your question…');
        try {
            try {
                await fetchChatJson('/evidence/ask',
                    {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
            } catch (_) {
                // An uncertain acknowledgement does not justify another submission.
            }
            if (!recoveryCurrent(account, generation)) return;
            status('L is reading the selected page…'); await recover(request_id, generation, account);
        } catch(error) {
            if (recoveryCurrent(account, generation)) status(error.message + ' Check Saved file answers before submitting again.');
        }
        finally { if (accountCurrent(account)) { busy=false; el('askEvidence').disabled=false; } }
    };
    el('evidenceHistory').onclick = () => reportFailure(history);
    window.addEventListener('l-account-ready', () => { resetAccount(); return reportFailure(() => refresh()); });
    new MutationObserver(() => {
        if (document.documentElement.dataset.account !== 'ready') resetAccount();
    }).observe(document.documentElement, {attributes:true, attributeFilter:['data-account']});
});
