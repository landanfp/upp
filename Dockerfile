FROM python:3.10-slim

WORKDIR /app

# نصب ابزارهای سیستمی موردنیاز برای ساخت پکیج‌ها
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libssl-dev \
    libffi-dev \
    libjpeg-dev \
    zlib1g-dev \
    libpq-dev \
    git \
 && rm -rf /var/lib/apt/lists/*

# کپی requirements.txt
COPY requirements.txt .

# نصب کتابخانه‌های پایتون
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# کپی کل پروژه
COPY . .

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

CMD ["python", "bot.py"]
