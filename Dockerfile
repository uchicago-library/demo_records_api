FROM python:3.5-alpine
COPY . /code
WORKDIR /code
RUN python setup.py install
RUN pip install gunicorn
ENV REC_API_CONFIG="/code/config.py"
ARG PORT="8910"
ENV PORT=$PORT
ARG WORKERS="4"
ENV WORKERS=$WORKERS
ARG TIMEOUT="30"
ENV TIMEOUT=$TIMEOUT
CMD gunicorn rec_api:app -w ${WORKERS} -t ${TIMEOUT} -b 0.0.0.0:${PORT}
