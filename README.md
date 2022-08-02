<img src="Docs/readme_imgs/icon.png" align="right" />

# Optum eSignature Support Portal

<p>The eSignature Support Portal was built by Jacob McNeece to service UnitedHealth Group's employees with their eSignature support needs. The goal of the tool is to automate solutions for common service requests to the internal Optum eSignature Support Team, and give employees access to vital information and functionality in a simplified manner so that they can be self sufficient when utilizing eSignature for their business(es).</p>

### API Calls Simplified

<p>Adobe Acrobat Sign has many different features and functionalities to match a user's requirements for sending out a document for signiture, but not all can be done from the browser solution. Some requires development skills and knowledge of making API calls to Adobe for fetching information or making bulk requests. With the release of the eSignature Support Portal this can all be done by a click of a button and zero development skills.</p>
<ul>This includes:
    <li>Automatting the flow of information for requesting access to Adobe Acrobat Sign using a handful of API calls.</li>
    <li>Supplying end users with the ability to find a Group Admins by entering a {group name} or {email of a colleague} whom has Acrobat Sign access.</li>
    <li>Gives end users the ability to cancel agreements sent out for signature in bulk. {coming soon]</li>
    <li>Supplies end users with information regarding who is the owner of a specific webform in Adobe Sign {coming soon}</li>
</ul>

### One Stop Shop For Everything Acrobat Sign

<p>In addition to simplifying functionality for the common user, the eSignature Support Portal also is the hub for: curreated training material userful for novice to expert Acrobat Sign users, the fastest routes to submitting service requests or incidents to the eSignature Opperations Team, and links to the Adobe Sign tool.</p>

<img src="Docs/readme_imgs/home_page.png" align="center" />
    
## Installation
        
<h3>Step 1: Creating a config.py file</h3>
<p>Save this file in the app directory of this project<p>
 
```python
    class Config(object):
        DEBUG = False
        TESTING = False
        # To make this more secure i could use the Secrets Python module or OS.random
        SECRET_KEY = # Insert PRODUCTION Access Token w: USER READ prviliges
        REQUEST_URL_USERS = # Insert Request URL for PRODUCITON Adobe Sign API
        REQUEST_URL_GROUPS = # Insert Request URL for PRODUCTION Adobe Sign API
        SESSION_COOKIE_SECURE = True

    class ProductionConfig(Config):
        pass

    class DevelopmentConfig(Config):
        DEBUG = True
        SECRET_KEY = # Insert SANDBOX Access Token w: USER READ prviliges
        REQUEST_URL_USERS = # Insert Request URL for SANDBOX Adobe Sign API
        REQUEST_URL_GROUPS = # Insert Request URL for SANDBOX Adobe Sign API 
        SESSION_COOKIE_SECURE = False

    class TestingConfig(Config):
        TESTING = True
        SECRET_KEY = # Insert SANDBOX Access Token w: USER READ prviliges
        REQUEST_URL_USERS = # Insert Request URL for SANDBOX Adobe Sign API
        REQUEST_URL_GROUPS = # Insert Request URL for SANDBOX Adobe Sign API
        SESSION_COOKIE_SECURE = False
```
    
<h3>Step 2: Download requirements.txt</h3>

```console
    pip install -r requirements.txt
```
<h3>Step 3: Run Commands in Termainal to Run Flask Project</h3>

```console
    source env/bin/activate
```
```console
    export FLASK_APP=run.py
```
```console
    export FLASK_ENV=production
```
```console
    flask run
```
<p>Select the link provided in the terminal<p>

```console
    Running on http://127.0.0.1:5000
```

## Using the Tool

