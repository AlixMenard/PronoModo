FROM python:3.13-alpine
WORKDIR /app

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["fastapi", "run"]
