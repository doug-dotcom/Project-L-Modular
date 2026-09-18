import base64
from io import BytesIO
import json
import subprocess
from types import SimpleNamespace
from uuid import uuid4

import jwt
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from core.cognition.account_access import require_account, account_task_token
from core.cognition.document_evidence import EvidenceStore, extract_pages, answer_from_document


def pdf_bytes():
    writer = PdfWriter()
    for text in ['Project Cedar has 7 blue boats.', 'Project Cedar has 12 red boats.']:
        page = writer.add_blank_page(width=300, height=300)
        font = DictionaryObject({NameObject('/Type'):NameObject('/Font'), NameObject('/Subtype'):NameObject('/Type1'), NameObject('/BaseFont'):NameObject('/Helvetica')})
        page[NameObject('/Resources')] = DictionaryObject({NameObject('/Font'):DictionaryObject({NameObject('/F1'):writer._add_object(font)})})
        stream = DecodedStreamObject(); stream.set_data(('BT /F1 12 Tf 10 200 Td ('+text+') Tj ET').encode())
        page[NameObject('/Contents')] = writer._add_object(stream)
    out=BytesIO(); writer.write(out); return out.getvalue()


def test_physical_pdf_pages_preserve_distinct_evidence():
    pages = extract_pages(pdf_bytes(), 'application/pdf')
    assert len(pages) == 2
    assert '7 blue' in pages[0]['text'] and '12 red' in pages[1]['text']
    assert pages[0]['page'] == 1 and pages[1]['page'] == 2


@pytest.mark.parametrize('data,mime', [(b'bad','application/pdf'),(b'not image','image/png'),(b'', 'image/png'),(b'x'*5242881,'image/png'),(b'<script/>','text/html')])
def test_invalid_files_are_rejected(data,mime):
    with pytest.raises(ValueError): extract_pages(data,mime)


def test_valid_image_and_mismatched_mime():
    out=BytesIO(); Image.new('RGB',(10,10),'blue').save(out,format='PNG')
    assert extract_pages(out.getvalue(),'image/png')[0]['kind']=='image'
    with pytest.raises(ValueError): extract_pages(out.getvalue(),'image/jpeg')


def test_empty_pdf_page_is_explicit_not_model_evidence():
    writer=PdfWriter(); writer.add_blank_page(width=100,height=100)
    out=BytesIO(); writer.write(out)
    assert extract_pages(out.getvalue(),'application/pdf')[0]['kind']=='no_text'


def auth_client(user_id, confirmed=True, anonymous=False, valid_session=True, email='owner@example.com'):
    user=SimpleNamespace(id=user_id, email=email,email_confirmed_at='2026-09-06' if confirmed else None,is_anonymous=anonymous)
    return SimpleNamespace(auth=SimpleNamespace(get_user=lambda token:SimpleNamespace(user=user)),
        rpc=lambda *a,**kw:SimpleNamespace(execute=lambda:SimpleNamespace(data=valid_session)))


def token(user_id, session_id=None):
    return 'Bearer '+jwt.encode({'sub':user_id,'session_id':session_id or str(uuid4())},'synthetic-test-only-key-long-enough',algorithm='HS256')


def stub_verified_user_endpoint(monkeypatch, client):
    # Account validation now uses REST, so mock that boundary rather than
    # accidentally passing negative tests because Auth is unconfigured.
    def lookup(path, payload=None, token=None, method='POST'):
        assert path == 'user' and method == 'GET'
        return vars(client.auth.get_user(token).user)
    monkeypatch.setattr('core.cognition.account_access.auth_request', lookup)


