"""Six synthetic-only page/image trials. No database writes or private sources."""
import base64
import hashlib
from io import BytesIO
import json
import math
import os
import statistics
import time
from types import SimpleNamespace
from uuid import uuid4

from openai import OpenAI
from PIL import Image, ImageDraw
from core.cognition.document_evidence import answer_from_document
from core.cognition.model_independence import OpenAIChatCompletionsAdapter


def run():
    client = OpenAI(api_key=os.environ['OPENAI_API_KEY'],timeout=45,max_retries=0)
    adapter = OpenAIChatCompletionsAdapter(client,os.getenv('OPENAI_MODEL','gpt-4o-mini'))
    image=Image.new('RGB',(500,350),'white'); ImageDraw.Draw(image).rectangle((80,50,420,300),fill='red')
    buffer=BytesIO(); image.save(buffer,format='PNG'); data=buffer.getvalue()
    pdf={'id':str(uuid4()),'filename':'Synthetic Cedar.pdf','sha256':hashlib.sha256(b'synthetic cedar pages').hexdigest(),
         'mime_type':'application/pdf','pages':[
          {'page':1,'kind':'pdf_text','text':'Project Cedar has 7 blue boats.','truncated':False},
          {'page':2,'kind':'pdf_text','text':'Project Cedar has 12 red boats.','truncated':False}]}
    picture={'id':str(uuid4()),'filename':'Synthetic red rectangle.png','sha256':hashlib.sha256(data).hexdigest(),
             'mime_type':'image/png','original_base64':base64.b64encode(data).decode(),
             'pages':[{'page':1,'kind':'image','text':'','truncated':False}]}
    results=[]
    for repeat in range(3):
        for name,doc,page,question in [('physical_page',pdf,2,'How many boats are on this page, and what colour are they?'),
                                        ('image_colour',picture,1,'What colour is the large rectangle?')]:
            started=time.monotonic()
            result=answer_from_document(SimpleNamespace(get=lambda *args,**kwargs:doc),adapter,{
                'user_id':str(uuid4()),'document_id':doc['id'],'source_sha256':doc['sha256'],
                'page':page,'question':question})
            answer=result['reply'].lower()
            passed=('red' in answer and ('12' in answer or 'twelve' in answer) and bool(result['evidence']['quotes'])) if name=='physical_page' else 'red' in answer
            passed=passed and result['evidence']['page']==page and result['memory_written'] is False
            results.append({'case':name,'trial':repeat+1,'passed':passed,'duration_ms':round((time.monotonic()-started)*1000),
                            'receipt':result['model_receipt']})
    durations=sorted(r['duration_ms'] for r in results)
    costs=[r['receipt'].get('cost',{}).get('amount') for r in results]
    report={'synthetic_only':True,'calls':len(results),'passed':all(r['passed'] for r in results),
            'median_ms':statistics.median(durations),'p95_ms':durations[math.ceil(.95*len(durations))-1],
            'min_ms':min(durations),'max_ms':max(durations),
            'estimated_usd_per_completed_task':sum(costs)/len(costs) if all(isinstance(c,(int,float)) for c in costs) else None,
            'memory_written':False,'trials':results}
    print('L_STAGE7_PROVIDER_CHECK '+json.dumps(report),flush=True)
    if not report['passed']:raise RuntimeError('Synthetic evidence gate failed')


if __name__=='__main__':run()
