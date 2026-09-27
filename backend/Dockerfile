# Single-stage on purpose.
#
# The backend is a Python application served by uvicorn, not a compiled
# artefact, so there is nothing for a second stage to copy. A multi-stage build
# here would add a layer without shrinking the image.
#
# 3.11 rather than the 3.9 used for local development: the code is written to
# 3.9 syntax and the test suite passes on 3.9, so 3.11 is a supported target
# and is still maintained, while 3.9 reached end of life. See
# architecture.md 9 for the one difference this can cause.
FROM python:3.11-slim

# Prevent .pyc files from being written into the image, and from being
# generated at all in a container that may be running as a non-root user with
# no write access to the app directory.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Dependencies in their own layer, so editing application code does not
# invalidate the install and trigger a full reinstall on every rebuild.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

# The SQLite file, the Chroma collection and uploaded originals all live under
# one directory so a single volume mount covers every piece of state. Created
# and owned up front: SQLite and Chroma both need to create files here, and
# they fail obscurely at the first request if the directory is not writable.
RUN mkdir -p /app/data/chroma /app/data/uploads \
    && adduser --system --group --no-create-home app \
    && chown -R app:app /app

USER app

EXPOSE 8000

# Readiness, not liveness: this reports on the Chroma client and the database,
# so an unhealthy result here means queries will fail, which is the thing a
# demo actually depends on.
#
# Uses the stdlib rather than curl, which is not present in the slim image and
# would otherwise mean adding a package purely to hold a health check.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["python", "-c", "import sys,urllib.request;\
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/ready',timeout=4).status==200 else 1)"]

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
