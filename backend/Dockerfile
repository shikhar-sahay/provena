FROM python:3.13-slim

WORKDIR /code

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN addgroup --system provena && adduser --system --ingroup provena provena
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini .

RUN mkdir -p /evidence /exports && chown -R provena:provena /code /evidence /exports && chmod 700 /evidence /exports
ENV EVIDENCE_STORAGE_ROOT=/evidence EXPORT_STORAGE_ROOT=/exports
USER provena

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=6 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/ready', timeout=4)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
