from distutils.command.config import config
from configparser import RawConfigParser
acrobat_sign_config = 'acrobatsign.config'
count_config = 'count.config'
config = RawConfigParser()
config.read(acrobat_sign_config)
config.read(count_config)

from flask import Flask

app = Flask(__name__)

if app.config["ENV"] == "production":
    app.config.from_object("config.ProductionConfig")
elif app.config["ENV"] == "testing":
    app.config.from_object("config.TestingConfig")
else:
    app.config.from_object("config.DevelopmentConfig")

ACCESSUSAGECOUNT_YEAR = int(config.get("usage_count", "request_year")) # This will be logged to see how often the REQUEST ACCESS API is used every year
FINDADMINUSAGECOUNT_YEAR = int(config.get("usage_count", "admin_year")) # This will be logged to see how often the FIND AMIN API is used every year
ACCESSUSAGECOUNT_MONTH = int(config.get("usage_count", "request_year")) # This will be logged to see how often the REQUEST ACCESS API is used every month
FINDADMINUSAGECOUNT_MONTH = int(config.get("usage_count", "admin_month")) # This will be logged to see how often the FIND AMIN API is used every month

from app import views
from app import admin_views