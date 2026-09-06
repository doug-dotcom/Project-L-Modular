"""Backend operator: curated timeline writes only, never run by the chat model.

JSON input via stdin avoids personal facts in shell history. --help for operations.
Every write requires an explicit source passage and an operator-reviewed claim.
"""
import argparse
import json
import os
import sys

from dotenv import load_dotenv
from supabase import create_client
from core.cognition.temporal_memory import memory_owner


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=['write', 'observe', 'request-removal'])
    args = parser.parse_args()
    load_dotenv()
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY')
    if not key or not os.getenv('SUPABASE_URL'):
        raise SystemExit('Existing backend Supabase configuration required.')
    client = create_client(os.environ['SUPABASE_URL'], key)
    data = json.load(sys.stdin)
    if 'p_user' in data:
        raise SystemExit('Owner is server-configured; do not supply p_user in input.')
    data['p_user'] = memory_owner()
    name = {'write': 'l_fact_write', 'observe': 'l_fact_observe',
            'request-removal': 'l_fact_request_removal'}[args.operation]
    try:
        result = client.rpc(name, data).execute().data
    except Exception:
        raise SystemExit('Fact operation rejected. Check dates, passage, replacement target and request identifier.')
    # Do not emit source contents or deletion inventories to general logs.
    print(json.dumps({k: v for k, v in result.items() if k != 'inventory'}))


if __name__ == '__main__':
    main()
