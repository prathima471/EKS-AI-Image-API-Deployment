# Use official Python base image
FROM python:3.11-slim

# Create non-root user (security best practice!)
RUN groupadd -r appuser && useradd -r -g appuser -d /app -s /sbin/nologin appuser

# set working directory
WORKDIR /app

# copy dependency file and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# copy application code
COPY . .

RUN chown -R appuser:appuser /app

USER appuser

# expose port the app will run on
EXPOSE 8000

# default command to run the API
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]