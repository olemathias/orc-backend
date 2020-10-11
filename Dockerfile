FROM python:3
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/orc
COPY . /opt/orc/
RUN pip install -r requirements.txt
