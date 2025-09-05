FROM python:3.9-slim-buster

WORKDIR /app

COPY . .

RUN pip install -r requirements.txt
RUN sed -i 's/\r$//' /app/entrypoint.sh
RUN chmod a+x /app/entrypoint.sh

EXPOSE 5006
ENTRYPOINT ["sh","/app/entrypoint.sh"]