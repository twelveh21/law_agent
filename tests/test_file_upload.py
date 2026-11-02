import io
import unittest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from docx import Document
import fitz
from app.api.v1.files import router, parse_attachment
from app.models.schemas import ChatRequest

class UploadTests(unittest.TestCase):
    def test_formats(self):
        self.assertEqual(parse_attachment('条款.txt','合同条款'.encode())['text'],'合同条款')
        doc=Document();doc.add_paragraph('合同正文'); table=doc.add_table(rows=1,cols=1);table.cell(0,0).text='表格条款'
        buf=io.BytesIO();doc.save(buf)
        self.assertIn('表格条款',parse_attachment('合同.docx',buf.getvalue())['text'])
        with fitz.open() as pdf:
            pdf.new_page().insert_text((50,50),'Contract terms')
            self.assertIn('Contract terms',parse_attachment('合同.pdf',pdf.tobytes())['text'])
    def test_reject_bad_and_long(self):
        for name,data in [('a.exe',b'a'),('a.png',b'fake'),('a.txt',b'a'*30001)]:
            with self.assertRaises(ValueError):parse_attachment(name,data)
    def test_multiple_chat_attachments(self):
        request=ChatRequest(thread_id='test',attachments=[{'name':'1.txt','text':'a'},{'name':'2.txt','text':'b'}])
        self.assertEqual(len(request.attachments),2)
        with self.assertRaises(ValueError):ChatRequest(thread_id='test',attachments=[{'name':'x','text':'a'*30000}]*3)
    def test_upload_endpoint(self):
        app=FastAPI();app.include_router(router)
        with TestClient(app) as client:
            response=client.post('/files/parse?filename=a.txt',content=b'contract')
            self.assertEqual(response.status_code,200)
            self.assertEqual(response.json()['text'],'contract')
            self.assertEqual(client.post('/files/parse?filename=a.txt',content=b'').status_code,400)
            self.assertEqual(client.post('/files/parse?filename=a.exe',content=b'abc').status_code,422)
