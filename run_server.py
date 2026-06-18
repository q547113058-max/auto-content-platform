"""
后端启动脚本 — Windows ProactorEventLoop 兼容版
解决 Playwright 在 uvicorn asyncio loop 下无法启动浏览器子进程的问题
"""
import sys
import asyncio

# 必须在 uvicorn 启动之前设置，且要用 loop_factory 方式
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        loop="asyncio",  # 使用 asyncio loop（上面已设置为 ProactorEventLoop）
    )
