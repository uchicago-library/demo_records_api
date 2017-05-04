from flask import Flask
from .blueprint import BLUEPRINT

app = Flask(__name__)

app.config.from_envvar("REC_API_CONFIG", silent=True)

app.register_blueprint(BLUEPRINT)
