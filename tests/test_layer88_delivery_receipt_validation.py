"""Delivery downgrade and terminal-path regressions, including real browser JS."""
from hashlib import sha256
import json
from pathlib import Path
import re
import subprocess

import httpx
import pytest
from supabase import create_client
from supabase.lib.client_options import SyncClientOptions

from core.cognition.delivery_integrity import (
    require_chat_delivery_payload,
    seal_chat_delivery_payload,
    verify_chat_delivery_payload,
)
from core.cognition.durable_tasks import TaskStore


REQUEST_ID = "10000000-0000-4000-8000-000000000088"
PRIVATE_REPLY = "Exact reply — café 👊\nKeep the original spacing.  "


def canonical_hash(value):
    return sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":")).encode()).hexdigest()


def sealed_payload():
    return seal_chat_delivery_payload({"reply": PRIVATE_REPLY}, request_id=REQUEST_ID)


def old_sealed_payload():
    payload = sealed_payload()
    del payload["delivery_protocol"]
    receipt = payload.pop("delivery_receipt")
    receipt["payload_sha256"] = canonical_hash(payload)
    receipt.pop("receipt_sha256")
    receipt["receipt_sha256"] = canonical_hash(receipt)
    return {**payload, "delivery_receipt": receipt}


def invalid_payloads():
    cases = []
    for receipt in (None, False, 0, "", "receipt", [], {}, ["receipt"]):
        payload = old_sealed_payload()
        payload["delivery_receipt"] = receipt
        cases.append(payload)
    missing = sealed_payload()
    del missing["delivery_receipt"]
    cases.append(missing)
    for field, value in (("version", "2.0"), ("status", "draft"),
                         ("request_id", 88), ("payload_sha256", "x" * 64),
                         ("reply_sha256", None), ("extra", "unknown")):
        payload = sealed_payload()
        receipt = payload["delivery_receipt"]
        receipt[field] = value
        # Even a self-consistent hash must not authorise an unsupported schema.
        receipt.pop("receipt_sha256")
        receipt["receipt_sha256"] = canonical_hash(receipt)
        cases.append(payload)
    changed = sealed_payload()
    changed["reply"] = "Changed after sealing"
    cases.append(changed)
    protocol = sealed_payload()
    protocol["delivery_protocol"] = None
    cases.append(protocol)
    cases.extend([None, [], "not an object", {"reply": 88}])
    return cases


@pytest.mark.parametrize("payload", invalid_payloads())
def test_layer88_invalid_receipts_and_marked_payloads_cannot_downgrade(payload):
    check = verify_chat_delivery_payload(payload, expected_request_id=REQUEST_ID)
    assert check["valid"] is False
    assert check["status"] == "mismatch"
    assert PRIVATE_REPLY not in json.dumps(check)
    with pytest.raises(ValueError, match="chat_delivery_integrity_mismatch"):
        require_chat_delivery_payload(payload, expected_request_id=REQUEST_ID)


@pytest.mark.parametrize("payload", [sealed_payload(), old_sealed_payload(),
                                    {"reply": "Older unbound answer"}])
def test_layer88_current_and_legacy_answers_remain_readable(payload):
    assert require_chat_delivery_payload(payload, expected_request_id=REQUEST_ID)["valid"]


@pytest.mark.parametrize("status", ["ready", "failed", "interrupted"])
@pytest.mark.parametrize("payload", [invalid_payloads()[0], invalid_payloads()[8],
                                    "invalid stored result"])
def test_layer88_database_read_withholds_invalid_result_for_every_terminal_status(status, payload):
    requests = []

    def respond(request):
        requests.append(request)
        return httpx.Response(200, json=[{"status": status, "result": payload}])

    with httpx.Client(transport=httpx.MockTransport(respond)) as transport:
        client = create_client("https://example.supabase.co", "ci-placeholder",
                               options=SyncClientOptions(httpx_client=transport))
        result = TaskStore(client).get(REQUEST_ID, "x" * 64)

    assert result["status"] == "failed"
    assert result["result"]["error"] is True
    assert PRIVATE_REPLY not in json.dumps(result)
    assert not result["delivery_integrity"]["valid"]
    assert len(requests) == 1
    # Preserve the three ownership filters while validating the returned JSON.
    assert requests[0].url.params["request_id"] == "eq." + REQUEST_ID
    assert requests[0].url.params["owner_hash"].startswith("eq.")
    assert requests[0].url.params["user_id"].startswith("eq.")


def test_layer88_write_rejects_missing_receipt_before_any_database_call():
    store = TaskStore(None)
    with pytest.raises(ValueError, match="chat_delivery_integrity_mismatch"):
        store.finish(REQUEST_ID, "worker", invalid_payloads()[8])


