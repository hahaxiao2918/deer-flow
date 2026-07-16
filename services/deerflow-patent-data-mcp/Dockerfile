FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
EXPOSE 8092
CMD ["python", "-m", "deerflow_patent_data_mcp"]
