FROM python:3.13

WORKDIR /app

RUN pip install uv
ENV UV_SYSTEM_PYTHON=1
ENV UV_LINK_MODE=copy

# backend deps
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

# backend code
COPY backend/app /app/app

WORKDIR /app
EXPOSE 8080

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]