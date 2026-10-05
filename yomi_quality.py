"""Conservative OCR comparison, confirmed-name hints and dialogue associations."""
from difflib import SequenceMatcher
import re
import numpy as np
from PIL import Image,ImageOps


def review_ocr(processor,image,blocks,original_process):
    if processor.source_lang_english != 'Japanese':return blocks
    candidates=sorted((b for b in blocks if b.xyxy is not None and len(b.text.strip())>=3),key=lambda b:len(b.text),reverse=True)[:6]
    from modules.utils.textblock import TextBlock
    for block in candidates:
        block.yomi_ocr_original=block.text
        block.yomi_ocr_alternatives=[];block.yomi_ocr_notes=[]
        x1,y1,x2,y2=map(int,block.xyxy)
        crop=image[max(0,y1-8):min(image.shape[0],y2+8),max(0,x1-8):min(image.shape[1],x2+8)]
        if not crop.size:continue
        try:
            enlarged=ImageOps.expand(Image.fromarray(crop).resize((crop.shape[1]*2,crop.shape[0]*2),Image.Resampling.LANCZOS),border=16,fill='white')
            variant=np.asarray(enlarged)
            retry=TextBlock(text_bbox=np.array([0,0,variant.shape[1],variant.shape[0]]),text_class='text_bubble')
            original_process(processor,variant,[retry])
            alternative=retry.text.strip()
            compact=lambda text:re.sub(r'[\s．。・…]+','',text)
            if alternative and compact(alternative)!=compact(block.text):
                block.yomi_ocr_alternatives=[alternative]
                block.yomi_ocr_notes=['二次识别与原文不一致，候选：'+alternative]
        except Exception:
            block.yomi_ocr_notes=['二次识别失败，请人工核对原文']
    return blocks


def related_groups(blocks):
    groups=[];used=set()
    for i,left in enumerate(blocks):
        if i in used or left.xyxy is None:continue
        for j in range(i+1,len(blocks)):
            right=blocks[j]
            if j in used or right.xyxy is None:continue
            a=np.asarray(left.xyxy,dtype=float);b=np.asarray(right.xyxy,dtype=float)
            ba=getattr(left,'bubble_xyxy',None);bb=getattr(right,'bubble_xyxy',None)
            same_bubble=ba is not None and bb is not None and np.allclose(ba,bb,atol=8)
            # A continuation in the same vertical column; keep adjacency strict.
            overlap=max(0,min(a[2],b[2])-max(a[0],b[0]))/max(1,min(a[2]-a[0],b[2]-b[0]))
            gap=max(0,max(a[1],b[1])-min(a[3],b[3]))
            column=overlap>.7 and gap<min(a[2]-a[0],b[2]-b[0])*.6
            continuation=not re.search(r'[！？!?。]$',left.text.strip()) and len(right.text.strip())<=8
            cross_block=(j==i+1 and re.search(r'[一-龯]$',left.text.strip()) is not None and re.match(r'^[ぁ-ゖ]',right.text.strip()) is not None and len(right.text.strip())<=6)
            if same_bubble or (column and continuation) or cross_block:
                ordered=[i,j] if cross_block else sorted((i,j),key=lambda n:(float(blocks[n].xyxy[1]) if column else -float(blocks[n].xyxy[0])))
                groups.append({'keys':[f'block_{n}' for n in ordered],'source':''.join(blocks[n].text for n in ordered),'reason':'same_bubble' if same_bubble else ('possible_sentence_across_blocks' if cross_block else 'possible_vertical_continuation')})
                used.update((i,j));break
    return groups


def quality_context(blocks,memory):
    hints={};confirmed=[t for t in memory['terms'] if t['status']=='confirmed' and 2<=len(t['source'])<=8]
    for i,block in enumerate(blocks):
        notes=list(getattr(block,'yomi_ocr_notes',[]));suggestions=[]
        for term in confirmed:
            source=term['source']
            if source in block.text:continue
            n=len(source)
            matches={block.text[k:k+n] for k in range(max(0,len(block.text)-n+1)) if sum(a!=b for a,b in zip(block.text[k:k+n],source))==1 and SequenceMatcher(None,block.text[k:k+n],source).ratio()>=.5}
            for match in sorted(matches):
                suggestions.append({'ocr':match,'confirmed_source':source,'target':term['target']})
                notes.append('疑似术语或人名误识别：'+match+' → '+source+'（需核对）')
        if notes or suggestions:
            hints[f'block_{i}']={'alternatives':getattr(block,'yomi_ocr_alternatives',[]),'name_candidates':suggestions,'notes':notes}
    # Similar honorific-bearing names on the same page are ambiguous even without a glossary.
    names=[]
    for i,block in enumerate(blocks):
        for match in re.finditer(r'([一-龯]{2,4})(?:さん|君|くん|ちゃん)',block.text):names.append((i,match.group(1)))
    for i,name in names:
        variants=sorted({other for j,other in names if j!=i and other!=name and len(other)==len(name) and sum(a!=b for a,b in zip(name,other))==1})
        if variants:
            entry=hints.setdefault(f'block_{i}',{'alternatives':[],'name_candidates':[],'notes':[]})
            entry['notes'].append('同页出现相似人名：'+name+' / '+', '.join(variants)+'，请确认是否为同一人物')
    groups=related_groups(blocks)
    for group in groups:
        if group['reason']!='same_bubble':
            for key in group['keys']:
                entry=hints.setdefault(key,{'alternatives':[],'name_candidates':[],'notes':[]})
                entry['notes'].append('可能与其他文字框组成连续对白，请核对关联与断句：'+', '.join(group['keys']))
    return {'ocr_checks':hints,'related_dialogue':groups}
