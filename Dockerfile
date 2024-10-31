FROM python:3.9-slim-buster

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt
RUN chmod a+x /app/entrypoint.sh

EXPOSE 5001
ENTRYPOINT ["sh","/app/entrypoint.sh"]