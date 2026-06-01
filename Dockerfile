# 使用官方輕量級 Python 映像檔
FROM python:3.10-slim

# 設定工作目錄
WORKDIR /app

# 複製並安裝套件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 複製所有程式碼到容器中
COPY . .

# 使用 gunicorn 啟動 Flask 應用程式
CMD exec gunicorn --bind :$PORT --workers 1 --threads 8 --timeout 0 app:app
