FROM python:3.12-slim
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY backend ./backend
COPY data ./data
COPY frontend/dist ./frontend/dist
RUN useradd --uid 10001 --create-home copilot
USER 10001
EXPOSE 8080
CMD ["python", "-m", "uvicorn", "copilot.api:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8080"]
