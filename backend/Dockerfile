FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

ENV HF_HOME=/models

# Torch is installed on its own so that editing requirements.txt does not
# fetch a few hundred megabytes of it again.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
CMD ["web"]
