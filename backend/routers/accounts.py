"""平台账号管理 API"""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from backend.models.database import get_db
from backend.models.models import PlatformAccount
from backend.schemas.schemas import (
    PlatformAccountCreate, PlatformAccountUpdate, PlatformAccountResponse, APIResponse,
)
from sqlalchemy import select
from pydantic import BaseModel
from loguru import logger

router = APIRouter()


class CookieImportRequest(BaseModel):
    cookie_string: str
    platform: Optional[str] = None  # 可选，默认用账号自身 platform


@router.post("/{account_id}/import-cookie", response_model=APIResponse)
async def import_cookie(
    account_id: int,
    body: CookieImportRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    粘贴浏览器 Cookie 字符串，自动解析为 StorageState JSON 并保存。
    保存路径：{STORAGE_STATES_DIR}/{platform}/{account_id}.json
    导入后自动用浏览器验证会话是否有效。
    """
    from loguru import logger
    from backend.config import settings
    from backend.services.cookie_parser import parse_cookie_string
    from pathlib import Path
    import json

    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    platform = body.platform or account.platform
    try:
        storage_state = parse_cookie_string(body.cookie_string, platform)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 保存到 storage_states 目录
    state_dir = Path(settings.STORAGE_STATES_DIR) / platform
    state_dir.mkdir(parents=True, exist_ok=True)
    state_path = state_dir / f"{account_id}.json"
    state_path.write_text(
        json.dumps(storage_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    cookie_count = len(storage_state.get("cookies", []))

    # 检查关键 Cookie 是否缺失（给用户更明确的诊断信息）
    from backend.services.cookie_parser import check_critical_cookies
    missing_critical = check_critical_cookies(storage_state["cookies"], platform)
    critical_hint = ""
    if missing_critical:
        names = "、".join(missing_critical)
        critical_hint = f"（注意：缺少关键 Cookie：{names}，导入后很可能无法通过验证）"

    # 导入后用浏览器真实验证会话
    verified = False
    verify_msg = ""
    try:
        from backend.services.session_manager import session_manager
        ctx = await session_manager.get_context(
            platform=platform,
            account_id=str(account_id),
            force_refresh=True,  # 强制绕过缓存，用新导入的 cookie 验证
        )
        if ctx:
            verified = True
            verify_msg = "，浏览器验证通过"
        else:
            verify_msg = "，但浏览器验证未通过（Cookie 可能不完整或已失效）"
    except Exception as e:
        logger.error(f"Cookie 导入后验证异常 [{platform}:{account_id}]: {e}")
        verify_msg = f"，浏览器验证异常（保留原状态）：{str(e)[:100]}"
        # 验证异常时不改 status，保留导入前状态（或保持 expired 不变）

    # 根据验证结果更新状态（仅当验证过程无异常时）
    if verified:
        account.status = "active"
    elif "验证异常" not in verify_msg:
        # 验证明确未通过（非异常），才标记为 expired
        account.status = "expired"
    # 验证异常时保留 account.status 原值，不做改动
    account.last_check_at = __import__("datetime").datetime.now()
    await db.commit()

    return APIResponse(
        success=verified,
        message=f"Cookie 已导入（{cookie_count} 条）{critical_hint}{verify_msg}",
        data={
            "cookie_count": cookie_count,
            "state_path": str(state_path),
            "verified": verified,
            "status": account.status,
            "missing_critical_cookies": missing_critical,
        },
    )


@router.post("/{account_id}/browser-login", response_model=APIResponse)
async def browser_login(account_id: int, db: AsyncSession = Depends(get_db)):
    """
    一键登录：启动可见浏览器，用户手动登录后自动抓取 Cookie 并保存。
    支持所有非 API 平台（微博、知乎、小红书、头条、抖音）。
    超时时间：5 分钟。
    """
    import asyncio

    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    platform = account.platform

    # 微信 API 类型不支持浏览器登录
    if platform == "wechat":
        raise HTTPException(status_code=400, detail="微信使用 API Token 方式，不支持浏览器登录")

    from backend.services.session_manager import session_manager
    from backend.services.session_manager import PLATFORM_CONFIGS

    if platform not in PLATFORM_CONFIGS:
        raise HTTPException(status_code=400, detail=f"平台 {platform} 暂不支持浏览器登录")

    config = PLATFORM_CONFIGS[platform]
    login_url = config.get("login_url", "")
    if not login_url:
        raise HTTPException(status_code=400, detail=f"平台 {platform} 未配置登录 URL")

    # 启动可见浏览器
    try:
        pw, browser, context, page = await session_manager.create_login_browser(platform)
    except Exception as e:
        logger.error(f"[{platform}:{account_id}] 启动浏览器失败: {e}")
        raise HTTPException(status_code=500, detail=f"启动浏览器失败: {str(e)}")

    # 轮询检测登录状态，最多等 5 分钟
    logged_in = False
    deadline = asyncio.get_event_loop().time() + 300  # 5 分钟
    poll_interval = 3  # 每 3 秒检查一次
    last_poll_url = ""

    try:
        while asyncio.get_event_loop().time() < deadline:
            await asyncio.sleep(poll_interval)

            # 获取当前 URL，检查是否已跳转离开登录页
            try:
                current_url = page.url
            except Exception:
                break  # 页面可能已被用户关闭

            # 快速预检：URL 中不含 login/signin/register 关键字则可能已登录
            exclude_urls = config.get("check_exclude_url", ["login", "signin", "register"])
            any_excluded = any(kw in current_url.lower() for kw in exclude_urls)

            if any_excluded:
                # 还在登录相关页面，继续等待
                last_poll_url = current_url
                continue

            # URL 看起来已离开登录页，用完整验证确认
            try:
                logged_in = await session_manager._verify_logged_in(context, platform)
            except Exception:
                logged_in = False

            if logged_in:
                break

            last_poll_url = current_url

        if logged_in:
            # 保存 StorageState
            await session_manager.save_session(context, platform, str(account_id))
            account.status = "active"
            account.last_check_at = __import__("datetime").datetime.now()
            await db.commit()

            # 加入缓存
            context_key = f"{platform}:{account_id}"
            session_manager._contexts[context_key] = context

            # 只关闭 browser 和 playwright，保留 context
            try:
                await browser.close()
            except Exception:
                pass
            try:
                await pw.stop()
            except Exception:
                pass

            return APIResponse(
                success=True,
                message=f"{platform} 登录成功，Cookie 已自动保存",
                data={"platform": platform, "status": "active"},
            )
        else:
            # 超时
            try:
                await context.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass
            try:
                await pw.stop()
            except Exception:
                pass

            last_info = f"，最后页面: {last_poll_url}" if last_poll_url else ""
            return APIResponse(
                success=False,
                message=f"登录超时（5 分钟），未检测到登录成功{last_info}",
                data={"platform": platform},
            )
    except Exception as e:
        logger.error(f"[{platform}:{account_id}] 浏览器登录异常: {e}")
        # 确保浏览器被关闭
        try:
            await browser.close()
        except Exception:
            pass
        try:
            await pw.stop()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"浏览器登录过程异常: {str(e)}")


@router.post("/{account_id}/debug-verify", response_model=APIResponse)
async def debug_verify_session(account_id: int, db: AsyncSession = Depends(get_db)):
    """
    诊断端点：详细输出会话验证过程，返回截图路径、CSS 匹配结果、URL 等。
    """
    from loguru import logger
    import json, base64, time

    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    platform = account.platform

    from backend.services.session_manager import session_manager, PLATFORM_CONFIGS

    config = PLATFORM_CONFIGS.get(platform, {})
    check_url = config.get("check_url", "")
    indicator = config.get("logged_in_indicator", "")
    exclude_urls = config.get("check_exclude_url", [])

    state_path = session_manager.storage_dir / platform / f"{account_id}.json"
    storage_info = {}
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            storage_info = {
                "has_file": True,
                "cookie_count": len(state.get("cookies", [])),
                "cookie_names": [c["name"] for c in state.get("cookies", [])],
            }
        except Exception as e:
            storage_info = {"has_file": True, "error": str(e)}
    else:
        storage_info = {"has_file": False}

    # 逐步骤验证
    steps = []
    logged_in = False

    try:
        ctx = await session_manager.get_context(platform, str(account_id), force_refresh=True)
    except Exception as e:
        steps.append({"step": "get_context", "status": "error", "detail": str(e)})
        return APIResponse(
            success=False,
            message=f"诊断完成（get_context 失败）",
            data={"platform": platform, "storage": storage_info, "steps": steps},
        )

    if ctx is None:
        steps.append({"step": "get_context", "status": "no_context", "detail": "返回 None"})
        return APIResponse(
            success=False,
            message="诊断完成（get_context 返回 None，即验证失败）",
            data={"platform": platform, "storage": storage_info, "steps": steps},
        )

    steps.append({"step": "get_context", "status": "ok"})

    # 现在有了已登录的 context，做详细验证
    try:
        page = await ctx.new_page()
        t0 = time.time()
        await page.goto(check_url, wait_until="networkidle", timeout=30000)
        steps.append({"step": "goto_check_url", "status": "ok", "elapsed": round(time.time() - t0, 2)})

        await page.wait_for_timeout(3000)
        url = page.url
        steps.append({"step": "page_url", "url": url})

        # CSS 选择器逐个测试
        if indicator:
            selectors = [s.strip() for s in indicator.split(",") if s.strip()]
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    steps.append({"step": f"css:{sel}", "found": el is not None})
                except Exception as e:
                    steps.append({"step": f"css:{sel}", "found": False, "error": str(e)[:100]})

        # URL 排除检查
        url_passed = all(kw not in url.lower() for kw in exclude_urls)
        steps.append({"step": "url_check", "passed": url_passed, "exclude_keywords": exclude_urls})

        # 截图
        import tempfile, os as _os
        screenshot_dir = session_manager.storage_dir.parent / "debug_screenshots"
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        screenshot_path = str(screenshot_dir / f"debug_{platform}_{account_id}_{int(time.time())}.png")
        await page.screenshot(path=screenshot_path, full_page=False)
        steps.append({"step": "screenshot", "path": screenshot_path})

        await page.close()
        logged_in = True

    except Exception as e:
        steps.append({"step": "verify_error", "detail": str(e)[:300]})

    return APIResponse(
        success=logged_in,
        message=f"诊断完成: {'✅ 验证通过' if logged_in else '❌ 验证失败'}",
        data={
            "platform": platform,
            "check_url": check_url,
            "storage": storage_info,
            "steps": steps,
        },
    )


@router.get("", response_model=List[PlatformAccountResponse])
async def list_accounts(
    platform: str = None,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(PlatformAccount)
    if platform:
        query = query.where(PlatformAccount.platform == platform)
    if status:
        query = query.where(PlatformAccount.status == status)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=PlatformAccountResponse)
async def create_account(
    data: PlatformAccountCreate,
    db: AsyncSession = Depends(get_db),
):
    account = PlatformAccount(
        platform=data.platform,
        account_name=data.account_name,
        account_id=data.account_id,
        login_type=data.login_type,
        auth_config=data._parse_auth_config(data.auth_config),
        proxy_ip=data.proxy_ip,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account


@router.get("/{account_id}", response_model=PlatformAccountResponse)
async def get_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    return account


@router.put("/{account_id}", response_model=PlatformAccountResponse)
async def update_account(
    account_id: int,
    data: PlatformAccountUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    update_data = data.model_dump(exclude_unset=True)

    # 特殊处理 auth_config：字符串 → dict
    if "auth_config" in update_data:
        update_data["auth_config"] = data._parse_auth_config(update_data["auth_config"])

    for key, value in update_data.items():
        if hasattr(account, key) and value is not None:
            setattr(account, key, value)
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/{account_id}", response_model=APIResponse)
async def delete_account(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")
    await db.delete(account)
    await db.commit()
    return APIResponse(success=True, message="账号已删除")


@router.post("/{account_id}/check", response_model=APIResponse)
async def check_account_session(
    account_id: int,
    db: AsyncSession = Depends(get_db),
):
    """手动触发账号会话检查"""
    from loguru import logger

    result = await db.execute(
        select(PlatformAccount).where(PlatformAccount.id == account_id)
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(status_code=404, detail="账号不存在")

    # 保存旧状态，仅当明确判断结果后才更新
    old_status = account.status

    try:
        from backend.services.session_manager import session_manager

        ctx = await session_manager.get_context(
            platform=account.platform,
            account_id=str(account.id),
        )

        if ctx:
            account.status = "active"
            account.last_check_at = __import__("datetime").datetime.now()
            await db.commit()
            return APIResponse(success=True, message="会话有效", data={"status": "active"})
        else:
            # get_context 返回 None = 会话确实失效，更新为 expired
            account.status = "expired"
            account.last_check_at = __import__("datetime").datetime.now()
            await db.commit()
            return APIResponse(success=False, message="会话已过期，需要重新登录", data={"status": "expired"})
    except Exception as e:
        logger.error(f"会话检查异常 [{account.platform}:{account_id}]: {e}")
        # 异常时不改 status，避免把 active 误改为 error
        # 仅记录检查时间，保留原有状态
        account.last_check_at = __import__("datetime").datetime.now()
        await db.commit()
        return APIResponse(
            success=False,
            message=f"会话检查失败（保留原状态「{old_status}」）：{str(e)[:200]}",
            data={"status": old_status},
        )
