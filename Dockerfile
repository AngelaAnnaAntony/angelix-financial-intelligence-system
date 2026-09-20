FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends \
build-essential \
libpq-dev \
tesseract-ocr \
tesseract-ocr-eng \
&& rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd --create-home angelix \
&& mkdir -p uploads generated_reports logs \
&& chown -R angelix:angelix /app
USER angelix
EXPOSE 10000
CMD ["sh","-c","flask --app run:app db upgrade && gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 wsgi:app"]
