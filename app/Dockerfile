FROM python:3.11-slim
WORKDIR /app
COPY ./app.py /app/app.py
RUN pip install --no-cache-dir flask gunicorn
ENV PORT=80
EXPOSE 80
CMD ["gunicorn", "--bind", "0.0.0.0:80", "app:app"]
