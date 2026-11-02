"""Bounded transient attachment parsing; files are not saved to a public bucket."""
import asyncio
import base64
import io
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from app.common.rate_limit import enforce_rate_limit

router = APIRouter()
MAX_BYTES = 10 * 1024 * 1024


def parse_attachment(name: str, data: bytes) -> dict:
    ext = Path(name).suffix.lower()
    if ext in {".png", ".jpg", ".jpeg", ".webp"}:
        valid = ((ext == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n")) or
                 (ext in {".jpg", ".jpeg"} and data.startswith(b"\xff\xd8\xff")) or
                 (ext == ".webp" and data[:4] == b"RIFF" and data[8:12] == b"WEBP"))
        if not valid:
            raise ValueError("图片格式与扩展名不一致")
        mime = {".png": "png", ".jpg": "jpeg", ".jpeg": "jpeg", ".webp": "webp"}[ext]
        return {"name": name, "image": f"data:image/{mime};base64," + base64.b64encode(data).decode()}
    if ext == ".pdf":
        import fitz
        with fitz.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                raise ValueError("请先解除 PDF 密码保护")
            if len(doc) > 100:
                raise ValueError("单份 PDF 最多支持 100 页，请拆分文件")
            pieces = []
            size = 0
            for page in doc:
                text = page.get_text()
                size += len(text)
                if size > 30000:
                    raise ValueError("文件文字超过 30000 字符，请拆分后上传")
                pieces.append(text)
            text = "\n".join(pieces)
    elif ext == ".docx":
        from docx import Document
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if sum(item.file_size for item in archive.infolist()) > 30 * 1024 * 1024:
                raise ValueError("Word 解压后过大，请精简文件")
        doc = Document(io.BytesIO(data))
        text = "\n".join([p.text for p in doc.paragraphs] +
                         [" | ".join(c.text for c in row.cells) for table in doc.tables for row in table.rows])
    elif ext in {".txt", ".md", ".csv"}:
        try:
            text = data.decode("utf-8-sig")
        except UnicodeDecodeError:
            text = data.decode("gb18030")
    else:
        raise ValueError("支持 PDF、DOCX、TXT、Markdown、CSV、PNG、JPG、WebP")
    if not text.strip():
        raise ValueError("未提取到文字，扫描版 PDF 请改用图片上传")
    if len(text) > 30000:
        raise ValueError("文件文字超过 30000 字符，请拆分后上传")
    return {"name": name, "text": text.strip()}


@router.post("/files/parse")
async def upload_file(request: Request, filename: str):
    enforce_rate_limit(request, "file-upload", "UPLOAD_RATE_LIMIT_PER_MINUTE")
    name = filename.replace("\\", "/").rsplit("/", 1)[-1]
    if not name or len(name) > 200:
        raise HTTPException(400, "文件名无效或过长")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BYTES:
            raise HTTPException(413, "单个文件不能超过 10 MB")
        data.extend(chunk)
    if not data:
        raise HTTPException(400, "不能上传空文件")
    try:
        return await asyncio.to_thread(parse_attachment, name, bytes(data))
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:
        raise HTTPException(422, "文件损坏或格式无法解析，请重新导出后上传") from exc
