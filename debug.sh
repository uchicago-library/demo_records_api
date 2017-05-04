#!/bin/sh

APP_SAVE=$FLASK_APP
export FLASK_APP=rec_api
python -m flask run
export FLASK_APP=$APP_SAVE
