FROM python:3.11-slim
WORKDIR /app
COPY app.py . 
RUN pip install Flask
EXPOSE 5000/tcp 
CMD ["python", "app.py"]
