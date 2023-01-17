from distutils.command.config import config
from flask import Flask

app = Flask(__name__)

if app.config["ENV"] == "production":
    app.config.from_object("config.ProductionConfig")
elif app.config["ENV"] == "testing":
    app.config.from_object("config.TestingConfig")
else:
    app.config.from_object("config.DevelopmentConfig")

ACCESSUSAGECOUNT_YEAR = 0 # This will be logged to see how often the REQUEST ACCESS API is used every year
FINDADMINUSAGECOUNT_YEAR = 0 # This will be logged to see how often the FIND AMIN API is used every year
ACCESSUSAGECOUNT_MONTH = 0 # This will be logged to see how often the REQUEST ACCESS API is used every month
FINDADMINUSAGECOUNT_MONTH = 0 # This will be logged to see how often the FIND AMIN API is used every month

from app import views
from app import admin_views