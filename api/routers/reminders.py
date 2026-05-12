import uuid
import time
from datetime import datetime
from fastapi import APIRouter, HTTPException, Body
from utils import get_app_data_dir, load_json, save_json

router = APIRouter(prefix="/api/reminders", tags=["reminders"])


def _db():
    return get_app_data_dir() + "/reminders.json"


@router.get("")
async def list_reminders():
    data = load_json(_db(), {"reminders": []})
    # 按时间排序
    reminders = sorted(data["reminders"], key=lambda r: (r.get("month", 0) or 0, r.get("day", 0) or 0, r.get("hour", 0), r.get("minute", 0)))
    return {"success": True, "data": reminders}


@router.post("")
async def create_reminder(payload: dict = Body(...)):
    content = payload.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=400, detail="提醒内容不能为空")

    reminder = {
        "id": uuid.uuid4().hex[:12],
        "content": content,
        "month": payload.get("month"),  # None = 每月
        "day": payload.get("day"),      # None = 每日
        "hour": int(payload.get("hour", 9)),
        "minute": int(payload.get("minute", 0)),
        "enabled": True,
        "created_at": int(time.time()),
    }
    data = load_json(_db(), {"reminders": []})
    data["reminders"].append(reminder)
    save_json(_db(), data)
    return {"success": True, "data": reminder}


@router.put("/{reminder_id}")
async def update_reminder(reminder_id: str, payload: dict = Body(...)):
    data = load_json(_db(), {"reminders": []})
    for r in data["reminders"]:
        if r["id"] == reminder_id:
            if "content" in payload:
                r["content"] = payload["content"]
            if "month" in payload:
                r["month"] = payload["month"]
            if "day" in payload:
                r["day"] = payload["day"]
            if "hour" in payload:
                r["hour"] = int(payload["hour"])
            if "minute" in payload:
                r["minute"] = int(payload["minute"])
            if "enabled" in payload:
                r["enabled"] = payload["enabled"]
            save_json(_db(), data)
            return {"success": True, "data": r}
    raise HTTPException(status_code=404, detail="提醒不存在")


@router.delete("/{reminder_id}")
async def delete_reminder(reminder_id: str):
    data = load_json(_db(), {"reminders": []})
    data["reminders"] = [r for r in data["reminders"] if r["id"] != reminder_id]
    save_json(_db(), data)
    return {"success": True}


@router.get("/due")
async def check_due_reminders():
    """检查当前到期的提醒。前端每分钟轮询。"""
    now = datetime.now()
    current_month = now.month
    current_day = now.day
    current_hour = now.hour
    current_minute = now.minute

    data = load_json(_db(), {"reminders": []})
    due = []
    for r in data["reminders"]:
        if not r.get("enabled", True):
            continue
        # 匹配月（如果设置了）
        if r.get("month") is not None and r["month"] != current_month:
            continue
        # 匹配日（如果设置了）
        if r.get("day") is not None and r["day"] != current_day:
            continue
        # 匹配小时和分钟（精确匹配当前分钟）
        if r["hour"] == current_hour and r["minute"] == current_minute:
            due.append(r)

    return {"success": True, "data": due}
