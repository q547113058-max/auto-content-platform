"""会话管理 API"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.schemas.schemas import (
    SessionStatusResponse, SessionCheckRequest, APIResponse,
)
from backend.services.session_manager import session_manager

router = APIRouter()


@router.get("/status", response_model=APIResponse)
async def get_all_sessions_status():
    """获取所有平台的会话状态"""
    report = await session_manager.check_all_sessions()
    return APIResponse(success=True, message="会话状态报告", data=report)


@router.post("/check", response_model=APIResponse)
async def check_sessions(request: SessionCheckRequest):
    """检查指定平台的会话状态"""
    platforms = request.platforms or [
        "xiaohongshu", "zhihu", "weibo", "wechat", "toutiao", "douyin"
    ]
    report = await session_manager.check_all_sessions()
    filtered = {p: report[p] for p in platforms if p in report}
    return APIResponse(success=True, message="会话检查完成", data=filtered)


@router.get("/{platform}/login")
async def trigger_login(platform: str):
    """
    L3: 触发平台登录流程
    启动浏览器打开登录页面，返回 VNC 连接信息
    """
    config = {
        "xiaohongshu": "https://creator.xiaohongshu.com/login",
        "zhihu": "https://www.zhihu.com/signin",
        "weibo": "https://weibo.com/login.php",
        "toutiao": "https://mp.toutiao.com/",
        "douyin": "https://creator.douyin.com/",
    }

    if platform not in config:
        valid = list(config.keys()) + ["wechat"]
        raise HTTPException(
            status_code=400,
            detail=f"平台 {platform} 暂不支持浏览器登录。支持: {valid}",
        )

    # 微信使用 API 方式
    if platform == "wechat":
        return APIResponse(
            success=True,
            message="微信公众号使用 API Token 方式，请通过账号管理配置 AppID/AppSecret",
            data={"login_type": "api"},
        )

    context = await session_manager.get_login_page(platform)

    return APIResponse(
        success=True,
        message=f"{platform} 登录页面已打开，请在 VNC 中完成登录",
        data={
            "platform": platform,
            "login_url": config[platform],
            "note": "登录成功后系统会自动保存 StorageState",
        },
    )
