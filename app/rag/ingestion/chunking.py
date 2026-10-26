from typing import Dict, List


def _split_paragraphs_with_headings(text:str)->List[Dict]:
    """根据标题层次分割段落，保持语义完整性。"""
    lines = text.splitlines()
    heading_stack:List[str]=[]
    paragraphs : List[Dict]=[]
    buf : List[str]=[]
    char_pos=0

    def flush_buf(end_pos:int):
        if not buf:
            return
        content = "\n".join(buf).strip()
        if not content:
            return
        paragraphs.append({
            "content":content,
            "heading_path":">".join(heading_stack) if heading_stack else None,
            "start":max(0,end_pos-len(content)),
            "end":end_pos,
        })
        buf.clear()

    for ln in lines:
        raw=ln
        if raw.strip().startswith("#"):
            flush_buf(char_pos)
            level=len(raw)-len(raw.lstrip('#'))
            title=raw.lstrip('#').strip()
            # 新标题会替换同级及更深层级的旧标题。
            heading_stack=heading_stack[:level-1]
            heading_stack.append(title)

            char_pos+=len(raw)+1
            continue

        #段落内容积累
        if raw.strip()=="":
            flush_buf(char_pos)
        else:
            buf.append(raw)
        char_pos+=len(raw)+1

    flush_buf(char_pos)
    if not paragraphs and text.strip():
        paragraphs=[{"content":text.strip(),"heading_path":None,"start":0,"end":len(text)}]
    return paragraphs


def _chunk_paragraphs(paragraphs:List[Dict],chunk_tokens:int,overlap_tokens:int)->List[Dict]:
    """基于token数量智能分块"""
    if chunk_tokens <= 0:
        raise ValueError("chunk_tokens 必须大于 0")
    if overlap_tokens < 0 or overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens 必须大于等于 0 且小于 chunk_tokens")

    chunks:List[Dict]=[]
    cur:List[Dict]=[]
    cur_tokens=0
    i=0

    while i < len(paragraphs):
        p=paragraphs[i]
        p_tokens=_approx_token_len(p["content"]) or 1

        if cur_tokens+p_tokens<=chunk_tokens or not cur:
            cur.append(p)
            cur_tokens+=p_tokens
            i+=1
        else:
            #生成当前分块
            content = "\n\n".join(x["content"] for x in cur)
            start=cur[0]["start"]
            end=cur[-1]["end"]
            heading_path=next((x["heading_path"] for x in reversed(cur) if x.get("heading_path")),None)
            chunks.append(
                {
                    "content":content,
                    "heading_path":heading_path,
                    "start":start,
                    "end":end,
                }
            )

            #构建重叠部分
            if overlap_tokens>0 and cur:
                kept:List[Dict]=[]
                kept_tokens=0
                for x in reversed(cur):
                    t=_approx_token_len(x["content"]) or 1
                    if kept_tokens+t > overlap_tokens:
                        break
                    kept.append(x)
                    kept_tokens+=t
                cur = list(reversed(kept))
                cur_tokens=kept_tokens
                # 若重叠段落加上当前待处理段落仍超限，丢弃重叠，
                # 否则 while 会重复处理同一段而无法前进。
                if cur_tokens + p_tokens > chunk_tokens:
                    cur=[]
                    cur_tokens=0
            else:
                cur=[]
                cur_tokens=0

    if cur:
        content="\n\n".join(x["content"] for x in cur)
        start=cur[0]["start"]
        end=cur[-1]["end"]
        heading_path=next((x["heading_path"] for x in reversed(cur) if x.get("heading_path")),None)
        chunks.append(
            {
                "content":content,
                "heading_path":heading_path,
                "start":start,
                "end":end,
            }
        )

    return chunks


def _approx_token_len(text:str)->int:
    """近似估计token长度"""
    cjk=sum(1 for ch in text if _is_cjk(ch))
    non_cjk_tokens=len([t for t in text.split() if t])
    return cjk+non_cjk_tokens


def _is_cjk(ch:str)->bool:
    """判断是否为cjk字符"""
    code=ord(ch)
    return(
            0x4E00 <= code <= 0x9FFF or  # CJK统一汉字
            0x3400 <= code <= 0x4DBF or  # CJK扩展A
            0x20000 <= code <= 0x2A6DF or  # CJK扩展B
            0x2A700 <= code <= 0x2B73F or  # CJK扩展C
            0x2B740 <= code <= 0x2B81F or  # CJK扩展D
            0x2B820 <= code <= 0x2CEAF or  # CJK扩展E
            0xF900 <= code <= 0xFAFF  # CJK兼容汉字
    )
