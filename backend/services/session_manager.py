"""
会话管理模块 — 三层会话保活机制
L1: API Token (微信公众号)
L2: Playwright StorageState 持久化 (全平台)
L3: 自动登录 / 人工干预
"""
from __future__ import annotations

# Windows: Playwright 子进程需要 ProactorEventLoop，必须在所有异步导入前设置
import sys as _sys
if _sys.platform == "win32":
    import asyncio as _asyncio
    _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())

import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from backend.utils.timezone_utils import now_shanghai
from typing import Optional, Dict, Any
from loguru import logger
from backend.config import settings

# Playwright 相关导入（运行时检查，避免在非浏览器环境崩溃）
try:
    from playwright.async_api import async_playwright, Browser, BrowserContext
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    logger.warning("Playwright not installed. Browser automation disabled.")


# ======================= 反检测脚本 =======================
STEALTH_JS = """
// ==== 隐藏 webdriver 标记 ====
Object.defineProperty(navigator, 'webdriver', { get: () => undefined });

// ==== 伪造 Chrome 运行时 ====
window.chrome = {
    runtime: {},
    loadTimes: function() {},
    csi: function() {},
    app: {}
};

// ==== 伪造 plugins ====
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
        ];
        plugins.item = (i) => plugins[i];
        plugins.namedItem = (name) => plugins.find(p => p.name === name);
        plugins.refresh = () => {};
        return plugins;
    }
});

// ==== 伪造 permissions ====
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
    Promise.resolve({ state: Notification.permission }) :
    originalQuery(parameters)
);

// ==== 伪造 languages ====
Object.defineProperty(navigator, 'languages', { get: () => ['zh-CN', 'zh', 'en'] });
Object.defineProperty(navigator, 'language', { get: () => 'zh-CN' });

// ==== 伪造 platform ====
Object.defineProperty(navigator, 'platform', { get: () => 'Win32' });

// ==== 伪造 hardwareConcurrency ====
Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });

// ==== 伪造 deviceMemory ====
Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });

// ==== 移除 PhantomJS 特征 ====
delete window.callPhantom;
delete window._phantom;
delete window.__phantomas;

// ==== 伪造 Canvas 指纹 ====
(function() {
    const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
    HTMLCanvasElement.prototype.toDataURL = function(type) {
        if (arguments[0] === 'image/png' && this.width > 200 && this.height > 20) {
            const context = this.getContext('2d');
            if (context) {
                const imageData = context.getImageData(0, 0, this.width, this.height);
                // 随机微调一个像素，改变指纹
                const offset = Math.floor(Math.random() * 5) + 1;
                if (imageData.data.length > offset) {
                    imageData.data[offset] = imageData.data[offset] + 1;
                    context.putImageData(imageData, 0, 0);
                }
            }
        }
        return originalToDataURL.apply(this, arguments);
    };
})();
"""

# ======================= 平台配置 =======================
PLATFORM_CONFIGS = {
    "xiaohongshu": {
        "login_url": "https://creator.xiaohongshu.com/login",
        "check_url": "https://creator.xiaohongshu.com/publish/publish",
        "logged_in_indicator": '[class*="creator"]',  # 创作者中心元素
    },
    "zhihu": {
        "login_url": "https://www.zhihu.com/signin",
        "check_url": "https://www.zhihu.com/notifications",
        "logged_in_indicator": (
            '[class*="AppHeader-profile"], '          # 顶部用户头像区域
            '[class*="Notification"], '                # 通知入口（已登录可见）
            '[class*="avatar"], '                     # 用户头像
            '.Modal, [class*="signin"], [class*="SignFlow"]'  # 未登录会出现登录弹窗
        ),
        "check_exclude_url": ["signin", "login", "SignFlow"],
        "logged_out_indicator": '[class*="SignFlow"], [class*="signin"]',  # 未登录标志
    },
    "weibo": {
        "login_url": "https://weibo.com/login.php",
        "check_url": "https://weibo.com",
        "logged_in_indicator": (
            # 新版微博 UI 登录标识
            '.woo-box-flex, '
            # 旧版微博导航栏
            '.gn_nav, [class*="gn_header"], '
            # 通用：顶部导航/个人中心入口
            '[class*="Frame_wrap"], '
            # 用户头像/昵称区域（任何能识别已登录的元素）
            '.head_pic, [class*="avatar"], '
            # 右侧个人信息面板
            '[class*="Profile"], [class*="person"]'
        ),
        "check_exclude_url": ["login", "signin", "register", "passport"],
    },
    "wechat": {
        "login_type": "api",  # 使用 API Token，不走 Playwright
        "check_url": "https://api.weixin.qq.com/cgi-bin/token",
    },
    "toutiao": {
        "login_url": "https://mp.toutiao.com/",
        "check_url": "https://mp.toutiao.com/profile/",
        "logged_in_indicator": '[class*="author-name"]',
    },
    "douyin": {
        "login_url": "https://creator.douyin.com/",
        "check_url": "https://creator.douyin.com/creator-micro/content/upload",
        "logged_in_indicator": '[class*="creator"]',
    },
}


