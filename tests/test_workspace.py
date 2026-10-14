import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi.testclient import TestClient

# Import after choosing a temporary data directory; never touch a user's workspace.
_TEST_DATA=tempfile.TemporaryDirectory()
os.environ['DATA_DIR']=_TEST_DATA.name
from app import main
from app.store import Store
from app.ingest import extract


class FakeRetrieval:
    def __init__(self):self.rows={};self.last_query='';self.owner=None;self.folder=None
    def add(self,owner,document,folder,passages,progress):
        progress('embedding',70)
        for p in passages:self.rows[p['id']]={**p,'owner':owner,'document':document,'folder':folder}
    def delete(self,owner,document):
        self.rows={k:v for k,v in self.rows.items() if not(v['owner']==owner and v['document']==document)}
    def search(self,owner,folder,query,limit=5):
        self.last_query=query;self.owner=owner;self.folder=folder
        return [(k,5 if 'unrelated' not in query else -5) for k,v in self.rows.items() if v['owner']==owner and (not folder or v['folder']==folder)][:limit]

class Immediate:
    def submit(self,fn,*args):fn(*args)

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.fake=FakeRetrieval()
        for name,value in [('store',Store(self.tmp.name)),('DATA',Path(self.tmp.name)),('retrieval',self.fake),('workers',Immediate())]:
            p=patch.object(main,name,value);p.start();self.addCleanup(p.stop)
        self.env=patch.dict(os.environ,{'GEMINI_API_KEY':'','MIN_RERANK_SCORE':'0','ALLOW_REGISTRATION':'true'},clear=False)
        self.env.start();self.addCleanup(self.env.stop)
        self.a=TestClient(main.app);self.b=TestClient(main.app)
        self.headers={'X-Requested-With':'SourceDesk'}
        for c,name in [(self.a,'alice'),(self.b,'bob')]:
            response=c.post('/api/register',json={'username':name,'password':'longpassword123'},headers=self.headers)
            self.assertEqual(response.status_code,200,response.text)
        self.folder=self.a.get('/api/collections').json()[0]['id']

    def upload(self,client=None,folder=None,filename='policy.txt',content=b'Employees may work remotely two days per week with manager approval.'):
        response=(client or self.a).post('/api/documents',data={'folder':folder or self.folder,'ocr':'false'},files={'file':(filename,content)},headers=self.headers)
        self.assertEqual(response.status_code,202,response.text)
        job=self.a.get('/api/jobs/'+response.json()['job_id']).json()
        self.assertEqual(job['stage'],'done',job)
        return response.json()

    def chat(self):
        return self.a.post('/api/chats',json={'folder':self.folder},headers=self.headers).json()['id']

    def ask(self,chat,question='How many remote days?'):
        return self.a.post('/api/ask',json={'chat_id':chat,'question':question},headers=self.headers)

    def test_auth_and_csrf(self):
        self.assertEqual(TestClient(main.app).get('/api/documents').status_code,401)
        self.assertEqual(self.a.post('/api/collections',json={'name':'Bad'}).status_code,403)
        self.assertEqual(self.a.post('/api/collections',json={'name':'Bad'},headers={**self.headers,'Origin':'https://evil.example'}).status_code,403)
        cookie=self.a.cookies.get('sourcedesk_session')
        stored=main.store.all('SELECT token FROM sessions')
        self.assertNotIn(cookie,str(stored))

    def test_resource_isolation(self):
        doc=self.upload();chat=self.chat();answer=self.ask(chat).json();chunk=answer['result']['sources'][0]['id']
        for path in ['/api/jobs/'+doc['job_id'],'/api/chats/'+chat,'/api/chats/'+chat+'/export/docx','/api/sources/'+chunk,'/api/sources/'+chunk+'/preview']:
            self.assertEqual(self.b.get(path).status_code,404,path)
        self.assertEqual(self.b.delete('/api/documents/'+doc['id'],headers=self.headers).status_code,404)
        self.assertEqual(self.b.post('/api/turns/'+answer['id']+'/feedback',json={'rating':1},headers=self.headers).status_code,404)
        self.assertEqual(self.b.get('/api/documents').json(),[])
        self.assertEqual(self.b.get('/api/usage').json()['summary']['requests'],0)
        self.assertEqual(self.b.post('/api/chats',json={'folder':self.folder},headers=self.headers).status_code,404)

    def test_saved_followup_and_feedback(self):
        self.upload();chat=self.chat();first=self.ask(chat).json();second=self.ask(chat,'Explain that further.').json()
        self.assertIn('How many remote days?',self.fake.last_query)
        self.assertEqual(len(self.a.get('/api/chats/'+chat).json()['turns']),2)
        self.assertEqual(self.a.post('/api/turns/'+first['id']+'/feedback',json={'rating':-1,'note':'Needs more detail'},headers=self.headers).status_code,200)
        self.assertEqual(self.a.get('/api/usage').json()['feedback'][0]['rating'],-1)

    def test_low_evidence_skips_generation(self):
        self.upload();chat=self.chat()
        with patch.object(main,'generate_auto') as generate:
            answer=self.ask(chat,'Something unrelated').json()['result']
            self.assertEqual(answer['mode'],'unsupported');generate.assert_not_called()

    def test_collection_scope_and_duplicate(self):
        self.upload()
        other=self.a.post('/api/collections',json={'name':'Other'},headers=self.headers).json()['id']
        self.assertEqual(self.a.get('/api/documents?folder='+other).json(),[])
        chat=self.a.post('/api/chats',json={'folder':other},headers=self.headers).json()['id']
        self.assertEqual(self.ask(chat).json()['result']['sources'],[])
        response=self.a.post('/api/documents',data={'folder':self.folder},files={'file':('copy.txt',b'Employees may work remotely two days per week with manager approval.')},headers=self.headers)
        self.assertEqual(response.status_code,409)

    def test_generation_usage_and_citation(self):
        self.upload();chat=self.chat()
        def generated(system,question,sources,**kwargs):
            return {'claims':[{'statement':'Two days are permitted.','source_id':sources[0]['id'],'quote':'work remotely two days per week'}]}, {'model':'test-model','usage':{'total_tokens':42},'attempted_models':['failed','test-model'],'fallback_used':True}
        with patch.dict(os.environ,{'GEMINI_API_KEY':'fake'}),patch.object(main,'generate_auto',side_effect=generated):
            result=self.ask(chat).json()['result']
        self.assertEqual(result['mode'],'answer');self.assertEqual(len(result['claims']),1)
        usage=self.a.get('/api/usage').json()['summary']
        self.assertEqual(usage['reported_tokens'],42);self.assertEqual(usage['fallback_attempts'],1)

    def test_pdf_preview_and_exports(self):
        import pymupdf as fitz
        pdf=fitz.open();page=pdf.new_page();page.insert_text((50,70),'Employees may work remotely two days per week with manager approval.')
        self.upload(filename='policy.pdf',content=pdf.tobytes());chat=self.chat();turn=self.ask(chat).json()
        chunk=turn['result']['sources'][0]['id']
        response=self.a.get('/api/sources/'+chunk+'/preview')
        self.assertEqual(response.status_code,200);self.assertTrue(response.content.startswith(b'\x89PNG'))
        for format,signature in [('pdf',b'%PDF'),('docx',b'PK')]:
            response=self.a.get('/api/chats/'+chat+'/export/'+format)
            self.assertEqual(response.status_code,200,response.text[:100] if response.status_code!=200 else '')
            self.assertTrue(response.content.startswith(signature))

    def test_logout_revokes_session(self):
        self.a.post('/api/logout',headers=self.headers)
        self.assertEqual(self.a.get('/api/me').status_code,401)

    def test_remove_document_blocks_preview(self):
        doc=self.upload();chat=self.chat();chunk=self.ask(chat).json()['result']['sources'][0]['id']
        self.assertEqual(self.a.delete('/api/documents/'+doc['id'],headers=self.headers).status_code,200)
        self.assertEqual(self.a.get('/api/sources/'+chunk).status_code,404)
        self.assertEqual(self.ask(chat).json()['result']['sources'],[])
