FROM python:3.13-slim
WORKDIR /app
COPY requirements-worker.txt .
RUN pip install --no-cache-dir -r requirements-worker.txt
COPY pyproject.toml .
COPY docops ./docops
RUN pip install --no-cache-dir --no-deps . && useradd --uid 10001 --create-home worker
USER 10001
ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "docops.azure_worker"]
