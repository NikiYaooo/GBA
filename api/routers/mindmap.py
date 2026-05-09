from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/api/mindmap", tags=["mindmap"])


@router.post("/parse")
async def parse_mindmap(file: UploadFile = File(...)):
    try:
        content = await file.read()
        filename = (file.filename or '').lower()
        if filename.endswith(('.png', '.jpg', '.jpeg')):
            try:
                from PIL import Image
                import io
                img = Image.open(io.BytesIO(content))
                text = ' '.join(str(img.size))
                return {"success": True, "content": f"图片尺寸: {text}（图片脑图内容建议手动转换为文本或使用OCR）"}
            except ImportError:
                return {"success": True, "content": "脑图图片已接收，建议转换为文本格式以获得更好的分析效果"}
        else:
            try:
                text = content.decode('utf-8')
            except Exception:
                text = content.decode('gbk', errors='replace')
            return {"success": True, "content": text[:5000]}
    except Exception as e:
        return {"success": False, "message": str(e)}
