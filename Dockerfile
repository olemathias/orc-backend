FROM python:3
ENV PYTHONUNBUFFERED=1
WORKDIR /opt/orc
COPY . /opt/orc/
# TODO Check what we need here
RUN apt-get install build-essential libldap2-dev libsasl2-dev slapd ldap-utils tox lcov valgrind
RUN pip install -r requirements.txt
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
