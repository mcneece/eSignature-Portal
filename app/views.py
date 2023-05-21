#**************************************************
# Views.py is the core code base for running the backend of the flask application
# Script checks user access, creates users in the Adobe Console and in Adobe Sign, and helps users find Admins
#**************************************************

##########
# Import application modules and classes
##########
from configparser import RawConfigParser
from urllib3.exceptions import InsecureRequestWarning
import pandas as pd  # for reading csv files (domains, AD group backup file)
import json  # for capturing JSON data in Adobe API calls
import requests  # for making API call to Adobe
from app import app  # for running Flask app
from requests import packages # For all API calls
import urllib3 # for Active Directory API calls
from flask import render_template, request, redirect, flash
from configparser import ConfigParser # for reading in values from config and .ini files
import datetime # for KPIs and Logging
from datetime import date # for KPIs and Logging
from datetime import timedelta # for KPIs and Logging
import os  # For File paths
import glob  # FileName Globbing Utility
import logging  # for logging data to files
from urllib.parse import urlencode # for UMAPI encoding JWT
import time # for KPIs and Logging
import jwt # for UMAPI jwt
import smtplib # for email method to send automated emails
import mimetypes # for email method to send automated emails
from email.message import EmailMessage # for email method to send automated emails

########### 
# Global Varibles used as KPIs, writes in the count.ini file how often the application is being used each Month and Year
###########
from app import FINDADMINUSAGECOUNT_MONTH
from app import FINDADMINUSAGECOUNT_YEAR
from app import ACCESSUSAGECOUNT_MONTH
from app import ACCESSUSAGECOUNT_YEAR

##########
#  Create Log Files for Debugging
##########
now = datetime.datetime.now()  # gets current date and time
debuglogfile = now.strftime('Logs/%b %d %Y DEBUG.log') # Creates log file for the day if it doesn't already exist
logging.basicConfig(level=logging.INFO, filename=(debuglogfile), encoding='utf-8', filemode='a',
                    format="%(asctime)s - %(levelname)s - %(message)s")  # Set configurations for logging
dir_name = 'Logs/'  # Log file directory
list_of_files = filter(os.path.isfile, glob.glob(dir_name + '*'))
list_of_files = sorted(list_of_files, key=os.path.getmtime) # Sort list of files based on last modification time in ascending order
if len(list_of_files) > 15:
    os.remove(list_of_files[0]) # Delete the oldest file after 15 log files have been created

##########
# Disable SSL cert verification for AD Lookup API call (suppress the warning from urllib3)
##########
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning) # supresses "InsecureRequestWarning: Unverified HTTPS request is being made to host"

##########
#  Read Configuration Files and assing variables
#########
acrobat_sign_config = 'acrobatsign.config'
config = RawConfigParser()
config.read(acrobat_sign_config)

host = config.get("acrobat_sign_server", "host")
endpoint = config.get("acrobat_sign_server", "endpoint")
access_token = config.get("acrobat_sign_enterprise", "access_token")
jwt_config = 'count.ini'
config.read(jwt_config)
token = config.get("umapi", "jwt_token")

##########
#  Set valid URL redirects to ensure redirects back to web application after executing a task only go to our verified web URLS
#########
VALID_REDIRECT = ["https://esign.optum.com/request-access", "https://esignstage.optum.com/request-access", "http://127.0.0.1:5000/request-access",
                  "https://esign.optum.com/find-admin", "https://esignstage.optum.com/find-admin", "http://127.0.0.1:5000/find-admin"] #  List of valid redirects

