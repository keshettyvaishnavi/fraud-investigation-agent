FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONPATH=/app/src
RUN python -m fraud_agent.data
EXPOSE 8000
CMD ["uvicorn", "fraud_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
