FROM python:3.12-slim-bullseye

WORKDIR /app

RUN apt-get update && \
    apt-get upgrade -y && \
    apt-get install -y python3-pip python3-numpy python3-scipy cmake ninja-build

COPY src ./src

RUN pip install --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r src/requirements.txt

CMD ["python3", "src/app.py"]