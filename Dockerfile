# 使用 Python 3.11.6 作為基礎映像
FROM python:3.11.6

# 更新套件庫並安裝 cron
RUN apt-get update && apt-get install -y cron

# 設置工作目錄
WORKDIR /app

# 複製當前目錄中的所有文件到容器的 /app 目錄
COPY . /app

# 安裝應用所需的所有 Python 依賴項
RUN pip install --no-cache-dir -r requirements.txt

# 複製 cron 任務設定檔到容器內
COPY cleanup_cron /etc/cron.d/cleanup_cron

# 設定適當權限並將其加入 crontab
RUN chmod 0644 /etc/cron.d/cleanup_cron && crontab /etc/cron.d/cleanup_cron

# 建立 cron 日誌檔 (選用)
RUN touch /var/log/cron.log

# 複製啟動腳本
COPY start.sh /start.sh
RUN chmod +x /start.sh

# 使用啟動腳本作為容器啟動命令
CMD ["/start.sh"]

