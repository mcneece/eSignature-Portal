# The config.py file is created to seperate

class Config(object):
    DEBUG = False
    TESTING = False
    # To make this more secure i could use the Secrets Python module or OS.random
    SECRET_KEY = "Bearer 3AAABLblqZhAPwYiPVI4CvpLOD1e6ejO2Uvk6IznySUXDhjL9mNyG30C4tSJB3B9S7ZvOqJ01NaG_mejfWKBrVA5O4VxfpB1a" #Production Key
    REQUEST_URL_USERS = "https://api.na3.adobesign.com/api/rest/v6/users/userByEmail"
    REQUEST_URL_GROUPS = "https://api.na3.adobesign.com/api/rest/v6/groups" 
    SESSION_COOKIE_SECURE = True
class ProductionConfig(Config):
    pass

class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = "Bearer 3AAABcnMhu1CzoStSwXHRIlky3NlORac_SApc3F3qEIuZ-bSsB_9veCr56HJR5WSRbX37tLRXyTt1mHoCqDwl7OXG0ug9sLBH" #Sandbox Key
    REQUEST_URL_USERS = "https://api.na1.adobesignsandbox.com/api/rest/v6/users/userByEmail"
    REQUEST_URL_GROUPS = "https://api.na1.adobesignsandbox.com/api/rest/v6/groups" 
    SESSION_COOKIE_SECURE = False

class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "Bearer 3AAABcnMhu1CzoStSwXHRIlky3NlORac_SApc3F3qEIuZ-bSsB_9veCr56HJR5WSRbX37tLRXyTt1mHoCqDwl7OXG0ug9sLBH" #Sandbox Key
    REQUEST_URL_USERS = "https://api.na1.adobesignsandbox.com/api/rest/v6/users/userByEmail"
    REQUEST_URL_GROUPS = "https://api.na1.adobesignsandbox.com/api/rest/v6/groups" 
    SESSION_COOKIE_SECURE = False