FROM python:3.12.10-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --only-binary=:all: dlib-bin==19.24.6 \
    && pip install -r requirements.txt \
    && pip install --no-deps face-recognition==1.3.0
COPY . .

EXPOSE 10000
CMD ["sh", "-c", "gunicorn run:app --workers 1 --threads 4 --timeout 180 --bind 0.0.0.0:${PORT:-10000}"]
