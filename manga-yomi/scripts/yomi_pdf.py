"""Render manga PDFs and build bilingual review PDFs; no external translation API."""
import argparse
import json
from pathlib import Path
from xml.sax.saxutils import escape
import pypdfium2 as pdfium

def prepare(source, out, start=1, end=None, dpi=160):
    if out.exists():
        raise ValueError("Output directory exists; choose a fresh directory")
    if not 72 <= dpi <= 300:
        raise ValueError("DPI must be 72..300")
    doc=pdfium.PdfDocument(str(source))
    try:
        total=len(doc);end=total if end is None else end
        if not 1 <= start <= end <= total:
            raise ValueError("Invalid page range")
        out.mkdir(parents=True)
        pages=[]
        for i in range(start-1,end):
            page=doc[i]
            try:
                width,height=page.get_size()
                if width*height*(dpi/72)**2 > 40000000:
                    raise ValueError("Page too large; choose a lower DPI")
                bitmap=page.render(scale=dpi/72)
                try:
                    bitmap.to_pil().save(out/f"p{i+1:03}.png")
                finally:
                    bitmap.close()
                textpage=page.get_textpage()
                try:
                    hint=textpage.get_text_range()
                finally:
                    textpage.close()
                pages.append({"page_id":f"p{i+1:03}","page_number":i+1,"image":f"p{i+1:03}.png","text_hint":hint,"blocks":[]})
            finally:
                page.close()
        manifest={"source_pdf":str(source.resolve()),"total_pages":total,"selected_range":[start,end],"dpi":dpi,"pages":pages}
        (out/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        return manifest
    finally:
        doc.close()

def compose(manifest_path,review_path,out,allow_draft=False):
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import ParagraphStyle
    manifest=json.loads(manifest_path.read_text(encoding='utf-8-sig'))
    review=json.loads(review_path.read_text(encoding='utf-8-sig'))
    expected=[p['page_id'] for p in manifest['pages']]
    pages=review.get('pages',[])
    if [p.get('page_id') for p in pages] != expected:
        raise ValueError("Review pages must exactly match manifest order and IDs")
    pending=0
    for page in pages:
        blocks=page.get('blocks')
        if not isinstance(blocks,list) or not blocks:
            raise ValueError("Each page needs reviewed blocks, or one explicitly marked no-text block")
        seen=set()
        for b in blocks:
            if not isinstance(b.get('id'),str) or b['id'] in seen:
                raise ValueError("Duplicate or invalid block ID")
            seen.add(b['id'])
            if not all(isinstance(b.get(k),str) for k in ('source','translation')) or not b['translation'].strip():
                raise ValueError("Each block needs source and a nonempty translation")
            if b.get('status') not in ('verified','proposed','needs_review'):
                raise ValueError("Invalid status")
            pending+=b['status']!='verified'
    if pending and not allow_draft:
        raise ValueError("Unconfirmed translations; use --allow-draft or finish review")
    if out.exists() or out.resolve() in (manifest_path.resolve(),review_path.resolve()):
        raise ValueError("Output exists or would overwrite input")
    # Validate all input images before writing output.
    images=[]
    for p in manifest['pages']:
        image=(manifest_path.parent/p['image']).resolve()
        if not image.is_relative_to(manifest_path.parent.resolve()) or not image.is_file():
            raise ValueError("Missing image or image outside manifest folder")
        images.append(image)
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
    pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
    style=ParagraphStyle('zh',fontName='STSong-Light',fontSize=11,leading=17,wordWrap='CJK')
    jp=ParagraphStyle('jp',parent=style,fontName='HeiseiMin-W3')
    out.parent.mkdir(parents=True,exist_ok=True)
    c=canvas.Canvas(str(out),pagesize=(595,842))
    c.setTitle('Manga Yomi - Bilingual Review')
    for original,page,image in zip(manifest['pages'],pages,images):
        c.setFont('STSong-Light',12)
        c.drawString(35,811,f"Manga Yomi | {page['page_id']} | 原始页面")
        c.drawImage(str(image),35,40,width=525,height=750,preserveAspectRatio=True,anchor='c')
        c.showPage()
        y=800
        def paragraph(text, st=style):
            nonlocal y
            para=Paragraph(escape(text).replace('\n','<br/>'),st)
            _,height=para.wrap(525,730)
            if height>730:
                raise ValueError('Block too long for one page; split the block')
            if y-height<40:
                c.showPage();y=800
            para.drawOn(c,35,y-height);y-=height+8
        paragraph(f"Manga Yomi | {page['page_id']} | {'待确认草稿' if pending else '已确认对照稿'}")
        for b in page['blocks']:
            paragraph(f"{b['id']} [{b['status']}]")
            paragraph(b['source'],jp)
            paragraph(b['translation'])
            if b.get('notes'):
                paragraph('备注：'+'；'.join(b['notes']))
        c.showPage()
    c.save()
    return pending

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('prepare');p.add_argument('pdf',type=Path);p.add_argument('--out',type=Path,required=True);p.add_argument('--start',type=int,default=1);p.add_argument('--end',type=int);p.add_argument('--dpi',type=int,default=160)
    p=sub.add_parser('compose');p.add_argument('--manifest',type=Path,required=True);p.add_argument('--review',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--allow-draft',action='store_true')
    a=parser.parse_args()
    try:
        if a.command=='prepare':
            m=prepare(a.pdf,a.out,a.start,a.end,a.dpi);print(f"Rendered {len(m['pages'])} pages. Visually inspect images; text_hint is not OCR.")
        else:
            n=compose(a.manifest,a.review,a.out,a.allow_draft);print(f"PDF created; {n} unconfirmed blocks. Semantic accuracy not checked by this script.")
    except Exception as exc:
        parser.exit(2,f"PDF processing failed: {exc}\n")

if __name__=='__main__':main()
