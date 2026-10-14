import io
import os
from pathlib import Path
from xml.sax.saxutils import escape


def sections(chat):
    yield 'title','SourceDesk conversation'
    yield 'text',chat['title']
    for index,turn in enumerate(chat['turns'],1):
        yield 'heading',f'Question {index}'
        yield 'text',turn['question']
        result=turn['result']
        yield 'text',result['message']
        for claim in result['claims']:
            source=next((s for s in result['sources'] if s['id']==claim['source_id']),None)
            yield 'text',claim['statement']
            yield 'quote',claim['quote']
            if source: yield 'source',f"Source: {source['name']} | Page or section {source['page']} | Passage {source['id']}"
        if not result['claims']:
            for source in result['sources']:
                yield 'source',f"Retrieved evidence: {source['name']} | Page or section {source['page']}"
                yield 'quote',source['text']
    yield 'source','Citation checks validate source references and quotations, not semantic correctness.'


def export_conversation(chat,format):
    output=io.BytesIO()
    if format=='docx':
        from docx import Document
        from docx.shared import Inches, Pt, RGBColor
        doc=Document()
        # Some installed default templates add a border to Title. Remove it.
        for doc_style in doc.styles:
            for border in doc_style.element.xpath('.//w:pBdr'):
                border.getparent().remove(border)
        doc.styles['Heading 1'].font.color.rgb=RGBColor(0,0,0)
        section=doc.sections[0];section.top_margin=section.bottom_margin=Inches(.8)
        style=doc.styles['Normal'];style.font.name='Calibri';style.font.size=Pt(11)
        style.paragraph_format.space_after=Pt(8)
        for kind,text in sections(chat):
            if kind=='title':
                p=doc.add_paragraph(text,'Title')
                for run in p.runs: run.font.color.rgb=RGBColor(0,0,0)
            elif kind=='heading':doc.add_heading(text,level=1)
            else:
                p=doc.add_paragraph(text)
                if kind=='quote':p.paragraph_format.left_indent=Inches(.2)
                if kind=='source':
                    for run in p.runs:run.font.size=Pt(9)
        doc.save(output)
        return output.getvalue(),'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.pagesizes import A4
    font='Helvetica'
    candidates=[os.getenv('EXPORT_FONT',''),'/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','C:/Windows/Fonts/arial.ttf']
    for path in candidates:
        if path and Path(path).is_file():
            if 'WorkspaceFont' not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont('WorkspaceFont',path))
            font='WorkspaceFont';break
    base=getSampleStyleSheet()
    styles={
        'title':ParagraphStyle('DocTitle',fontName=font,fontSize=22,leading=27,spaceAfter=18),
        'heading':ParagraphStyle('DocHeading',fontName=font,fontSize=14,leading=18,spaceBefore=16,spaceAfter=8,keepWithNext=True),
        'text':ParagraphStyle('Body',fontName=font,fontSize=10,leading=15,spaceAfter=8,splitLongWords=True),
        'quote':ParagraphStyle('Quote',fontName=font,fontSize=10,leading=15,leftIndent=12,spaceAfter=9,splitLongWords=True),
        'source':ParagraphStyle('Source',fontName=font,fontSize=8,leading=12,spaceAfter=12,splitLongWords=True)}
    flow=[Paragraph(escape(text).replace('\n','<br/>'),styles[kind]) for kind,text in sections(chat)]
    SimpleDocTemplate(output,pagesize=A4,leftMargin=48,rightMargin=48,topMargin=48,bottomMargin=48).build(flow)
    return output.getvalue(),'application/pdf'
