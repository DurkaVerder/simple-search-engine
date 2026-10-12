FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY import_docs.py posts.csv ./

CMD ["python", "import_docs.py", "/app/posts.csv"]
