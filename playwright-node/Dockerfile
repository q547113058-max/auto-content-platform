FROM mcr.microsoft.com/playwright/python:v1.47.0-noble

WORKDIR /app

# 复制 requirements 并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制 playwright automation 代码
COPY playwright_automation/ ./playwright_automation/
COPY backend/ ./backend/

# 暴露 CDP 和 VNC 端口  
EXPOSE 9222 5900

# 默认命令：启动一个等待连接的 Playwright
CMD ["python", "-c", "import time; time.sleep(999999)"]
