"""Server-verified account boundary; recovery capabilities are not identities."""
import hashlib
import hmac
import os
from uuid import UUID

import httpx
import jwt
from fastapi import HTTPException


def auth_request(path, payload=None, token=None, method='POST'):
    url = os.getenv('SUPABASE_URL', '').rstrip('/')
    key = os.getenv('SUPABASE_PUBLISHABLE_KEY', '')
    if not url or not key:
        raise HTTPException(503, 'Account sign-in is not configured yet.')
    headers = {'apikey': key}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    try:
        with httpx.Client(timeout=15) as client:
            response = client.request(method, url + '/auth/v1/' + path, json=payload, headers=headers)
        if response.status_code >= 400:
            # Never expose provider bodies (may include account/session details).
            messages = {
                'invalid_credentials': 'Email or password was not accepted. Use Forgot password to reset your password.',
                'email_not_confirmed': 'Confirm your email using the newest confirmation email, then sign in.',
                'same_password': 'Choose a different new password.',
                'weak_password': 'Choose a stronger password of at least 12 characters.',
                'otp_expired': 'This link has expired or already been used. Request a new reset email.',
            }
            try:
                code = response.json().get('error_code', '')
            except (ValueError, AttributeError):
                code = ''
            message = messages.get(code, 'Account request could not finish. Please try again.')
            if response.status_code == 429:
                message = 'Too many requests. Please wait before requesting another email or trying again.'
            raise HTTPException(429 if response.status_code == 429 else 400, message)
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
        # Validate the exact bearer token against Supabase Auth over its REST endpoint.
        # This avoids mutating or depending on the shared server-side Supabase auth client.
        user = auth_request('user', token=token, method='GET')
        claims = jwt.decode(token, options={'verify_signature': False})
        user_id = str(UUID(str(user.get('id', ''))))
        session_id = str(UUID(str(claims.get('session_id', ''))))
        email = str(user.get('email') or '')
        confirmed = bool(user.get('email_confirmed_at') or user.get('confirmed_at'))
        anonymous = bool(user.get('is_anonymous', False))
        if str(claims.get('sub') or '') != user_id or not confirmed or anonymous:
            raise ValueError('Unverified account')
        allowed = os.getenv('L_OWNER_EMAIL', '').strip().casefold()
        if not allowed or email.casefold() != allowed:
            raise HTTPException(403, 'This account does not have access to this L.')
        # Also rejects revoked sessions immediately and binds access to one provisioned owner.
        allowed_session = client.rpc('l_account_session_valid', {
            'p_user': user_id, 'p_session': session_id}).execute().data
        if allowed_session is not True:
            raise HTTPException(403, 'This L account is not activated, or the session has ended.')
        return {'user_id': user_id, 'email': email}
    except HTTPException as exc:
        # A bearer token rejected by Supabase is an authentication failure, not a bad form request.
        if exc.status_code == 400 and exc.detail == 'Account request could not finish. Please try again.':
            raise HTTPException(401, 'Your session could not be verified. Please sign in again.') from exc
        raise
    except Exception as exc:
        raise HTTPException(401, 'Your session could not be verified. Please sign in again.') from exc


def account_task_token(user_id):
    # Stable across devices/restarts; never accepted from a client or returned to one.
    key = os.getenv('SUPABASE_SERVICE_ROLE_KEY') or os.getenv('SUPABASE_KEY', '')
    if not key:
        raise RuntimeError('Task ownership is unavailable')
    return hmac.new(key.encode(), ('l-account-tasks:' + str(UUID(user_id))).encode(), hashlib.sha256).hexdigest()