def test_layer88_browser_verification_and_all_terminal_display_paths():
    html = Path("ui/index.html").read_text()
    source = next(script for script in re.findall(r"<script>(.*?)</script>", html, re.S)
                  if "const API_URL" in script)
    vectors = [
        {"payload": payload, "valid": False} for payload in invalid_payloads()
    ] + [{"payload": payload, "valid": True} for payload in (
        sealed_payload(), old_sealed_payload(), {"reply": "Older unbound answer"})]
    script = r'''
const assert = require('node:assert/strict');
const vm = require('node:vm');
const storage = new Map();
const elements = new Map();
const shown = [];
const voiced = [];
let envelope;
let fetches = 0;
function element() {
 return {textContent: '', value: '', children: [], remove() {},
   appendChild(child) { this.children.push(child); shown.push(child); },
   insertBefore(child) { elements.set(child.id, child); }};
}
for (const id of ['chat', 'chatToolsActions', 'closeChatTools', 'message']) elements.set(id, element());
const context = {
 TextEncoder, window: {crypto: require('node:crypto').webcrypto,
   lVoice: {canSend: () => true, saveDraft() {}, onReply: (...args) => voiced.push(args)}},
 document: {addEventListener() {}, createElement: element, getElementById: id => elements.get(id)},
 localStorage: {getItem: k => storage.get(k) || null, setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k)},
 setTimeout: fn => fn(),
 fetch: async (url, options) => {
   fetches++;
   // Acknowledge a new task once; subsequent requests only retrieve its result.
   return {ok: true, json: async () => options?.method === 'POST' ? {status: 'queued'} : envelope};
 },
};
vm.createContext(context);
vm.runInContext(SOURCE, context);
(async () => {
 for (const vector of VECTORS) {
   context.payload = vector.payload;
   const result = await vm.runInContext('verifyDeliveryReply(payload, REQUEST_ID)', context);
   assert.equal(result.valid, vector.valid, JSON.stringify(vector));
 }
 context.payload = GOOD;
 assert.equal((await vm.runInContext('verifyDeliveryReply(payload, "different-request")', context)).valid, false);
 context.window.crypto = {};
 assert.equal((await vm.runInContext('verifyDeliveryReply(payload, REQUEST_ID)', context)).valid, false);
 context.window.crypto = require('node:crypto').webcrypto;
 for (const status of ['ready', 'failed', 'interrupted']) {
   envelope = {status, result: BAD};
   const before = fetches;
   const result = await vm.runInContext('recoverChatResponse(REQUEST_ID)', context);
   assert.equal(fetches - before, 1);
   assert.equal(result.error, true);
   assert.match(result.reply, /failed delivery integrity/);
   assert.ok(!JSON.stringify(result).includes(PRIVATE_REPLY));
 }
 envelope = {status: 'failed', result: {reply: 'Safe failure'}};
 const failed = await vm.runInContext('recoverChatResponse(REQUEST_ID)', context);
 assert.equal(failed.error, true);
 assert.equal(failed.reply, 'Safe failure');
 envelope = {status: 'ready', result: GOOD, freshness: {status: 'superseded'}};
 const recovered = await vm.runInContext('recoverChatResponse(REQUEST_ID)', context);
 assert.ok(recovered.reply.endsWith(PRIVATE_REPLY));
 assert.match(recovered.reply, /facts have since changed/);
 // Exercise the Saved answers button, not only its verifier helper.
 await vm.runInContext('resumePendingRequest()', context);
 vm.runInContext('rememberPendingRequest(REQUEST_ID, "test"); clearPendingRequest(REQUEST_ID);', context);
 for (const status of ['ready', 'failed', 'interrupted']) {
   envelope = {status, result: BAD};
   shown.length = 0;
   await elements.get('savedAnswersAction').onclick();
   assert.ok(shown.some(item => item.textContent.includes('failed delivery integrity')));
   assert.ok(!shown.some(item => item.textContent.includes(PRIVATE_REPLY)));
 }
 // New chat completion must also withhold the damaged text from rendering/TTS.
 envelope = {status: 'failed', result: BAD};
 shown.length = 0;
 elements.get('message').value = 'test message';
 await vm.runInContext('sendMessage()', context);
 assert.ok(!shown.some(item => item.textContent.includes(PRIVATE_REPLY)));
 assert.equal(voiced.length, 1);
 assert.equal(voiced[0][1], false);
 assert.ok(!voiced[0][0].includes(PRIVATE_REPLY));
})().catch(error => {console.error(error); process.exitCode = 1;});
'''
    constants = {"REQUEST_ID": REQUEST_ID, "GOOD": sealed_payload(),
                 "BAD": invalid_payloads()[0], "PRIVATE_REPLY": PRIVATE_REPLY}
    script = script.replace("SOURCE", json.dumps(source)).replace("VECTORS", json.dumps(vectors))
    script = "\n".join(f"const {key} = {json.dumps(value)};" for key, value in constants.items()) + "\n" + script
    script = script.replace("vm.createContext(context);", "Object.assign(context, {REQUEST_ID}); vm.createContext(context);")
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
