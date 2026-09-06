"""Account and source endpoints. No credentials, originals or excerpts in logs."""
import base64
import os
from uuid import UUID
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from core.cognition.account_access import auth_request, account_task_token
from core.cognition.document_evidence import EvidenceStore, MAX_BYTES


class Login(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=8, max_length=256)


class Refresh(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=8192)


class Question(BaseModel):
    request_id: UUID
    document_id: UUID
    page: int = Field(ge=1, le=30)
    question: str = Field(min_length=1, max_length=4000)


def routes(client, tasks):
    router = APIRouter()
    store = EvidenceStore(client)

    @router.get('/account/config')
    def config():
        return {'configured': bool(os.getenv('L_OWNER_EMAIL') and os.getenv('SUPABASE_PUBLISHABLE_KEY'))}

    def owner_email(email):
        if email.strip().casefold() != os.getenv('L_OWNER_EMAIL', '').casefold():
            raise HTTPException(403, 'This account does not have access to this L.')
        return email.strip().lower()

    @router.post('/account/login')
    def login(body: Login):
        return auth_request('token?grant_type=password', {'email': owner_email(body.email), 'password': body.password})

    @router.post('/account/signup')
    def signup(body: Login):
        if len(body.password) < 12:
            raise HTTPException(400, 'Choose a password of at least 12 characters.')
        # Only an explicit user action sends the confirmation email. No admin confirmation.
        result = auth_request('signup', {'email': owner_email(body.email), 'password': body.password})
        if result.get('access_token'):
            return result
        return {'confirmation_required': True}

    @router.post('/account/refresh')
    def refresh(body: Refresh):
        return auth_request('token?grant_type=refresh_token', {'refresh_token': body.refresh_token})

    @router.get('/account/me')
    def me(request: Request):
        return request.state.account

    @router.post('/account/logout')
    def logout(request: Request):
        auth_request('logout?scope=local', token=request.headers['authorization'][7:])
        return {'signed_out': True}

    @router.get('/evidence/files')
    def files(request: Request):
        return {'files': store.list(request.state.account['user_id'])}

    @router.post('/evidence/files')
    async def upload(request: Request, file: UploadFile = File(...)):
        try:
            data = await file.read(MAX_BYTES + 1)
            result = await run_in_threadpool(store.save, request.state.account['user_id'], data,
                                            file.content_type, file.filename)
            return result
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, 'Could not confirm the file was saved. Retry the same file; duplicates are not added. The pilot holds up to 20 files.') from exc
        finally:
            await file.close()

    def owned(request, document_id, original=False):
        try:
            return store.get(request.state.account['user_id'], document_id, original)
        except (ValueError, LookupError) as exc:
            raise HTTPException(404, 'File not found') from exc

    @router.get('/evidence/files/{document_id}')
    def detail(request: Request, document_id: UUID):
        result = owned(request, str(document_id))
        result.pop('user_id', None)
        return result

    @router.get('/evidence/files/{document_id}/original')
    def original(request: Request, document_id: UUID):
        doc = owned(request, str(document_id), True)
        # Attachment delivery prevents active PDF/metadata content from running in L's origin.
        from urllib.parse import quote
        return Response(base64.b64decode(doc['original_base64']), media_type=doc['mime_type'], headers={
            'Content-Disposition': "attachment; filename*=UTF-8''" + quote(doc['filename'], safe=''),
            'X-Content-Type-Options': 'nosniff', 'Cache-Control': 'no-store'})

    @router.post('/evidence/ask')
    def ask(request: Request, body: Question):
        doc = owned(request, str(body.document_id))
        if body.page > doc['page_count'] or not body.question.strip():
            raise HTTPException(400, 'Choose an existing page and enter a question.')
        user_id = request.state.account['user_id']
        payload = {'kind': 'document_evidence', 'request_id': str(body.request_id), 'user_id': user_id,
                   'document_id': str(body.document_id), 'page': body.page, 'question': body.question,
                   'source_sha256': doc['sha256']}
        result = tasks.submit(payload, account_task_token(user_id))
        if result['status'] in ('conflict', 'not_found'):
            raise HTTPException(409, 'That question ID is already in use. Start a new question.')
        return {**result, 'durable': True}

    @router.get('/evidence/tasks/{task_id}')
    def result(request: Request, task_id: UUID):
        return tasks.get(str(task_id), account_task_token(request.state.account['user_id']))

    @router.get('/evidence/tasks')
    def history(request: Request):
        from core.cognition.durable_tasks import owner_identity
        user_id, owner = owner_identity(account_task_token(request.state.account['user_id']))
        rows = client.table('l_chat_tasks').select('request_id,status,request,created_at').eq(
            'user_id', user_id).eq('owner_hash', owner).order('created_at', desc=True).limit(20).execute().data
        return {'tasks': rows}

    return router
