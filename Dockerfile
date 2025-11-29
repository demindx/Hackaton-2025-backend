FROM python:3.13

WORKDIR /app

RUN pip install uv

COPY . .

ENV UV_PROJECT_ENVIRONMENT="/usr/local/"
RUN uv sync

EXPOSE 8080

CMD ["uv", "run", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
# CMD ["uv", "run", "fastapi", "dev", "src/main.py", "--port", "8080","--host", "0.0.0.0"]
