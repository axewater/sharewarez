FROM python:3.9-slim-buster

WORKDIR /app
COPY ./requirements.txt /app
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5001
ENV FLASK_APP=app.py
ENV DATABASE_URL='postgresql://sharewarez:!Piratingin2024!@db/sharewarez'
RUN python docker_adduser.py

#CMD ["flask", "run", "--host", "0.0.0.0"]
#CMD ["bash", "-c", "while true; do sleep 3600; done"]
