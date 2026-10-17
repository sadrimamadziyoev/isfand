FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements.lock ./
RUN --mount=type=secret,id=build_ca,required=false \
    if [ -f /run/secrets/build_ca ]; then export PIP_CERT=/run/secrets/build_ca; fi; \
    pip install --no-cache-dir --require-hashes -r requirements.lock
RUN useradd --create-home app
COPY --chown=app:app . .
USER app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--no-access-log"]
