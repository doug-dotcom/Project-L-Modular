"""Server-verified account boundary; recovery capabilities are not identities."""
import hashlib
import hmac
import os
from uuid import UUID

import httpx
import jwt
from fastapi import HTTPException


def auth_request(path, payload=None, token=None):
    url = os.getenv('SUPABASE_URL', '').rstrip('/')
    key = os.getenv('SUPABASE_PUBLISHABLE_KEY', '')
    if not url or not key:
        raise HTTPException(503, 'Account sign-in is not configured yet.')
    headers = {'apikey': key}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with httpx.Client(timeout=15) as client:
            response = client.post(url + '/auth/v1/' + path, json=payload, headers=headers)
        if response.status_code >= 400:
            # Never expose provider bodies (may include account/session details).
            raise HTTPException(429 if response.status_code == 429 else 400,
                                'Sign-in could not finish. Check your details and email confirmation, then try again.')
        return response.json() if response.content else {}
    except httpx.HTTPError as exc:
        raise HTTPException(503, 'Account service is temporarily unavailable.') from exc


def require_account(client, authorization):
    if not isinstance(authorization, str) or not authorization.startswith('Bearer '):
        raise HTTPException(401, 'Please sign in to L.')
    token = authorization[7:]
    if len(token) > 8192 or client is None:
        raise HTTPException(401, 'Please sign in to L.')
    try:
        # Remote validation first. Unverified decoding below is ONLY for session lookup.
        user = client.auth.get_user(token).user
        claims = jwt.decode(token, options={'verify_signature': False})
        user_id = str(UUID(str(user.id)))
        session_id = str(UUID(claims.get('session_id', '')))
        if claims.get('sub') != user_id or not user.email_confirmed_at or user.is_anonymous:
            raise ValueError('Unverified account')
        allowed = os.getenv('L_OWNER_EMAIL', '').strip().casefold()
        if not allowed or str(user.email).casefold() != allowed:
            raise HTTPException(403, 'This account does not have access to this L.')
        # Also rejects revoked sessions immediately and binds access to one provisioned owner.
        allowed_session = client.rpc('l_account_session_valid', {
            'p_user': user_id, 'p_session': session_id}).execute().data
        if allowed_session is not True:
            raise HTTPException(403, 'This L account is not activated, or the session has ended.')
        return {'user_id': user_id, 'email': user.email}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(401, 'Your session could not be verified. Please sign in again.') from exc


def account_task_token(user_id):
    # Stable across devices/restarts; never accepted from a client or returned to one.
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY', '')
    if not key:
        raise RuntimeError('Task ownership is unavailable')
    return hmac.new(key.encode(), ('l-account-tasks:' + str(UUID(user_id))).encode(), hashlib.sha256).hexdigest()
