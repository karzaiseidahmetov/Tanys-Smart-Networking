FROM python:3.12-slim
WORKDIR /app
COPY app ./app
COPY static ./static
COPY data ./data
ENV PORT=8090 HOST=0.0.0.0 PYTHONUNBUFFERED=1
EXPOSE 8090
CMD ["python", "-m", "app.server"]
