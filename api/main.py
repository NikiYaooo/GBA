import os
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from utils import get_app_data_dir, ensure_dir, load_json, save_json
from default_prompts import DEFAULT_PROMPTS
from knowledge_base import KnowledgeBase
from ai_service import AIService

import routers.documents as documents_router
import routers.ai as ai_router
import routers.knowledge_base as kb_router
import routers.config as config_router
import routers.excel as excel_router
import routers.prompts as prompts_router
import routers.mindmap as mindmap_router
import routers.template as template_router
import routers.reminders as reminders_router
import routers.image_gen as image_gen_router
import routers.image_library as image_library_router

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = get_app_data_dir()
ensure_dir(DATA_DIR)

DOCS_DB = os.path.join(DATA_DIR, "documents.json")
CONFIG_DB = os.path.join(DATA_DIR, "config.json")
PROMPTS_DB = os.path.join(DATA_DIR, "prompts.json")
LOG_DIR = os.path.join(DATA_DIR, "logs")
ensure_dir(LOG_DIR)

# 初始化日志文件
try:
    with open(os.path.join(LOG_DIR, "api.log"), 'a', encoding='utf-8') as _f:
        _f.write('')
except Exception:
    pass

# 仅在 prompts.json 不存在时才写入默认配置（修复每次启动覆盖用户自定义 Prompt 的 bug）
if not os.path.exists(PROMPTS_DB):
    try:
        save_json(PROMPTS_DB, DEFAULT_PROMPTS)
    except Exception:
        pass

# 初始化知识库（多项目管理）
kb = KnowledgeBase(data_dir=DATA_DIR)

# 初始化 AI 服务
ai_service = AIService(kb=kb, data_dir=DATA_DIR)

# 创建 FastAPI 应用
app = FastAPI(title="游戏策划AI文档助手 API")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 将共享服务挂载到路由器
kb_router.router.kb = kb
ai_router.router.ai_service = ai_service
image_gen_router.router.ai_service = ai_service

# 注册路由
app.include_router(documents_router.router)
app.include_router(ai_router.router)
app.include_router(kb_router.router)
app.include_router(config_router.router)
app.include_router(excel_router.router)
app.include_router(prompts_router.router)
app.include_router(mindmap_router.router)
app.include_router(template_router.router)
app.include_router(reminders_router.router)
app.include_router(image_gen_router.router)
app.include_router(image_library_router.router)


@app.get("/")
async def root():
    return {"message": "游戏策划AI文档助手 API 已启动"}


if __name__ == "__main__":
    port = int(os.environ.get('GB_PORT', '8000'))
    uvicorn.run(app, host="127.0.0.1", port=port)