@pytest.mark.parametrize('reason',['missing','unconfirmed','anonymous','other_email','revoked','wrong_sub','missing_owner'])
def test_auth_rejects_untrusted_or_wrong_account(monkeypatch,reason):
    user=str(uuid4()); monkeypatch.setenv('L_OWNER_EMAIL','owner@example.com')
    if reason=='missing_owner':monkeypatch.delenv('L_OWNER_EMAIL')
    client=auth_client(user,confirmed=reason!='unconfirmed',anonymous=reason=='anonymous',
                       valid_session=reason!='revoked',email='other@example.com' if reason=='other_email' else 'owner@example.com')
    stub_verified_user_endpoint(monkeypatch, client)
    header='' if reason=='missing' else token(str(uuid4()) if reason=='wrong_sub' else user)
    with pytest.raises(HTTPException): require_account(client,header)


def test_valid_account_and_unforgeable_task_namespace(monkeypatch):
    user=str(uuid4()); monkeypatch.setenv('L_OWNER_EMAIL','owner@example.com')
    monkeypatch.setenv('SUPABASE_SERVICE_ROLE_KEY','synthetic-key')
    client=auth_client(user)
    stub_verified_user_endpoint(monkeypatch, client)
    assert require_account(client,token(user))['user_id']==user
    assert account_task_token(user)==account_task_token(user)
    assert account_task_token(user)!=account_task_token(str(uuid4()))


def test_server_validation_failure_cannot_fall_back_to_decode(monkeypatch):
    monkeypatch.setenv('L_OWNER_EMAIL','owner@example.com')
    def fail(_):raise RuntimeError('private token details')
    client=SimpleNamespace(auth=SimpleNamespace(get_user=fail))
    stub_verified_user_endpoint(monkeypatch, client)
    with pytest.raises(HTTPException) as error:require_account(client,token(str(uuid4())))
    assert 'private token' not in error.value.detail


class Query:
    def __init__(self,rows):self.rows=rows
    def select(self,*a):return self
    def eq(self,k,v):self.rows=[r for r in self.rows if r[k]==v];return self
    def limit(self,*a):return self
    def execute(self):return SimpleNamespace(data=self.rows)


def test_backend_filters_both_document_and_owner():
    a,b=str(uuid4()),str(uuid4()); doc=str(uuid4())
    client=SimpleNamespace(table=lambda _:Query([{'id':doc,'user_id':a}]))
    store=EvidenceStore(client)
    assert store.get(a,doc)['id']==doc
    with pytest.raises(LookupError):store.get(b,doc)


@pytest.mark.parametrize('model_quote,accepted',[('7 blue boats',True),('12 red boats',False),('',False)])
def test_quotes_must_match_selected_page(monkeypatch,model_quote,accepted):
    import core.cognition.document_evidence as module
    doc={'id':str(uuid4()),'filename':'Cedar.pdf','sha256':'a'*64,'pages':[{'page':1,'text':'Cedar has 7 blue boats.','kind':'pdf_text','truncated':False}], 'mime_type':'application/pdf'}
    store=SimpleNamespace(get=lambda *a,**kw:doc)
    monkeypatch.setattr(module,'invoke_model',lambda *a:{'content':json.dumps({'answer':'There are seven blue boats.','quotes':[model_quote]}),'receipt':{'status':'complete'}})
    result=answer_from_document(store,object(),{'user_id':str(uuid4()),'document_id':doc['id'],'source_sha256':'a'*64,'page':1,'question':'How many?'})
    assert bool(result['evidence']['quotes'])==accepted
    assert result['memory_written'] is False
    if not accepted:assert 'could not verify' in result['reply']


def test_wrong_source_version_never_calls_model():
    store=SimpleNamespace(get=lambda *a,**kw:{'sha256':'a'*64})
    with pytest.raises(ValueError):answer_from_document(store,None,{'user_id':str(uuid4()),'document_id':str(uuid4()),'source_sha256':'b'*64})


@pytest.mark.parametrize('path,method',[('/chat/start','POST'),('/chat','POST'),('/voice/transcribe','POST'),('/image/start','POST'),('/cognition/status','GET'),('/evidence/files','GET'),('/evidence/ask','POST'),('/chat/result/'+str(uuid4()),'GET')])
def test_http_routes_reject_unauthenticated_requests(path,method):
    from api.server import app
    response=TestClient(app).request(method,path)
    assert response.status_code==401
    assert response.headers['cache-control']=='no-store'


