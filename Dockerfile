FROM python:3.9-slim-buster

WORKDIR /app
COPY ./requirements.txt /app
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5001
RUN chmod a+x /app/entrypoint.sh

ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.7.3/wait /wait
RUN chmod +x /wait

ENTRYPOINT ["/app/entrypoint.sh"]

