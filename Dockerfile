FROM python:3.12-slim

# Mencegah Python membuat berkas .pyc dan memastikan log tidak di-buffer
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Instal dependensi C library untuk WeasyPrint & ReportLab
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    shared-mime-info \
    fonts-liberation \
    fonts-dejavu-core \
    libxml2 \
    libxslt1.1 \
    git \
    curl \
    dos2unix \
    && rm -rf /var/lib/apt/lists/*

# Instal dependensi Python (Layer Caching)
COPY requirements.txt /app/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Salin source code aplikasi
COPY . /app/

# Pastikan line-ending Unix LF dan permission eksekusi untuk entrypoint
RUN dos2unix /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Buat direktori media dan staticfiles
RUN mkdir -p /app/media /app/staticfiles

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