def test_public_page_is_available_but_api_key_is_not_exposed():
    from api.server import app
    client=TestClient(app)
    assert client.get('/').status_code==200
    result=client.get('/account/config').json()
    assert set(result)=={'configured'}


def test_account_browser_boundary():
    subprocess.run(['node','tests/account_session.test.cjs'],check=True,capture_output=True,text=True)


def test_account_recovery_browser():
    subprocess.run(['node','tests/account_recovery.test.cjs'],check=True,capture_output=True,text=True)


def test_chat_tools_browser():
    subprocess.run(['node','tests/chat_tools.test.cjs'],check=True,capture_output=True,text=True)


@pytest.mark.parametrize('header', ['', 'Bearer forged-token'])
def test_password_change_requires_verified_session(header, monkeypatch):
    from api.server import app
    def reject_token(*args, **kwargs):
        raise HTTPException(400, 'Account request could not finish. Please try again.')
    monkeypatch.setattr('core.cognition.account_access.auth_request', reject_token)
    response = TestClient(app).post('/account/password', headers={'Authorization':header},
                                    json={'password':'synthetic-new-password'})
    assert response.status_code == 401
    assert response.headers['cache-control'] == 'no-store'


def test_recovery_owner_only_and_fixed_redirect(monkeypatch):
    from fastapi import FastAPI
    import api.account_documents as module
    calls=[]
    monkeypatch.setenv('L_OWNER_EMAIL','owner@example.com')
    monkeypatch.setattr(module,'auth_request',lambda *args,**kw: calls.append((args,kw)) or {})
    app=FastAPI(); app.include_router(module.routes(None,None)); client=TestClient(app)
    other=client.post('/account/recover',json={'email':'other@example.com'})
    assert other.status_code==200 and not calls
    owner=client.post('/account/recover',json={'email':' OWNER@example.com '},headers={'Host':'attacker.example'})
    assert owner.json()==other.json()
    from urllib.parse import parse_qs, urlsplit
    assert parse_qs(urlsplit(calls[0][0][0]).query)['redirect_to']==[module.ACCOUNT_REDIRECT]
    assert calls[0][0][1]=={'email':'owner@example.com'}


def test_password_update_uses_user_token_and_revokes_sessions(monkeypatch):
    from fastapi import FastAPI
    import api.account_documents as module
    calls=[]
    monkeypatch.setattr(module,'auth_request',lambda *args,**kw: calls.append((args,kw)) or {})
    # Router unit test; real application middleware is covered separately above.
    app=FastAPI(); app.include_router(module.routes(None,None)); client=TestClient(app)
    assert client.post('/account/password',json={'password':'short'},headers={'Authorization':'Bearer synthetic'}).status_code==422
    assert not calls
    response=client.post('/account/password',json={'password':'synthetic-new-password'},headers={'Authorization':'Bearer synthetic'})
    assert response.json()=={'password_updated':True,'signed_out':True}
    assert calls[0]==(('user',{'password':'synthetic-new-password'}),{'token':'synthetic','method':'PUT'})
    assert calls[1]==(('logout?scope=global',),{'token':'synthetic'})


@pytest.mark.parametrize('code,expected',[('invalid_credentials','Forgot password'),('email_not_confirmed','Confirm your email'),('secret-upstream-body','Account request')])
def test_auth_errors_use_allowlisted_messages(monkeypatch,code,expected):
    import httpx
    from core.cognition.account_access import auth_request
    monkeypatch.setenv('SUPABASE_URL','https://example.supabase.co')
    monkeypatch.setenv('SUPABASE_PUBLISHABLE_KEY','synthetic')
    monkeypatch.setattr(httpx.Client,'request',lambda *a,**kw:httpx.Response(400,json={'error_code':code,'message':'secret-upstream-body'}))
    with pytest.raises(HTTPException) as error: auth_request('token?grant_type=password',{})
    assert expected in error.value.detail
    assert 'secret-upstream-body' not in error.value.detail
