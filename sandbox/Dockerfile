FROM python:3.13-slim

# 中文字体：否则 matplotlib 画中文标签会变成 □□
RUN apt-get update && apt-get install -y --no-install-recommends fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir pandas matplotlib

RUN useradd --create-home sandbox
USER sandbox
WORKDIR /home/sandbox