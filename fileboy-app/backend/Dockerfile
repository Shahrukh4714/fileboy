FROM python:3.12-slim

# Install system dependencies: ffmpeg for video/audio, libreoffice for documents, poppler for pdf2image
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libreoffice \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

RUN mkdir -p /tmp/fileboy/uploads /tmp/fileboy/outputs

EXPOSE 5050

CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "2", "app:app"]
