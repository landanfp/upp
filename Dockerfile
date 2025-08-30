FROM debian:latest

ENV DEBIAN_FRONTEND=noninteractive

# نصب پکیج‌ها
RUN apt update && apt upgrade -y && \
    apt install -y git curl python3-pip python3-venv ffmpeg

# نصب NodeJS (نسخه LTS جدید)
RUN curl -sL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    npm i -g npm

# ساخت virtualenv برای پایتون
RUN python3 -m venv /venv
ENV PATH="/venv/bin:$PATH"

# نصب pip و Pyrogram نسخه مشخص
RUN pip install --upgrade pip
RUN pip install pyrogram==1.4.16

# نصب بقیه پکیج‌ها بدون آپدیت Pyrogram
COPY requirements.txt /requirements.txt
RUN pip install --no-deps -r /requirements.txt

# تنظیم دایرکتوری پروژه
WORKDIR /Uploader-Bot-V2

# کپی اسکریپت شروع
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/bin/bash", "/start.sh"]
