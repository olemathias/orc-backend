###########
# App Build #
###########

# pull official base image
FROM python:3.10-alpine as builder

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install psycopg2 dependencies
RUN apk update \
    && apk add postgresql-dev libpq python3-dev gcc libc-dev libffi-dev musl-dev git

# install dependencies
COPY ./requirements.txt .
RUN pip wheel --no-cache-dir --no-deps --wheel-dir /usr/src/app/wheels -r requirements.txt

#########
# FINAL App #
#########

# pull official base image
FROM python:3.10-alpine as app

# create directory for the app user
RUN mkdir -p /home/app

# create the app user
RUN addgroup -S app && adduser -S app -G app

# create the appropriate directories
ENV HOME=/home/app
ENV APP_HOME=/home/app/web
RUN mkdir $APP_HOME
RUN mkdir $APP_HOME/staticfiles
RUN mkdir $APP_HOME/mediafiles
WORKDIR $APP_HOME

# install dependencies
RUN apk update && apk add postgresql-dev libpq python3-dev gcc libc-dev libffi-dev musl-dev git

COPY --from=builder /usr/src/app/wheels /wheels
COPY --from=builder /usr/src/app/requirements.txt .
RUN pip install --no-cache /wheels/*

# copy entrypoint.sh
COPY ./entrypoint.sh .
RUN sed -i 's/\r$//g'  $APP_HOME/entrypoint.sh
RUN chmod +x  $APP_HOME/entrypoint.sh

# copy project
COPY . $APP_HOME

# chown all the files to the app user
RUN chown -R app:app $APP_HOME

# change to the app user
USER app

# run entrypoint.prod.sh
ENTRYPOINT ["/home/app/web/entrypoint.sh"]
CMD ["gunicorn", "orc.wsgi:application", "--bind", "0.0.0.0:8000"]

#########
# Static Build #
#########

FROM app as static-build
WORKDIR /home/app/web/
RUN python manage.py collectstatic

#########
# FINAL Static #
#########

FROM nginx:latest as static
COPY --from=static-build /home/app/web/static/ /usr/share/nginx/html/