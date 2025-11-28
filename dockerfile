FROM python:3.11-slim

# ---------------------------
# 🔧 Corrige problemas de encoding (UTF-8)
# ---------------------------
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8

WORKDIR /app


RUN apt-get update && apt-get install -y \
    firebird-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "app.py"]
