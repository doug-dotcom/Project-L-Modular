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
        const ledger = report.task_ledger, saved = report.saved_answers;
        const counts = [ledger?.tasks_observed, saved?.certified_answers,
            saved?.not_ready_answers, saved?.failed_recovery_records, saved?.unassessed_rows,
            saved?.rows_observed, ledger?.malformed_rows, ledger?.invalid_task_rows];
        if (!counts.every(n => Number.isSafeInteger(n) && n >= 0 && n <= 10000))
            throw new Error('Invalid recovery counts');
        const [tasks, certified, unfinished, failed, unassessed, rows, malformed, invalid] = counts;
        if (certified + unfinished + failed + unassessed !== rows ||
            tasks + malformed !== rows || invalid > tasks)
            throw new Error('Inconsistent recovery counts');
        if (typeof report.scan_complete !== 'boolean' || typeof report.capped !== 'boolean' ||
            typeof report.recovery_ready !== 'boolean') throw new Error('Invalid recovery flags');
        const ready = report.status.startsWith('ready');
        if (report.recovery_ready !== ready ||
            (report.status === 'incomplete_scan' ? report.scan_complete && !report.capped
                : !report.scan_complete || report.capped))
            throw new Error('Inconsistent recovery scope');
        if (ready && !(report.checks?.ledger_consistent === true &&
            report.checks?.all_observed_tasks_certified === true &&
            rows > 0 && certified === rows && unfinished + failed + unassessed + invalid === 0))
            throw new Error('Inconsistent recovery report');
        if (report.status === 'no_tasks' && rows !== 0)
            throw new Error('Inconsistent empty history');
        if (report.status === 'pending_tasks' && !(unfinished > 0 && failed + unassessed + invalid === 0))
            throw new Error('Inconsistent unfinished history');
        const guidance = report.status === 'incomplete_scan'
            ? 'These counts cover only the records checked. Try the check again; a partial result cannot confirm the rest of your history.'
            : failed || unassessed || invalid
            ? 'Review Saved answers for what is available. These checks do not repair records or resend tasks.'
            : unfinished
            ? 'Review unfinished tasks in Saved answers before sending them again; an action may already have happened.'
            : '';
        return {title: messages[report.status][0], body: messages[report.status][1], guidance,
            counts: `Records checked: ${rows} · Results recoverable: ${certified} · Unfinished: ${unfinished} · Recovery checks failed: ${failed} · Could not assess: ${unassessed}`,
            ledger: invalid || malformed
                ? `Task records needing attention: ${invalid + malformed}. These can overlap the recovery counts above.` : ''};
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
        function show(title, body, counts = '', checkedAt = null, busy = false, focusResult = true, details = {}) {
            const {guidance = '', ledger = ''} = details;
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
                if (ledger) {
                    const issues = document.createElement('p'); issues.textContent = ledger; card.append(issues);
                }
                if (guidance) {
                    const next = document.createElement('p'); next.textContent = guidance; card.append(next);
                }
                note.textContent = 'Recoverable results may include failed-task messages; this does not mean the task succeeded. This check covers saved tasks linked to this browser, up to the check’s start time. It checks storage and recovery; answer accuracy still needs review.';
                card.append(note);
            }
            if (checkedAt) {
                const stamp = document.createElement('p');
                stamp.textContent = 'Check started: ' + checkedAt.toLocaleString() + '. This is a point-in-time result.';
                card.append(stamp);
            }
            const actions = document.createElement('div');
            actions.className = 'recovery-check-actions';
            function action(label, handler) {
                const control = document.createElement('button');
                control.type = 'button'; control.textContent = label; control.onclick = handler;
                actions.append(control);
            }
            if (!busy) {
                action('Check again', () => button.click());
                action('Open saved answers', () => {
                    const saved = document.getElementById('savedAnswersAction');
                    if (saved && !saved.disabled) saved.click();
                });
            }
            action('Dismiss', () => { clear(); document.getElementById('uploadBtn')?.focus(); });
            card.append(actions);
            if (focusResult) {
                chat.append(card);
                card.focus();
                chat.scrollTop = chat.scrollHeight;
            }
        }
        function invalidate() {
            if (!card) return;
            generation += 1;
            button.disabled = false;
            show('Saved-answer check is out of date',
                'Tasks or the browser recovery link have changed. Check again for a current result.',
                '', null, false, false);
        }
        window.addEventListener('l-account-ready', clear);
        window.addEventListener('l-task-started', invalidate);
        window.addEventListener('storage', event => {
            if (event.key === null || ['project-l-saved-tasks', 'project-l-recovery-token'].includes(event.key))
                invalidate();
        });
        new MutationObserver(() => {
            if (document.documentElement.dataset.account !== 'ready') clear();
        }).observe(document.documentElement, {attributes: true, attributeFilter: ['data-account']});
        button.onclick = async () => {
            if (button.disabled || document.documentElement.dataset.account !== 'ready') return;
            const request = ++generation;
            const checkedAt = new Date();
            window.lChatTools?.close();
            button.disabled = true;
            show('Checking saved answers…', 'L is checking the saved task records and their answers.', '', null, true);
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
                show(view.title, view.body, view.counts, checkedAt, false, true, view);
            } catch (_) {
                if (request === generation && document.documentElement.dataset.account === 'ready')
                    show('The check could not finish', 'Please try Check saved answers again shortly. Your saved tasks have not been changed.');
            } finally {
                if (request === generation) button.disabled = false;
            }
        };
    });
})();
