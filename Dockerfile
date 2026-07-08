FROM python:3.12-slim

WORKDIR /srv

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Only what the running server needs. Everything runs on the deterministic path,
# so no API keys are required for the live demo.
COPY app ./app
COPY data ./data
COPY static ./static

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
