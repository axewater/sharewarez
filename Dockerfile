FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install -r requirements.txt
RUN sed -i 's/\r$//' /app/entrypoint.sh
RUN sed -i 's/\r$//' /app/startweb-docker.sh
RUN chmod a+x /app/entrypoint.sh
RUN chmod a+x /app/startweb-docker.sh

EXPOSE 5006
ENTRYPOINT ["/bin/bash","/app/entrypoint.sh"]