class SessionManager:
    """统一会话管理器"""

    def __init__(self):
        self._browser: Optional[Browser] = None
        self._pw = None  # 持久化 playwright 实例，避免 event loop 问题
        self._contexts: Dict[str, BrowserContext] = {}
        self.storage_dir = Path(settings.STORAGE_STATES_DIR)

    @property
    async def browser(self) -> Browser:
        """懒加载浏览器实例（兼容 Windows ProactorEventLoop）
        
        当检测到 _browser 断开连接时，同时复位 _pw，
        避免残留的 Playwright 实例在当前 event loop 中不可用导致异常。
        """
        try:
            connected = self._browser is not None and self._browser.is_connected()
        except Exception:
            connected = False
            logger.warning("[SessionManager] is_connected() 异常，强制重建")

        if not connected:
            if not PLAYWRIGHT_AVAILABLE:
                raise RuntimeError("Playwright not installed")
            import sys, asyncio

            # 彻底清理旧实例
            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None

            if self._pw is not None:
                try:
                    await self._pw.stop()
                except Exception:
                    pass
                self._pw = None

            # 清理所有已失效的上下文缓存
            for key in list(self._contexts.keys()):
                try:
                    await self._contexts[key].close()
                except Exception:
                    pass
            self._contexts.clear()

            # Windows: 确保当前 loop 是 ProactorEventLoop，Playwright subprocess 需要
            if sys.platform == "win32":
                loop = asyncio.get_event_loop()
                if not isinstance(loop, asyncio.ProactorEventLoop):
                    logger.warning(f"[SessionManager] 当前 loop 是 {type(loop).__name__}，尝试切换为 ProactorEventLoop")
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                    new_loop = asyncio.ProactorEventLoop()
                    asyncio.set_event_loop(new_loop)
                    logger.info("[SessionManager] 已切换到 ProactorEventLoop")

            self._pw = await async_playwright().start()
            launch_options = {
                "headless": settings.PLAYWRIGHT_HEADLESS,
                "args": [
                    "--disable-blink-features=AutomationControlled",
                    "--disable-features=IsolateOrigins,site-per-process",
                    "--disable-site-isolation-trials",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-extensions",
                ],
            }
            self._browser = await self._pw.chromium.launch(**launch_options)
            logger.info("[SessionManager] Browser 重新启动成功")
        return self._browser

    async def get_context(
        self,
        platform: str,
        account_id: str,
        force_refresh: bool = False,
    ) -> Optional[BrowserContext]:
        """
        获取已登录的浏览器上下文
        优先级：StorageState文件 > Cookie注入 > 需要重新登录
        """
        context_key = f"{platform}:{account_id}"

        # 检查缓存上下文是否仍然有效
        if context_key in self._contexts and not force_refresh:
            context = self._contexts[context_key]
            try:
                pages = context.pages
                if pages:
                    await pages[0].goto("about:blank")
                else:
                    # 上下文没有打开的页面，创建一个临时页面检查
                    page = await context.new_page()
                    await page.close()
                return context
            except Exception:
                logger.warning(f"[{platform}:{account_id}] 缓存上下文失效，清理")
                try:
                    await context.close()
                except Exception:
                    pass
                del self._contexts[context_key]

        state_path = self.storage_dir / platform / f"{account_id}.json"

        # force_refresh 只跳过缓存（上面已处理），不跳过 state file 加载
        if state_path.exists():
            try:
                storage_state = json.loads(state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"[{platform}:{account_id}] StorageState 文件损坏: {e}")
                return None

            if self._check_cookies_valid(storage_state):
                try:
                    context = await self._create_context_with_state(storage_state)
                except Exception as e:
                    logger.error(f"[{platform}:{account_id}] 创建浏览器上下文失败: {e}")
                    return None

                try:
                    logged_in = await self._verify_logged_in(context, platform)
                except Exception as e:
                    logger.error(f"[{platform}:{account_id}] 登录验证过程异常: {e}")
                    logged_in = False

                if logged_in:
                    self._contexts[context_key] = context
                    logger.info(f"[{platform}:{account_id}] 会话有效，StorageState 复用")
                    return context
                else:
                    logger.warning(f"[{platform}:{account_id}] StorageState 过期，需重新登录")
                    try:
                        await context.close()
                    except Exception:
                        pass
            else:
                logger.warning(f"[{platform}:{account_id}] Cookie 已过期")
        else:
            logger.info(f"[{platform}:{account_id}] 无 StorageState 文件，需首次登录")

        return None

    async def _create_context_with_state(
        self, storage_state: Dict[str, Any]
    ) -> BrowserContext:
        """使用 StorageState 创建浏览器上下文，含反检测配置"""
        browser = await self.browser
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            geolocation={"latitude": 39.9042, "longitude": 116.4074},
            permissions=["geolocation"],
            storage_state=storage_state,
        )
        await context.add_init_script(STEALTH_JS)
        return context

    async def create_fresh_context(self) -> BrowserContext:
        """创建一个干净的浏览器上下文（未登录）"""
        browser = await self.browser
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
            geolocation={"latitude": 39.9042, "longitude": 116.4074},
            permissions=["geolocation"],
        )
        await context.add_init_script(STEALTH_JS)
        return context

    def _check_cookies_valid(self, storage_state: Dict[str, Any]) -> bool:
        """检查 StorageState 中 Cookie 是否有效"""
        cookies = storage_state.get("cookies", [])
        if not cookies:
            return False

        now = time.time()
        active_cookies = 0
        for cookie in cookies:
            expires = cookie.get("expires", -1)
            if expires == -1:  # session cookie
                active_cookies += 1
                continue
            if expires > now:
                active_cookies += 1

        return active_cookies >= 2  # 至少 2 个有效 cookie

    async def _verify_logged_in(
        self, context: BrowserContext, platform: str
    ) -> bool:
        """验证是否处于登录状态"""
        config = PLATFORM_CONFIGS.get(platform, {})
        check_url = config.get("check_url")
        indicator = config.get("logged_in_indicator")
        exclude_urls = config.get("check_exclude_url", [])

        if not check_url:
            return True

        page = None
        try:
            page = await context.new_page()
            logger.info(f"[{platform}] 开始验证登录状态，访问: {check_url}")

            # 使用 networkidle 确保 SPA 页面完全渲染（微博、知乎等需要）
            try:
                await page.goto(check_url, wait_until="networkidle", timeout=25000)
            except Exception:
                # networkidle 超时降级为 domcontentloaded + 延长等待
                logger.info(f"[{platform}] networkidle 超时，降级为 domcontentloaded")
                await page.goto(check_url, wait_until="domcontentloaded", timeout=20000)

            # 等待 SPA 渲染完成（5 秒，微博/知乎等重型页面需要）
            await page.wait_for_timeout(5000)

            # 如果是未登录状态，SPA 可能还会做一次客户端跳转，再等 2 秒
            await page.wait_for_timeout(2000)

            url = page.url
            logger.info(f"[{platform}] 页面实际 URL: {url}")

            # 先检查是否跳转到登录页（最可靠的判断）
            for kw in exclude_urls:
                if kw.lower() in url.lower():
                    logger.warning(f"[{platform}] URL 包含排除关键字「{kw}」，判定为未登录: {url}")
                    # 保存失败截图供排查
                    try:
                        screenshot_dir = Path(settings.STORAGE_STATES_DIR).parent / "debug_screenshots"
                        screenshot_dir.mkdir(parents=True, exist_ok=True)
                        screenshot_path = screenshot_dir / f"{platform}_failed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                        await page.screenshot(path=str(screenshot_path))
                        logger.info(f"[{platform}] 验证失败截图已保存: {screenshot_path}")
                    except Exception:
                        pass
                    return False

            # 再尝试 CSS 选择器（使用 wait_for_selector 提高容错）
            if indicator:
                selectors = [s.strip() for s in indicator.split(",") if s.strip()]
                for sel in selectors:
                    try:
                        # 用 wait_for_selector 容忍 SPA 异步渲染延迟
                        element = await page.wait_for_selector(sel, state="attached", timeout=3000)
                        if element:
                            logger.info(f"[{platform}] 登录验证通过 (CSS 匹配: {sel})")
                            return True
                    except Exception:
                        # 3 秒超时正常，试下一个选择器
                        continue

            # 检查是否有"未登录"标志元素（如登录弹窗、登录按钮）
            logged_out_indicator = config.get("logged_out_indicator")
            if logged_out_indicator:
                for sel in logged_out_indicator.split(","):
                    sel = sel.strip()
                    if not sel:
                        continue
                    try:
                        element = await page.query_selector(sel)
                        if element:
                            logger.warning(f"[{platform}] 检测到未登录标志元素: {sel}")
                            # 保存截图
                            try:
                                screenshot_dir = Path(settings.STORAGE_STATES_DIR).parent / "debug_screenshots"
                                screenshot_dir.mkdir(parents=True, exist_ok=True)
                                screenshot_path = screenshot_dir / f"{platform}_logged_out_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                                await page.screenshot(path=str(screenshot_path))
                                logger.info(f"[{platform}] 未登录标志截图: {screenshot_path}")
                            except Exception:
                                pass
                            return False
                    except Exception:
                        pass

            # 回退：URL 中没有配置的排除关键字才算通过
            # 注意：必须使用平台配置的 exclude_urls，不能硬编码
            is_logged_in = all(
                kw not in url.lower() for kw in (exclude_urls or ["login", "signin", "register"])
            )
            if is_logged_in:
                logger.info(f"[{platform}] 登录验证通过 (URL 回退检查: {url}）")
            else:
                logger.warning(f"[{platform}] 登录验证未通过 (URL={url}, 排除关键={exclude_urls})")
                try:
                    screenshot_dir = Path(settings.STORAGE_STATES_DIR).parent / "debug_screenshots"
                    screenshot_dir.mkdir(parents=True, exist_ok=True)
                    screenshot_path = screenshot_dir / f"{platform}_fallback_fail_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    await page.screenshot(path=str(screenshot_path))
                    logger.info(f"[{platform}] 回退失败截图: {screenshot_path}")
                except Exception:
                    pass
            return is_logged_in
        except Exception as e:
            logger.error(f"[{platform}] 登录验证异常: {e}")
            return False
        finally:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass

    async def save_session(
        self, context: BrowserContext, platform: str, account_id: str
    ):
        """保存 StorageState 到文件"""
        state = await context.storage_state()

        platform_dir = self.storage_dir / platform
        platform_dir.mkdir(parents=True, exist_ok=True)

        state_path = platform_dir / f"{account_id}.json"
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

        # 更新元数据
        meta_path = platform_dir / "meta.json"
        meta = {}
        if meta_path.exists():
            meta = json.loads(meta_path.read_text(encoding="utf-8"))

        meta[account_id] = {
            "last_check_at": now_shanghai().isoformat(),
            "status": "active",
            "cookie_count": len(state.get("cookies", [])),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"[{platform}:{account_id}] StorageState 已保存")

    async def create_login_browser(self, platform: str):
        """
        一键登录：启动一个可见的 Chromium 浏览器，打开平台登录页。
        返回 (playwright_instance, browser, context, page) 四元组，
        调用方负责轮询登录状态，并在完成后关闭 browser + playwright。
        """
        if not PLAYWRIGHT_AVAILABLE:
            raise RuntimeError("Playwright not installed")

        config = PLATFORM_CONFIGS.get(platform, {})
        login_url = config.get("login_url", "")
        if not login_url:
            raise ValueError(f"平台 {platform} 未配置 login_url")

        # 确保共享的 playwright 实例已启动（复用 SessionManager 的 browser 属性逻辑）
        await self.browser  # 触发 _pw 和 _browser 初始化（headless）

        # 额外启动一个可见的浏览器用于用户登录
        login_browser = await self._pw.chromium.launch(
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )
        context = await login_browser.new_context(
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        await context.add_init_script(STEALTH_JS)
        page = await context.new_page()
        await page.goto(login_url, wait_until="networkidle", timeout=30000)
        logger.info(f"[{platform}] 一键登录：浏览器已打开 {login_url}，等待用户完成登录...")

        return self._pw, login_browser, context, page

    async def get_login_page(self, platform: str) -> BrowserContext:
        """
        L3: 获取用于手动登录的页面
        返回一个干净的浏览器上下文，用户可在 VNC 中完成登录
        """
        config = PLATFORM_CONFIGS.get(platform, {})
        login_url = config.get("login_url", "")

        context = await self.create_fresh_context()
        page = await context.new_page()
        if login_url:
            await page.goto(login_url, wait_until="networkidle")

        # 保持页面打开，等待用户登录
        logger.info(f"[{platform}] 登录页面已打开，等待登录...")
        return context

    async def check_all_sessions(self) -> Dict[str, Any]:
        """检查所有平台的会话状态，返回健康报告"""
        report = {}

        for platform in PLATFORM_CONFIGS:
            platform_dir = self.storage_dir / platform
            if not platform_dir.exists():
                report[platform] = {"status": "empty", "accounts": []}
                continue

            meta_path = platform_dir / "meta.json"
            if not meta_path.exists():
                report[platform] = {"status": "no_meta", "accounts": []}
                continue

            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            accounts_status = []
            for account_id, info in meta.items():
                state_path = platform_dir / f"{account_id}.json"
                is_valid = False
                if state_path.exists():
                    state = json.loads(state_path.read_text(encoding="utf-8"))
                    is_valid = self._check_cookies_valid(state)

                last_check = info.get("last_check_at", "unknown")
                accounts_status.append({
                    "account_id": account_id,
                    "valid": is_valid,
                    "last_check_at": last_check,
                })

            report[platform] = {
                "status": "healthy" if all(a["valid"] for a in accounts_status) else "degraded",
                "accounts": accounts_status,
            }

        return report

    async def cleanup(self):
        """清理所有上下���和浏览器"""
        for ctx in self._contexts.values():
            try:
                await ctx.close()
            except Exception:
                pass
        self._contexts.clear()

        if self._browser:
            try:
                await self._browser.close()
            except Exception:
                pass
            self._browser = None

        logger.info("SessionManager 已清理")


# ======================= 微信公众号 API Token 管理 =======================
class WechatTokenManager:
    """
    微信公众号 access_token 管理（L1: API Token 层）
    - Redis 缓存，自动续期
    - 提前 5 分钟过期，避免临界状态
    """

    def __init__(self, redis_client=None):
        self.redis = redis_client
        self._cache: Dict[str, Dict[str, Any]] = {}

    async def get_access_token(
        self, appid: str, appsecret: str, force_refresh: bool = False
    ) -> str:
        """
        获取微信公众号 access_token
        Redis 优先 → 本地缓存 → API 请求
        """
        cache_key = f"wechat:token:{appid}"

        # Redis 查找
        if self.redis and not force_refresh:
            token = await self.redis.get(cache_key)
            if token:
                return token.decode("utf-8") if isinstance(token, bytes) else token

        # 本地缓存查找
        if appid in self._cache and not force_refresh:
            cached = self._cache[appid]
            if time.time() < cached["expires_at"]:
                return cached["token"]

        # 请求微信 API
        import httpx
        url = "https://api.weixin.qq.com/cgi-bin/token"
        params = {
            "grant_type": "client_credential",
            "appid": appid,
            "secret": appsecret,
        }

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=10)
            data = resp.json()

        if "access_token" in data:
            token = data["access_token"]
            expires_in = data.get("expires_in", 7200) - 300  # 提前 5 分钟

            # 写入 Redis
            if self.redis:
                await self.redis.setex(cache_key, expires_in, token)

            # 写入本地缓存
            self._cache[appid] = {
                "token": token,
                "expires_at": time.time() + expires_in,
            }

            logger.info(f"WeChat access_token 已更新，有效期 {expires_in}s")
            return token
        else:
            error_msg = data.get("errmsg", "未知错误")
            logger.error(f"WeChat token 获取失败: {error_msg}")
            raise RuntimeError(f"WeChat API error: {error_msg}")


# 全局单例
session_manager = SessionManager()
wechat_token_manager = WechatTokenManager()
