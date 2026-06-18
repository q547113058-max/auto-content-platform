"""
会话管理模块 — 三层会话保活机制
L1: API Token (微信公众号)
L2: Playwright StorageState 持久化 (全平台)
L3: 自动登录 / 人工干预
"""
from __future__ import annotations
import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timezone, timedelta
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
        "check_url": "https://www.zhihu.com",
        "logged_in_indicator": '[class*="AppHeader-profile"], .AppHeader-profile, [class*="user"], .top-nav-profile',
        "check_exclude_url": ["signin", "login"],
    },
    "weibo": {
        "login_url": "https://weibo.com/login.php",
        "check_url": "https://weibo.com",
        "logged_in_indicator": '[title*="我的主页"]',
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
        """懒加载浏览器实例（兼容 Windows ProactorEventLoop）"""
        if self._browser is None or not self._browser.is_connected():
            if not PLAYWRIGHT_AVAILABLE:
                raise RuntimeError("Playwright not installed")
            import sys, asyncio
            # Windows: 确保当前 loop 是 ProactorEventLoop，Playwright subprocess 需要
            if sys.platform == "win32":
                loop = asyncio.get_event_loop()
                if not isinstance(loop, asyncio.ProactorEventLoop):
                    logger.warning(f"[SessionManager] 当前 loop 是 {type(loop).__name__}，尝试切换为 ProactorEventLoop")
                    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
                    new_loop = asyncio.ProactorEventLoop()
                    asyncio.set_event_loop(new_loop)
                    logger.info("[SessionManager] 已切换到 ProactorEventLoop")
            # 使用 async with 语法兼容 Windows uvicorn ProactorEventLoop
            if self._pw is None:
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
            logger.info("Browser launched")
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

        if context_key in self._contexts and not force_refresh:
            context = self._contexts[context_key]
            try:
                await context.pages[0].goto("about:blank")
                return context
            except Exception:
                pass

        state_path = self.storage_dir / platform / f"{account_id}.json"

        if state_path.exists() and not force_refresh:
            storage_state = json.loads(state_path.read_text(encoding="utf-8"))
            if self._check_cookies_valid(storage_state):
                context = await self._create_context_with_state(storage_state)
                if await self._verify_logged_in(context, platform):
                    self._contexts[context_key] = context
                    logger.info(f"[{platform}:{account_id}] 会话有效，StorageState 复用")
                    return context
                else:
                    logger.warning(f"[{platform}:{account_id}] StorageState 过期，需重新登录")
            else:
                logger.warning(f"[{platform}:{account_id}] Cookie 已过期")
        else:
            logger.info(f"[{platform}:{account_id}] 无 StorageState，需首次登录")

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

        try:
            page = await context.new_page()
            await page.goto(check_url, wait_until="domcontentloaded", timeout=20000)

            # 先检查是否跳转到登录页（最可靠的判断）
            url = page.url
            for kw in exclude_urls:
                if kw.lower() in url.lower():
                    logger.info(f"[{platform}] 页面跳转至登录页: {url}")
                    await page.close()
                    return False

            # 再尝试 CSS 选择器
            if indicator:
                # 支持逗号分隔的多个选择器
                selectors = [s.strip() for s in indicator.split(",") if s.strip()]
                for sel in selectors:
                    try:
                        element = await page.query_selector(sel)
                        if element:
                            logger.info(f"[{platform}] 登录验证通过 (匹配: {sel})")
                            await page.close()
                            return True
                    except Exception:
                        continue

            # 回退：URL 中没有 login/signin 也算通过
            is_logged_in = all(
                kw not in url.lower() for kw in ["login", "signin", "register"]
            )
            if is_logged_in:
                logger.info(f"[{platform}] 登录验证通过 (URL检查: {url})")

            await page.close()
            return is_logged_in
        except Exception as e:
            logger.error(f"[{platform}] 登录验证失败: {e}")
            return False

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
            "last_check_at": datetime.now(timezone.utc).isoformat(),
            "status": "active",
            "cookie_count": len(state.get("cookies", [])),
        }
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        logger.info(f"[{platform}:{account_id}] StorageState 已保存")

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
