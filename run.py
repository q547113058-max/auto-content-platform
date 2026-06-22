"""
AutoContentPlatform 启动脚本
职责：杀掉旧进程 → 设置 EventLoop → 启动 uvicorn
必须在项目根目录 (auto-content-platform/) 下运行。
"""
import os
import sys
import time
import socket
import signal
import subprocess

PORT = 8005
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── 步骤 0: 切到项目根目录 ──
os.chdir(PROJECT_DIR)
print(f"[run] 工作目录: {PROJECT_DIR}")


def kill_port_owner(port: int):
    """强杀占用指定端口的进程（Windows）"""
    if sys.platform != "win32":
        return
    try:
        # netstat -ano | findstr :PORT
        result = subprocess.run(
            ["cmd", "/c", f"netstat -ano | findstr :{port}"],
            capture_output=True, text=True, timeout=5,
        )
        pids = set()
        for line in result.stdout.strip().split("\n"):
            parts = line.strip().split()
            if len(parts) >= 5 and parts[4].isdigit():
                pids.add(parts[4])
        for pid in pids:
            try:
                subprocess.run(["taskkill", "/PID", pid, "/F"],
                               capture_output=True, timeout=5)
                print(f"[run] 已终止旧进程 PID={pid}")
            except Exception:
                pass
        if pids:
            time.sleep(1.5)  # 等端口释放
    except Exception:
        pass


def ensure_port_free(port: int, retries: int = 10):
    """确保端口空闲"""
    for i in range(retries):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(("127.0.0.1", port))
        sock.close()
        if result != 0:  # 连接失败 = 端口空闲
            return True
        print(f"[run] 端口 {port} 仍被占用，等待释放 ({i+1}/{retries})...")
        kill_port_owner(port)
        time.sleep(1)
    return False


# ── 步骤 1: 杀旧进程、释放端口 ──
print(f"[run] 检查端口 {PORT}...")
kill_port_owner(PORT)
if not ensure_port_free(PORT):
    print(f"[run] [FAIL] 端口 {PORT} 无法释放，请手动检查后重试")
    sys.exit(1)
print(f"[run] [OK] 端口 {PORT} 空闲")

# ── 步骤 2: Windows Event Loop ──
if sys.platform == "win32":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    print("[run] EventLoop: WindowsProactorEventLoopPolicy")

# ── 步骤 3: 启动 ──
import uvicorn

print(f"[run] [START] 启动服务 http://127.0.0.1:{PORT}")
print("[run] 按 Ctrl+C 停止")

uvicorn.run(
    "backend.main:app",
    host="0.0.0.0",
    port=PORT,
    reload=False,
)
