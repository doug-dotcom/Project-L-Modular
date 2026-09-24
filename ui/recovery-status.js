/* On-demand recovery diagnostics. All displayed copy is fixed or numeric. */
(() => {
    const messages = {
        ready: ['Saved answers checked', 'The checked task records and saved answers passed recovery checks.'],
        ready_with_legacy: ['Saved answers checked — includes older answers', 'Recovery checks passed. Some older answers use legacy checks with less authentication evidence.'],
        pending_tasks: ['Some tasks are unfinished', 'Saved results passed their checks, but unfinished or interrupted tasks remain. Open Saved answers to review them before sending again.'],
        needs_attention: ['Some saved records need attention', 'A task record, saved answer or verification problem prevented a clear recovery result. Open Saved answers to review what is available.'],
        incomplete_scan: ['The check is incomplete', 'L could not check the entire selected history. This result cannot confirm that every saved answer is recoverable.'],
        no_tasks: ['No saved tasks found for this browser', 'This browser’s recovery link has no saved tasks in the checked history. Another browser may have a different link.'],
    };
    function describe(report) {
        if (!report || report.mode !== 'durable_recovery_readiness' ||
            !Object.hasOwn(messages, report.status)) throw new Error('Invalid recovery report');
        const counts = [report.task_ledger?.tasks_observed, report.saved_answers?.certified_answers,
                        report.saved_answers?.not_ready_answers];
        if (!counts.every(n => Number.isSafeInteger(n) && n >= 0 && n <= 10000))
            throw new Error('Invalid recovery counts');
        if (counts[1] + counts[2] > counts[0]) throw new Error('Inconsistent recovery counts');
        if (report.status.startsWith('ready') && !(report.recovery_ready === true &&
            report.scan_complete === true && report.capped === false &&
            report.checks?.ledger_consistent === true &&
            report.checks?.all_observed_tasks_certified === true &&
            counts[0] > 0 && counts[1] === counts[0] && counts[2] === 0))
            throw new Error('Inconsistent recovery report');
        return {title: messages[report.status][0], body: messages[report.status][1],
            counts: `Tasks checked: ${counts[0]} · Answers recoverable: ${counts[1]} · Unfinished: ${counts[2]}`};
    }
    if (typeof module !== 'undefined' && module.exports) module.exports = {describe};
    if (typeof document === 'undefined') return;
    document.addEventListener('DOMContentLoaded', () => {
        const button = document.getElementById('checkSavedAnswersAction');
        const chat = document.getElementById('chat');
        let card, generation = 0;
        function clear() {
            generation += 1;
            card?.remove(); card = null;
            button.disabled = false;
        }
        function show(title, body, counts = '') {
            if (!card) {
                card = document.createElement('section');
                card.className = 'msg assistant';
                card.id = 'savedAnswerCheck';
                card.setAttribute('role', 'status');
                card.setAttribute('aria-live', 'polite');
                card.setAttribute('tabindex', '-1');
            }
            card.replaceChildren();
            const heading = document.createElement('strong'); heading.textContent = title;
            const text = document.createElement('p'); text.textContent = body;
            card.append(heading, text);
            if (counts) {
                const totals = document.createElement('p'); totals.textContent = counts; card.append(totals);
                const note = document.createElement('small');
                note.textContent = 'This check covers saved tasks linked to this browser, up to the check’s start time. It checks storage and recovery; answer accuracy still needs review.';
                card.append(note);
            }
            chat.append(card);
            card.focus();
            chat.scrollTop = chat.scrollHeight;
        }
        window.addEventListener('l-account-ready', clear);
        new MutationObserver(() => {
            if (document.documentElement.dataset.account !== 'ready') clear();
        }).observe(document.documentElement, {attributes: true, attributeFilter: ['data-account']});
        button.onclick = async () => {
            if (button.disabled || document.documentElement.dataset.account !== 'ready') return;
            const request = ++generation;
            window.lChatTools?.close();
            button.disabled = true;
            show('Checking saved answers…', 'L is checking the saved task records and their answers.');
            try {
                const token = localStorage.getItem('project-l-recovery-token');
                if (!token) {
                    show('No recovery link in this browser', 'Send a message here first, or use the browser where you saved your tasks.');
                    return;
                }
                const report = await fetchChatJson('/cognition/recovery-readiness?page_size=100&max_rows=10000',
                    {method: 'GET', cache: 'no-store', headers: {'X-L-Recovery-Token': token}}, 30000);
                if (request !== generation || document.documentElement.dataset.account !== 'ready') return;
                const view = describe(report);
                show(view.title, view.body, view.counts);
            } catch (_) {
                if (request === generation && document.documentElement.dataset.account === 'ready')
                    show('The check could not finish', 'Please try Check saved answers again shortly. Your saved tasks have not been changed.');
            } finally {
                if (request === generation) button.disabled = false;
            }
        };
    });
})();
