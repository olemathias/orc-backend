FROM python:3
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/orc
COPY . /opt/orc/
RUN apt-get install libsasl2-dev python-dev libldap2-dev libssl-dev
RUN pip install -r requirements.txt
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
