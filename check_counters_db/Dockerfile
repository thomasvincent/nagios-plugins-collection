FROM python:3.14.0a3-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python", "vertigo_status_checker.py"]
