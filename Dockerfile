FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home angelix && mkdir -p uploads generated_reports logs && chown -R angelix:angelix /app
USER angelix
EXPOSE 8000
CMD ["gunicorn","--bind","0.0.0.0:8000","--workers","2","wsgi:app"]
