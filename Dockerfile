FROM python:3.13.1

# 필요한 패키지 설치
RUN apt-get clean && apt-get update && apt-get install -y \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# 작업 디렉토리를 설정합니다.
WORKDIR /app


# 가상 환경을 생성하고 활성화하여 필요한 Python 패키지들을 설치합니다.
RUN pip install --upgrade pip
RUN pip install fastapi pandas python-dotenv beautifulsoup4 google-generativeai google-ai-generativelanguage==0.6.10 google-api-core==2.24.0 google-api-python-client==2.159.0 requests geopy uvicorn pillow python-multipart


ARG API_KEY

RUN echo "API_KEY=$API_KEY" > /app/.env

COPY . .

# Flask 애플리케이션을 실행하는 명령어
CMD ["uvicorn", "FastAPIServer:app", "--host", "0.0.0.0", "--port", "7052"]
