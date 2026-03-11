FROM python:3.10-slim

WORKDIR /app
复制并安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 暴露 Streamlit 默认端口
EXPOSE 8501

# 启动命令：必须加上 --server.address=0.0.0.0 否则外部无法访问
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]

##Todo: 目前只能关闭梯子情况下启动才可连接, [某些情况下也能成功]