###########
# Custom Modules for Flask Application (class eSignature)
###########
class eSignature(object):
    "Grouping of methods that takes a user input and checks their Acrobat Sign access as well as giving them information on potential solutions if they do not pass validation"
    # Start of Request Modules========================================================================

    def __init__(self, claimed_domains_file):
        '''claimed_domains_file (str): path to local file with claimed domains'''

        # using pandas to read in the csv file as a dataframe and then extract column A {domains} and put them in a list
        try:
            domains_df = pd.read_csv(claimed_domains_file)
        except Exception as e:
            logging.error('Error with opening claimed fomains File __init__')
        # Assigns list of domains to instance attribute valid_domains
        self.valid_domains = domains_df["Domain"].to_list()
        # secret key for flask project
        self.bearer_id = app.config["SECRET_KEY"]


    def emailvalidation(self, email):
        '''Takes email input and determines if it is a legit email and also runs a  claimed domain check'''
        
        # Input catches the appropraite email format for only one @ sign

        if email == "": # no value was given for email
            logging.warn("def emailvalidation: No email given")
            return False, "No email given!"

        email = email.lower() # makes email all lower case to ensure that there is issues matching due to case sensativity.
        l = email.split("@")   # Split username and domainname
        username, domainname = l[0], l[1] # grab domain value
        subdomain, topleveldomain = domainname.split(".")  # split into subdomain and top-level domain (TLD)

        if topleveldomain not in ["com", "edu", "org", "gov", "net"]: # is top-level domain (TLD) legit?
            logging.warn(
                "def emailvalidation: domain name must have one of the following top-level-domains: .com, .edu, .org, .gov, .net")
            return False, "domain name must have one of the following top-level-domains: .com, .edu, .org, .gov, .net"

        domainlist = []
        for x in self.valid_domains:  # is domain inside the valid_domains list (is it claimed in Adobe root console for UHG)?
            domainlist.append(x.lower())
        if domainname in domainlist:
            logging.debug("Passed email validation")
            return True, None
        else:
            logging.warn("def emailvalidation: " + domainname +
                         " is not a claimed domain in UHG Adobe console")
            return None, domainname


    def acrobatSignAccessCheck(self, userinput):
        '''Takes email perameter and makes an API call to Adobe to check if users has Adobe Sign access'''

        url = "https://" + host + endpoint + "/users/userByEmail" # Request URL for userByEmail

        payload = {}
        headers = {
            'x-email': userinput,  # x-email retrieves user data for just that users
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(
                url, headers=headers, data=payload, timeout=5)
        except requests.exceptions.Timeout:
            logging.warn(
                "def actobatSignAccessCheck: The following request timed-out " + url)
            return False, "The following request timed-out" + url
        # Load JSON data into a variable
        # .loads converts the JSON data into a Python Dictionary
        jsondata = json.loads(response.text)
        # response was 200 (email was found) return True and user's ID
        if response.status_code == 200:

            # capture user ID for active check API and to return
            userid = jsondata["userId"]

            # API call to Adobe: USERS/{USERID}
            url = "https://" + host + endpoint + "/users/" + userid

            payload = {}
            headers = {
                'Authorization': "Bearer " + access_token
            }
            try:
                response = requests.get(
                    url, headers=headers, data=payload, timeout=5)
            except requests.exceptions.Timeout:
                logging.error(
                    "def actobatSignAccessCheck: The following request timed-out " + url)
                return False, "The following request timed-out" + url
            if response.status_code == 404:
                logging.error("def actobatSignAccessCheck: " + userinput + " is in a PENDING or LOCKED statue: Adobe API error: " + userinput +
                              " was found in UserByEmail API... userId:" + userid + " but that ID gave a 404 error in the /users/\{userID\} API")
                return None, None
            
            userdata = json.loads(response.text) # .loads converts the JSON data into a Python Dictionary
            # Check if the users status is Active
            status = userdata["status"]
            if status == "ACTIVE":
                logging.info("def acrobatSignAccessCheck: " +
                             userinput + " = Active User")
                return True, userid
            else:
                logging.info("def acrobatSignAccessCheck: " +
                             userinput + " = Inactive User")
                return None, "User is not created in an \'ACTIVE\' status"

        # response is 404 then user email (x-email in header of API call) does not exist in UHG's Acrobat Sign
        elif response.status_code == 404:
            logging.warn("404 error in users/userByEmail: " +
                         userinput + " does not exist in UHG's Acrobat Sign")
            return None, None

        else:  # If response code is not 200 or 404 then log code: and error message
            logging.error("users/userByEmail Response Error:",
                          jsondata["code"], jsondata["message"])
            # Alert User in UI
            return False, "users/userByEmail Response Error: " + str(jsondata["code"]) + ": " + jsondata["message"]


    def groupCheck(self, userID):
        "This function takes the user ID and runs it in an API call that returns (groupId (string); groupName (string); createdDate (date, optional); isDefaultGroup (boolean, optional)"

        # API call to Adobe: USER/{USERID}/GROUPS
        url = "https://" + host + endpoint + "/users/" + userID + "/groups"

        payload = {}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(
                url, headers=headers, data=payload, timeout=5)
        except requests.exceptions.Timeout:
            logging.warn("def groupCheck: The following URL timed-out " + url)
            flash("The following URL timed-out " + url, "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)
        # Load JSON data into a variable
        # .loads converts the JSON data into a Python Dictionary
        jsondata = json.loads(response.text)

        # If response is not 200 then unkown error stop system
        if response.status_code != 200:
            logging.warn("def groupCheck: /group Response Error:" +
                         str(jsondata["code"]) + jsondata["message"])
            # Flash error message to UI for user
            flash("/group Response Error: " +
                  str(jsondata["code"]) + ": " + jsondata["message"], "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)
        # Get user groups and Ids for a specific user
        groupinfo = jsondata["groupInfoList"]
        returnedinfo = []
        for i in groupinfo:  # For each group the user is apart of grab the name and groupid
            nameandid = (i["name"], i["id"])
            returnedinfo.append(nameandid)
        return returnedinfo


    def usersInGroup(self, groupID, groupName):
        "This function takes the Group ID(s) and runs it in an API call that returns (email (string):id (string): isGroupAdmin (boolean): company (string, optional): firstName (string, optional): lastName (string, optional):"
        # API call to Adobe: GROUPS/{GROUPID}/USERS
        # # # This only works if our Group Sizes stay under 5k
        url = "https://" + host + endpoint + "/groups/" + \
            groupID + "/users" + "?pageSize=5000"

        payload = {}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(
                url, headers=headers, data=payload, timeout=5)
        except requests.exceptions.Timeout:
            logging.warn(
                "def usersInGroup: The following URL timed-out " + url)
            flash("The following URL timed-out " + url, "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)

        jsondata = json.loads(response.text) # .loads converts the JSON data into a Python Dictionary
        # If response is not 200 then unkown error stop system
        if response.status_code != 200:
            logging.warn("def usersInGroup: groups/" + str(groupID) + "/users Response Error:",
                         jsondata["code"], jsondata["message"])
            # Flash error message to user in UI
            flash("groups/" + groupID + "/users Response Error: " +
                  str(jsondata["code"]) + ": " + jsondata["message"], "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)

        # Creates a dictionary of only Group Admins:
        listofadmins = {groupName: []}
        # loops through all users in the group and if they are an admin adds them to the list of admins dictionary

        for i in jsondata["userInfoList"]:
            if i["isGroupAdmin"] == True:
                listofadmins[groupName].append(i)
        return listofadmins


    def activeDirectoryCheck(self, email):
        "This function checks active directory to see the user is part of the required security group in Active Directory"
        acrobat_sign_config = 'acrobatsign.config'
        config = RawConfigParser()
        config.read(acrobat_sign_config)
        # Active Directory server parameters
        ad_host = config.get("active_directory_server", "host")
        ad_endpoint = config.get("active_directory_server", "endpoint")
        ad_token_endpoint = config.get(
            "active_directory_server", "token_endpoint")

        # Active Directory enterprise parameters
        client_id = config.get("active_directory_enterprise", "client_id")
        client_secret = config.get(
            "active_directory_enterprise", "client_secret")
        grant_type = config.get("active_directory_enterprise", "grant_type")

        # API AD Lookup
        url = "https://" + ad_host + ad_token_endpoint

        payload = json.dumps({
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": grant_type
        })

        headers = {
            'Content-Type': 'application/json'
        }
        try:
            # Send HTTP request to AD to get access token
            response = requests.post(
                url, headers=headers, data=payload, verify=False, timeout=5)
            # .loads converts the JSON data into a Python Dictionary
            jsondata = json.loads(response.text)
        except requests.exceptions.Timeout:
            logging.warn(
                "def usersInGroup: The following URL timed-out " + url)
            flash("The following URL timed-out " + url, "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)
        except ConnectionError as conn:
            raise RuntimeError(
                f'Connot connect to AD HTTP server for Access Token - {response.status_code}')

        l = email.split("@")
        username, domainname = l[0], l[1]

        url = "https://" + ad_host + ad_endpoint + \
            username+"%40"+domainname

        payload = {}
        headers = {
            # Retrieved access token from above POST HTTP reequest
            'Authorization': 'Bearer '+jsondata["access_token"]
        }
        response = requests.get(url, headers=headers,
                                data=payload, verify=False, timeout=5)

        # .loads converts the JSON data into a Python Dictionary
        jsondata = json.loads(response.text)

        if response.status_code == 200:  # API success look through JSON data pull member data
            user = jsondata['resource']['user']

            user_fname = user['firstName']
            user_lname = user['lastName']
            return True, user_fname, user_lname

        elif response.status_code == 404:  # User not found in AD
            print("User not found in Active Directory")
            return None, None, None
        else:
            logging.warn(f'AD HTTP Connection Error - {response.status_code}')
            return False, None, None


    def jwt_token():
        # read confg file
        config_file_name = "acrobatsign.config"
        config = RawConfigParser()
        config.read(config_file_name)

        # read server parameters
        ims_host = config.get("umapi_server", "ims_host")
        ims_endpoint_jwt = config.get("umapi_server", "ims_endpoint_jwt")

        org_id = config.get("umapi_enterprise", "org_id")
        tech_acct = config.get("umapi_enterprise", "tech_acct")
        api_key = config.get("umapi_enterprise", "api_key")
        client_secret = config.get("umapi_enterprise", "client_secret")
        priv_key_filename = config.get("umapi_enterprise", "priv_key_filename")

        # read jwt and exired time parameters
        config_file_name = "count.ini"
        config = RawConfigParser()
        config.read(config_file_name)

        expired_time = config.get("umapi", "expired_time")
        jwt_token = (config.get("umapi", "jwt_token"))

        now = int(time.time())
        if now >= int(expired_time):
            # Set the expiration time for the JSON Web Token to one day from the current time.
            expiry_time = int(time.time())+60*60*24

            # create payload
            payload = {
                'exp': expiry_time,
                'iss': org_id,
                'sub': tech_acct,
                'aud': "https://" + ims_host + "/c/" + api_key
            }

            # define scope
            scopes = ["ent_user_sdk"]

            # Add Scopes
            for scope in scopes:
                payload["https://" + ims_host + "/s/" + scope] = True

            # Read the private key we will use to sign the JWT
            priv_key_file = open(priv_key_filename)
            priv_key = priv_key_file.read()
            priv_key_file.close()

            # Create JSON Web Token, signing it with the private key
            jwt_token = jwt.encode(payload, priv_key, algorithm='RS256')

            # method parameter. The credentials are place in the boy of the POST request. the "client_id value is the API key"
            url = "https://" + ims_host + ims_endpoint_jwt

            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Cache-Control": "no-cache"
            }

            body_credentials = {
                "client_id": api_key,
                "client_secret": client_secret,
                "jwt_token": jwt_token
            }

            body = urlencode(body_credentials)

            # Send HTTP request
            response = requests.post(
                url, headers=headers, data=body, timeout=5)

            # evaluate resposne
            if response.status_code == 200:
                jwt_token = json.loads(response.text)['access_token']
                eSignature.savejwt(jwt_token, expiry_time)
                return jwt_token
        else:
            return jwt_token


    def savejwt(webtoken, expired_time):
        "This function saves the JWT token and expiration of token to a file for reusage until it expires"
        # .ini file allows us to write to the file without the sever restarting ("unlike .config files")
        config_file_name = "count.ini"

        config.set("umapi", "jwt_token", webtoken)
        config.set("umapi", "expired_time", expired_time)
        config_file = open(config_file_name, "w")
        config.write(config_file)
        config_file.close
        return


    def createUser(self, email, fName, lName):
        "This function creates a federated ID in UHG's Adobe Sign console with group assignment to dtm_esignature"
        config_file_name = "acrobatsign.config"
        config = RawConfigParser()
        config.read(config_file_name)

        # read parameters
        host = config.get("umapi_server", "host")
        endpoint = config.get("umapi_server", "endpoint")
        org_id = config.get("umapi_enterprise", "org_id")
        api_key = config.get("umapi_enterprise", "api_key")

        token = str(eSignature.jwt_token())

        url = "https://" + host + endpoint + "/action/" + org_id
        headers = {
            "Content-type": "application/json",
            "Accept": "application/json",
            "x-api-key": api_key,
            "Authorization": "Bearer " + token
        }

        json_data = \
            [{
                "user": email,
                "requestID": "action_1",
                "do": [
                    {
                        "createFederatedID": {
                            "email": email,
                            "firstname": fName,
                            "lastname": lName,
                            # If the user exist in the console it will not create another user
                            "option": "ignoreIfAlreadyExists"
                        }
                    },
                    {
                        "add": {
                            "group": [
                                "dtm_esignature"
                            ]
                        }
                    }
                ]
            }]

        # Prepare Body
        body = json.dumps(json_data)

        res = requests.post(url, headers=headers, data=body)
        if res.status_code == 200: 
            return True, res.status_code, email + " was created in the Adobe Console"
        else:
            return False, res.status_code, email + " was NOT created in the Adobe Console"


    def send_email(self, email):
        "This function will send a welcom email to newly onboarded users of Adobe Acrobat Sign"
        msg = EmailMessage()
        msg['Subject'] = 'Adobe Acrobat Sign Access Notification'
        msg['From'] = 'esignaturedtm@optum.com'
        msg['To'] = email
        msg['Cc'] = ''

        htmlfile = 'app/templates/client/email-inline_welcome.html'
        mime_type, _ = mimetypes.guess_type(htmlfile, strict=True)

        # Read HTML file and embed the images to the email
        with open(htmlfile, 'rb') as fp:
            img_data = fp.read()
            msg.set_content(img_data, maintype=mime_type, subtype='html')

        # Send the email via our own SMTP server
        s = smtplib.SMTP('mailo2.uhc.com')
        s.send_message(msg)
        s.quit
        return


    def creategrouplist(self):
        "this function creates a list of groups in Adobe Acrobat Sign"

        url = "https://" + host + endpoint + "/groups" + "?pageSize=750"

        payload = {}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(
                url, headers=headers, data=payload, timeout=5)

        except requests.exceptions.Timeout:
            logging.warn(
                "def creategrouplist: The following URL timed-out " + url)
            flash("def creategrouplist: The following URL timed-out " + url, "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)

        if response.status_code != 200:
            logging.warn("def grouplist: " + host + endpoint + "/groups Response Error:",
                         str(jsondata["code"]) + jsondata["message"])
            # Alert UI with error
            return False, host + endpoint + "/groups Response Error: " + jsondata["code"] + ": " + jsondata["message"]

        # .loads converts the JSON data into a Python Dictionary
        jsondata = json.loads(response.text)

        counter = 0
        grouplist = []
        for each in jsondata["groupInfoList"]:
            grouplist.append(each["groupName"])
            counter += 1
        return grouplist, counter

    def grouplist(self, groupName):
        "Using group Name get group ID"
        url = "https://" + host + endpoint + "/groups" + "?pageSize=750"

        payload = {}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(
                url, headers=headers, data=payload, timeout=5)
        except requests.exceptions.Timeout:
            logging.warn("The following URL timed-out " + url)
            return False, "The following URL timed-out " + url
        # .loads converts the JSON data into a Python Dictionary
        jsondata = json.loads(response.text)

        if response.status_code != 200:
            logging.warn("def grouplist: " + host + endpoint + "/groups Response Error:",
                         jsondata["code"], jsondata["message"])
            # Alert UI with error
            return False, host + endpoint + "/groups Response Error: " + str(jsondata["code"]) + ": " + jsondata["message"]

        groupID = ""

        for i in jsondata["groupInfoList"]:
            if groupName.lower() == i["groupName"].lower():
                groupID = i["groupId"]
        return True, groupID


#**************************************************
# Home Page
#**************************************************
@app.route("/")
def home():
    logging.debug(
        '-----------------------    HOME PAGE     --------------------------------')
    "This is the home page containing information and links to Adobe Acrobat Sign, most of this code is in the index.html file"
    return render_template("client/index.html")

#*****************************************
# Request Access Page
#*****************************************
@app.route("/request-access", methods=["GET", "POST"])
def requestaccess():
    logging.debug(
        '-----------------------    REQUEST ACCESS PAGE    --------------------------------')
    "This webpage is for running the Adobe Acrobat Sign Access Check for Users"
    # make a instance (object) of the class and use instance methods from now on
    ad = eSignature(claimed_domains_file="data_files/claimed_domains.csv",
                     users_esignatures_file="data_files/dtm_esignature_users.csv")

    # Read config file for writting globals to config
    config_object = ConfigParser()
    config_object.read("count.ini")
    global ACCESSUSAGECOUNT_MONTH
    global ACCESSUSAGECOUNT_YEAR
    if request.method == "POST":

        # The following code with for logging ACCESSS
        today = date.today()
        yesterday = today - timedelta(days=1)
        todayyear = today.strftime('%Y')
        yesterdayyear = yesterday.strftime('%Y')
        todaymonth = today.strftime('%b')
        yesterdaymonth = yesterday.strftime('%b')
        if todaymonth != yesterdaymonth:
            ACCESSUSAGECOUNT_MONTH = 1
            # Get the USAGE COUNT from config
            count = config_object["usage_count"]

            # Update the month usage count
            count["request_month"] = str(ACCESSUSAGECOUNT_MONTH)
            # Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        else:
            ACCESSUSAGECOUNT_MONTH += 1  # Access check used
            logging.info("Current REQUEST ACCESS API Usage for the Month of " +
                         todaymonth + ": is " + str(ACCESSUSAGECOUNT_MONTH))

            # Get the USAGE COUNT from config
            count = config_object["usage_count"]

            # Update the month usage count
            count["request_month"] = str(ACCESSUSAGECOUNT_MONTH)
            # Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)

        if todayyear != yesterdayyear:
            ACCESSUSAGECOUNT_YEAR = 1
            # Get the USAGE COUNT from config
            count = config_object["usage_count"]

            # Update the year usage count
            count["request_year"] = str(ACCESSUSAGECOUNT_YEAR)
            # Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        else:
            ACCESSUSAGECOUNT_YEAR += 1  # Access check used
            logging.info("Current REQUEST ACCESS API Usage YTD: " +
                         str(ACCESSUSAGECOUNT_YEAR))
            # Get the USAGE COUNT from config
            count = config_object["usage_count"]

            # Update the YEAR usage count
            count["request_year"] = str(ACCESSUSAGECOUNT_YEAR)
            # Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)

        userinput = request.form["useremail"]
        logging.debug("Running Access Check", userinput)
        # Step 1: Email Validation, this check will verify if the user input is a valid email
        # Bool is True if all email validation passed otherwise false, if True message = None, if False message has error for Flask Flash
        bool, message = ad.emailvalidation(userinput)
        if bool == True:  # Runs email through function that checks if it is formatted correctly, if so returns True, if not returns error message
            # Step 2: Adobe Acrobat Sign Access Check, this check will look through a list of users in Adobe sign that are active and validate if the user input email is part of that list
            # Returns True and user ID if their is a match, returns False and an error message if API call issue, return False and None if the email wasn't found
            result, userId_message = ad.acrobatSignAccessCheck(userinput)
            # Step 2 Passed: Adobe Acrobat Sign Access Check, user has an Adobe Acrobat Sign Account
            if result == True:
                # Step 3: Run a group check on the user that passed Adobe Acrobat Sign Access Check
                # using the user ID, return the group (name, Id) that they are apart of
                groupnameandid = ad.groupCheck(userId_message)
                groups = []
                for i in groupnameandid:
                    group = str(i[0])
                    groups.append(group)
                # Step 3 Failed: User is in Default Group in Adobe Sign
                if len(groups) == 1 and group == "Default Group":
                    logging.warn("User " + userinput +
                                 " is in the Default Group")
                    flash(userinput, "default_group")
                    if request.url in VALID_REDIRECT:
                        return redirect(request.url)
                # Step 3 Passed: User is in a group in Adobe Sign and they have an 'active' account
                else:
                    logging.debug(userinput + ": Passed Access Check!")
                    flash(userinput, "access_success")
                    if request.url in VALID_REDIRECT:
                        return redirect(request.url)
            elif result is None:  # User does not have an Adobe Sign account
                # Step 4: Validate they are a existing employee in Active Directory (returns first and last name)
                result, fName_code, lName_message = ad.activeDirectoryCheck(
                    userinput)
                if result == True:  # This means the user exist in AD but does not have access, Create Federated ID
                    result, code, message = ad.createUser(
                        userinput, fName_code, lName_message)
                    if result == True:  # Users was successfully created
                        logging.info(
                            "Federated ID succesfully created for" + userinput)
                        # Sends a welcome email to the user
                        ad.send_email(userinput)
                        logging.debug("Welcome email sent" + userinput)
                        flash(userinput, "access_granted")
                        if request.url in VALID_REDIRECT:
                            return redirect(request.url)
                    elif result == False and code == 404:
                        logging.info(
                            "The following user already exist" + userinput)
                        flash(userinput, "umapi_exist")
                        if request.url in VALID_REDIRECT:
                            return redirect(request.url)
                    else:
                        logging.error("The following error occurd with UMAPI API: " +
                                      str(code) + ": " + message + " for " + userinput)
                        flash(userinput, "adFail")
                        if request.url in VALID_REDIRECT:
                            return redirect(request.url)
                elif result == None:  # Email not found in Active Directory
                    logging.info("The following user email (" + userinput +
                                 ") was not found in UHG's Active Directory")
                    flash(userinput, "ad_notfound")
                    if request.url in VALID_REDIRECT:
                        return redirect(request.url)
                else:  # Error w/ Active Directory API notifing the user to open a ticket
                    logging.error("The following error occurd with AD API: " +
                                  fName_code + ": " + lName_message + "for " + userinput)
                    flash(userinput, "adFail")
                    if request.url in VALID_REDIRECT:
                        return redirect(request.url)
            else:  # Error API call GET /user/userByEmail
                logging.warn(
                    userinput + "had an error with the API call GET /users/userByEmail OR is not an 'Active' user in Adobe Acrobat Sign")
                flash(userId_message, "alert")
                if request.url in VALID_REDIRECT:
                    return redirect(request.url)
        # Step 1 Failed: users domain is not claimed in the UHG console
        elif bool is None:
            logging.warn(userinput + " failed domain check")
            flash(message, "domain_fail")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)
        # Step 1 Failed: User inputed email in a invalid format
        else:
            logging.debug(userinput + "Invalid email format")
            flash(message, "email")
            # Redirection from remote source (validate user input)
            if request.url in VALID_REDIRECT:
                return redirect(request.url)
    # Loads Orign HTML Template for Webpage
    return render_template("client/request_access.html")

#********************************************
# Find Admin Page
#********************************************
@app.route("/find-admin", methods=["GET", "POST"])
def findadmin():
    "This webpage is for users who don't know who their admin is"
    logging.debug(
        '-----------------------    FIND ADMIN PAGE    --------------------------------')

    # make a instance (object) of the class and use instance methods from now on
    ad = eSignature(claimed_domains_file="data_files/claimed_domains.csv",  # This file stores all claimed domains
                     # This file stores all AD users in the dtm_esignature security group
                     users_esignatures_file="data_files/dtm_esignature_users.csv")
    # This creates a group list that will be used to populate the search dropdown and validate the user input
    grouplist, count = ad.creategrouplist()
    logging.info(f'We have {count} groups')
    admindict = {}  # Empty Dictionary that will be used to merge multiple Admin Dictionaries together

    config_object = ConfigParser()
    config_object.read("count.ini")
    global FINDADMINUSAGECOUNT_MONTH  # Declare the global to use for Year count
    global FINDADMINUSAGECOUNT_YEAR  # Declare the gloval to user for Month count

    if request.method == "POST":

        today = date.today()  # Get todays date
        yesterday = today - timedelta(days=1)  # Get yesterdays date
        todayyear = today.strftime('%Y')  # Get the year for today
        yesterdayyear = yesterday.strftime('%Y')  # Get the year for yesterday
        todaymonth = today.strftime('%b')
        yesterdaymonth = yesterday.strftime('%b')
        if todaymonth != yesterdaymonth:
            FINDADMINUSAGECOUNT_MONTH = 1
            # Get the USAGE COUNT from config
            count = config_object["usage_count"]

            # Update the month usage count
            count["admin_month"] = str(FINDADMINUSAGECOUNT_MONTH)
            # Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        else:
            FINDADMINUSAGECOUNT_MONTH += 1
            logging.info("Current FIND ADMIN API Usage for the Month of " +
                         todaymonth + ": is " + str(FINDADMINUSAGECOUNT_MONTH))
            # Get the USAGE COUNT from config
            count = config_object["usage_count"]

            # Update the month usage count
            count["admin_month"] = str(FINDADMINUSAGECOUNT_MONTH)
            # Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        if todayyear != yesterdayyear:
            FINDADMINUSAGECOUNT_YEAR = 1
            # Get the USAGE COUNT from config
            count = config_object["usage_count"]

            # Update the month usage count
            count["admin_year"] = str(FINDADMINUSAGECOUNT_YEAR)
            # Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        else:
            FINDADMINUSAGECOUNT_YEAR += 1
            logging.info("Current FIND ADMIN API Usage YTD: " +
                         str(FINDADMINUSAGECOUNT_YEAR))

            # Get the USAGE COUNT from config
            count = config_object["usage_count"]

            # Update the month usage count
            count["admin_year"] = str(FINDADMINUSAGECOUNT_YEAR)
            # Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)

        email = str(request.form["email"])
        group = str(request.form["group"])
        # If the user input something
        if email or group != "":
            # If the user submited information in the email search run email search code:
            if len(email) > len(group):
                # Step 1: Email Validation, this check will verify if the user input is a valid email
                bool, message = ad.emailvalidation(email)
                if bool == True:  # Runs email through function that checks if it is formatted correctly, if so returns True, if not returns error message
                    # Step 2: Adobe Acrobat Sign Access Check, this check will look through a list of users in Adobe sign that are active and validate if the user input email is part of that list
                    # Returns True and user ID if their is a match, returns false if their isn't a match
                    result, userId = ad.acrobatSignAccessCheck(email)
                    # Step 2 Passed: Adobe Acrobat Sign Access Check, user has an Adobe Acrobat Sign Account
                    if result == True:
                        # Step 3: Run a group check on the user that passed Adobe Acrobat Sign Access Check
                        # using the user ID, return the group (name, Id) that they are apart of
                        groupnameandid = ad.groupCheck(userId)
                        groups = []
                        for i in groupnameandid:
                            group = str(i[0])
                            groups.append(group)
                        # Step 3 Failed: User is in Default Group
                        if len(groups) == 1 and group == "Default Group":
                            logging.warn(
                                "User (" + email + ") in Default Group")
                            flash(email, "default_group")
                            if request.url in VALID_REDIRECT:
                                return redirect(request.url)
                        # Step 3 Passed: User is in a group and active
                        else:
                            # Create a dictionary of admin and render it to the HTML file
                            for i in groupnameandid:  # For each group and id in the list merge the admins from that group to a dictionary
                                # using the group ID, this call runs an API call to capture all users in that group and creates a list of admins to return
                                admindict = admindict | ad.usersInGroup(
                                    i[1], i[0])
                            logging.info(
                                "Group Lookup using EMAIL (" + email + "): Success")
                            alert = "<div align=\"left\" class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Admin's Found!</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>Please contact one of the following admins to get added to your group:</p><ul>"
                            return render_template("client/admin_lookup.html", alert=alert, admindict=admindict, grouplist=grouplist)
                    # Step 1 Failed: User does not have an Acrobat Sign Account
                    else:
                        logging.info("Email (" + email + "): No Account Found")
                        flash(email, "emailNotFound")
                        if request.url in VALID_REDIRECT:
                            return redirect(request.url)
                # Step 1 Failed: users domain is not claimed in the UHG console
                elif bool is None:
                    alert = "<div align=\"left\" class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Unclaimed Domain</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following domain <strong>" + \
                        message+"</strong> is not a claimed domain in UHG's Adobe Console.</p><p class=\"mb-1\">Currently only users with claimed domains can be provisioned in Adobe Acrobat Sign, because of this <strong>" + \
                            email+"</strong> does not have an active account in Adobe Acrobat Sign.</p></div>"
                    logging.warn(email + "failed due to Unclaimed Domain")
                    return render_template("client/admin_lookup.html", alert=alert, grouplist=grouplist)
                else:
                    logging.warn(email + "Invalid email format: " + message)
                    flash(message, "email")
                    if request.url in VALID_REDIRECT:
                        return redirect(request.url)
            else:
                if group in grouplist:  # user provided value is validated for security
                    result, groupid = ad.grouplist(group)
                    if result == True:
                        if groupid != "":
                            # using the group ID, this call runs an API call to capture all users in that group and creates a dictionary of admins to return
                            admindict = ad.usersInGroup(groupid, group)
                            if len(admindict[group]) != 0:
                                logging.info(
                                    "Group Lookup (" + group + "): Success")
                                alert = "<div align=\"left\" class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\">Admin's Found!</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p class=\"ms-4\">Please contact one of the following admins to get added to your group, or make changes to your group settings.</p><ul>"
                                return render_template("client/admin_lookup.html", alert=alert, admindict=admindict, grouplist=grouplist)
                            else:
                                logging.warn(
                                    "Group (" + group + "): No Admin For this group")
                                flash(group, "noAdmin")
                                if request.url in VALID_REDIRECT:
                                    return redirect(request.url)
                        else:
                            flash(group, "groupNotFound")
                            logging.warn(group + ": group was not found")
                            if request.url in VALID_REDIRECT:
                                return redirect(request.url)
                    else:
                        flash(groupid, "alert")
                        logging.error(groupid + ": error")
                        if request.url in VALID_REDIRECT:
                            return redirect(request.url)
    return render_template("client/admin_lookup.html", grouplist=grouplist)
# End Find Admin Page_________________________________________________________________________________________________________________________________________________


@app.route("/open-ticket")
def openticket():
    "This is the weppage users will visit to open one of the following tickets (Incident, Net New, Enhancement)"
    return render_template("client/openticket.html")


@app.route("/admin")
def admin():
    "This is the beginning of our admin page which may grow to something more"
    return render_template("admin/admin.html")


@app.route("/testing")
def testing():
    "This is our automated test scripts page which is used for releases or testing with groups"
    return render_template("admin/automated_testing.html")
