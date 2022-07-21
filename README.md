<img src="Docs/readme_imgs/icon.png" align="right" />
<h1>Optum eSignature Support Portal</h1>
<p>The eSignature Support Portal was built by Jacob McNeece to service UnitedHealth Group's employees with their eSignature support needs. The goal of the tool is to automate solutions for commmon service requests to the internal Optum eSignature Support Team, and give employees access to vital information and functionality in a simplified manner so that the can be self sufficient when utilizing eSignature for their business(es).</p>

<h3>API Calls Simplified</h3>
<p>Adobe Acrobat Sign has many different features and functionalities to match a user's requirements for sending out a document for signiture, but not all can be done from the browser solution. Some requires development skills and knowledge of making API calls to Adobe for fetching information or making bulk requests. With the release of the eSignature Support Portal this can all be done by a click of a button and zero development skills.</p>
<ul>This includes:
    <li>Automatting the flow of information for requesting access to Adobe Acrobat Sign using a handful of API calls.</li>
    <li>Supplying end users with the ability to find a Group Admins by entering a {group name} or {email of a colleague} whom has Acrobat Sign access.</li>
    <li>Gives end users the ability to cancel agreements sent out for signature in bulk.</li>
    <li>Supplies end users with information regarding who is the owner of a specific webform in Adobe Sign</li>
</ul>

<h3>One Stop Shop For Everything Acrobat Sign</h3>
<p>In addition to simplifying functionality for the common user, the eSignature Support Portal also is the hub for: curreated training material for novice to expert Acrobat Sign users, the fastest routes to submitting service requests to the eSignature Opperations Team, and links to the Adobe Sign tool for beginner users.</p>
    
<h1>Using The Tool</h1>
        
        SECRET_KEY = #Insert Sandbox Access Token w/ User Read Privileges
        
<h3>Step 1: Creating a config.py file</h3>
    class Config(object):
        DEBUG = False
        TESTING = False
        SECRET_KEY = # Insert PRODUCTION Access Token w: USER READ prviliges
        REQUEST_URL = # Insert Request URL for PRODUCTION Adobe Sign API
        SESSION_COOKIE_SECURE = True

    class ProductionConfig(Config):
        pass

    class DevelopmentConfig(Config):
        DEBUG = True
        SECRET_KEY = # Insert SANDBOX Access Token w: USER READ prviliges
        REQUEST_URL = # Insert Request URL for SANDBOX Adobe Sign API
        SESSION_COOKIE_SECURE = False

    class TestingConfig(Config):
        TESTING = True
        SECRET_KEY = # Insert SANDBOX Access Token w: USER READ prviliges
        REQUEST_URL = # Insert Request URL for SANDBOX Adobe Sign API
        SESSION_COOKIE_SECURE = False

<h3>Download requirements.txt</h3>
