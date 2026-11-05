FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY backend /app/backend
COPY data /app/data
COPY public /app/public
RUN groupadd -g 10001 campus && useradd -u 10001 -g campus -s /usr/sbin/nologin campus \
    && mkdir -p /data/uploads && chown -R campus:campus /data/uploads /app
USER campus
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
