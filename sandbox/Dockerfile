FROM python:3.13-slim

# 分析要用 pandas
RUN pip install --no-cache-dir pandas

# 非 root 用户跑代码
RUN useradd --create-home sandbox
USER sandbox
WORKDIR /home/sandbox