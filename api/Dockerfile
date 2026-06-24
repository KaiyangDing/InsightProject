FROM python:3.13-slim

# docker CLI：DockerCodeExecutor 通过 `docker run` 在沙箱里跑分析代码（配合下面挂载宿主 socket）
RUN apt-get update && apt-get install -y --no-install-recommends docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir uv

WORKDIR /app
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev

COPY api ./api

ENV PYTHONUTF8=1 PYTHONPATH=/app
EXPOSE 8000
CMD ["uv", "run", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]