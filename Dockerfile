FROM python:3.9-slim-buster

WORKDIR /app

RUN apt-get update -y
RUN apt-get install netcat -y

#COPY ./requirements.txt /app
#COPY ./entrypoint.sh /app/
COPY . .

RUN pip install -r requirements.txt
EXPOSE 5001
RUN chmod a+x /app/entrypoint.sh

ADD https://github.com/ufoscout/docker-compose-wait/releases/download/2.7.3/wait /wait
RUN chmod +x /wait

RUN ls -l /app

ENTRYPOINT ["sh","/app/entrypoint.sh"]

