const assert = require('assert');

function source() {
    const fs = require('fs');
    return fs.readFileSync('ui/concierge-completions.js', 'utf8');
}

(function test_completion_consumer_is_answer_hash_bound() {
    const text = source();
    assert(text.includes('/foundation/completions/claim'));
    assert(text.includes('/foundation/completions/'));
    assert(text.includes('finalAnswerSha256'));
    assert(text.includes('sha256HexText'));
    assert(text.includes('completion-answer-integrity-mismatch'));
})();

(function test_completion_consumer_acknowledges_only_after_render_path() {
    const text = source();
    const render = text.indexOf('render(eventId, eventType, answer)');
    const ack = text.indexOf('await acknowledge(eventId, leaseToken)');
    assert(render >= 0);
    assert(ack > render);
    assert(text.includes("eventType === 'retry-abandoned'"));
    assert(text.includes('project-l-concierge-completions-v1'));
})();

(function test_completion_polling_is_bounded_and_account_scoped() {
    const text = source();
    assert(text.includes("dataset.account === 'ready'"));
    assert(text.includes('document.visibilityState'));
    assert(text.includes('count < 3'));
    assert(text.includes('POLL_MS = 30000'));
})();
