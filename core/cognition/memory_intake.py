"""Recognise supplied updates and acknowledge only verified raw writes."""
import re


def memory_intake_kind(message):
    text = str(message).strip().lower()
    # Copied assistant preambles and markdown headings are common on mobile.
    text = re.sub(r'^paste this[^:]*:\s*', '', text)
    text = text.lstrip('#* >\n')
    save = bool(re.search(r'\b(?:please )?(?:save|store|remember|record) (?:this|the update|my update|my daily|the report)', text))
    supplied = bool(re.match(r'(?:daily (?:report|update)|bali journal)\b[^\n]*\n', text)) and len(text) > 250
    if not (save or supplied):
        return None
    if re.search(r'\b(?:do not|don.t|never) (?:save|store|remember|record)\b', text):
        return None
    if save and re.search(r'\b(?:just sent|previous message|earlier message|above)\b', text):
        return 'previous_update'
    return 'supplied_update'


def intake_receipt(kind, raw_row):
    saved = isinstance(raw_row, dict) and bool(raw_row.get('id'))
    receipt = {'status': 'saved' if saved else 'failed', 'scope': 'current_message'}
    if saved:
        receipt['raw_id'] = raw_row['id']
    if kind == 'previous_update':
        reply = ('I cannot confirm the earlier update from this message alone. '
                 'Please paste the full update again, starting with "Please save this update:".')
        receipt['previous_update_status'] = 'not_verified'
    elif saved:
        reply = 'Your update was saved to raw memory. It does not need an evidence search.'
    else:
        reply = 'I could not confirm that your update was saved. Please try sending it again.'
    return {'reply': reply, 'error': not saved, 'memory_intake': receipt}
