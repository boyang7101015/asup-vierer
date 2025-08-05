#!/bin/bash
# 啟動 cron（背景執行）
cron

# 啟動 Gunicorn 應用
exec gunicorn -w 4 --threads 2 -b 0.0.0.0:5000 app:app

