import pandas as pd  # for reading csv files (domains, AD group backup file)
import json  # for capturing JSON data in Adobe API calls
import requests  # for making API call to Adobe
from app import app  # for running Flask app
from flask import render_template, request, redirect, flash #Project is built on Flask APP
from configparser import ConfigParser
# Setup Logging ------------------------------------
import datetime
from datetime import date
from datetime import timedelta
import os # For File paths
import glob # FileName Globbing Utility
import logging # Used for logging data to files

# UMAPI/Email --------------------------------------
import sys
from urllib.parse import urlencode
import whois
import urllib3
import pprint
import time
import jwt
import getpass
import functools
import operator
import smtplib
import mimetypes
from email.message import EmailMessage
#from pyad import aduser

# APP Constants for counting application usage
from app import FINDADMINUSAGECOUNT_MONTH
from app import FINDADMINUSAGECOUNT_YEAR
from app import ACCESSUSAGECOUNT_MONTH
from app import ACCESSUSAGECOUNT_YEAR


now = datetime.datetime.now() # gets current date and time
debuglogfile = now.strftime('Logs/%b %d %Y DEBUG.log') # Creates debug file
logging.basicConfig(level =logging.INFO, filename=(debuglogfile), encoding='utf-8', filemode='a',
                    format="%(asctime)s - %(levelname)s - %(message)s")

dir_name = 'Logs/' #Log file directory
# Get list of all files in the Log file directory
list_of_files = filter( os.path.isfile,
                        glob.glob(dir_name + '*'))
# Sort list of files based on last modification time in ascending order
list_of_files = sorted( list_of_files,
                        key = os.path.getmtime)
# Delete the oldest file after 15 log files have been created 
if len(list_of_files) > 15:
    os.remove(list_of_files[0])

# Suppress only the single warning from urllib3
# This code is required to disable SSL cert verification for AD Lookup API call
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# read configuration files [user management]
from configparser import RawConfigParser
acrobat_sign_config = 'acrobatsign.config'
config = RawConfigParser()
config.read(acrobat_sign_config)

# Acrobat Sign server parameters
host = config.get("acrobat_sign_server", "host")
endpoint = config.get("acrobat_sign_server", "endpoint")

# Acrobat Sign enterprise parameters
access_token = config.get("acrobat_sign_enterprise", "access_token")

# List of valid redirects
VALID_REDIRECT = ["https://esign.optum.com/request-access", "https://esignstage.optum.com/request-access", "http://127.0.0.1:5000/request-access", 
                    "https://esign.optum.com/find-admin", "https://esignstage.optum.com/find-admin", "http://127.0.0.1:5000/find-admin"]

# Start of Modules____________________________________________________________________________________
class AcrobatData(object):
    "Grouping of methods that takes a user input and checks their Acrobat Sign access as well as giving them information on potential solutions if they do not pass validation"
    # Start of Request Modules========================================================================

    def __init__(self, claimed_domains_file, users_esignatures_file):
        '''create instance and load data from local files. If emails_file is not N, this would be a cache
        claimed_domains_file (str): path to local file with claimed domains'''

        # make file paths into instance attributes
        self.users_esignatures_file = users_esignatures_file
        self.users_esignatures = None

        # using pandas to read in the csv file as a dataframe and then extract column A {domains} and put them in a list
        try:
            domains_df = pd.read_csv(claimed_domains_file)
        except Exception as e:
            logging.error('Error with opening claimed fomains File __init__')
        self.valid_domains = domains_df["Domain"].to_list() # Assigns list of domains to instance attribute valid_domains
        self.bearer_id = app.config["SECRET_KEY"] #secret key for flask project
    
    # Step 1
    def emailvalidation(self, email):
        "This function will take the users input and determine if it is a legit email (email is formatted correctly), and also run a domain check"
        # HTML already catches the appropraite email format for only one @ sign

        # If email = blank
        if email == "":
            logging.warn("def emailvalidation: No email given")
            return False, "No email given!"
        
        email = email.lower() # makes email all lower case to ensure that there is issues matching due to case sensativity.
        
        # Split username and domainname
        l = email.split("@")
        username, domainname = l[0], l[1]

        # split into subdomain and top-level domain (TLD)
        subdomain, topleveldomain = domainname.split(".")

        # is top-level domain (TLD) legit?
        if topleveldomain not in ["com", "edu", "org", "gov", "net"]:
            logging.warn("def emailvalidation: domain name must have one of the following top-level-domains: .com, .edu, .org, .gov, .net")
            return False, "domain name must have one of the following top-level-domains: .com, .edu, .org, .gov, .net"

        # is domain inside the valid_domains list (is it claimed in Adobe root console for UHG)?
        domainlist = []
        for x in self.valid_domains:
               domainlist.append(x.lower())
        if domainname in domainlist:
            logging.debug("Passed email validation")
            return True, None
        else:
            logging.warn("def emailvalidation: " + domainname + " is not a claimed domain in UHG Adobe console")
            return None, domainname

    # Step 2
    def acrobatSignAccessCheck(self, userinput):
        "This function takes an email as a parameter and runs a GET user/userByEmail API call to Acrobat Sign returning email:'example@example.com', id:'1234567',isAccountAdmin:'(True, False)'"

        # Make API call using Python requests package, Adobe v6 rest API Get /userByEmail
        url = "https://" + host + endpoint + "/users/userByEmail"

        payload = {}
        headers = {
            'x-email': userinput, # x-email retrieves user data for just that users
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=5)
        except requests.exceptions.Timeout:
            logging.warn("def actobatSignAccessCheck: The following request timed-out "+url)
            return False, "The following request timed-out"+url
        # Load JSON data into a variable
        jsondata = json.loads(response.text) #.loads converts the JSON data into a Python Dictionary
        if response.status_code == 200: # response was 200 (email was found) return True and user's ID
            
            userid = jsondata["userId"] # capture user ID for active check API and to return

            #Active check API call
            url = "https://" + host + endpoint + "/users/" + userid

            payload = {}
            headers = {
                'Authorization': "Bearer " + access_token
            }
            try:
                response = requests.get(url, headers=headers, data=payload, timeout=5)
            except requests.exceptions.Timeout:
                logging.error("def actobatSignAccessCheck: The following request timed-out "+url)
                return False, "The following request timed-out"+url
            if response.status_code == 404:
                logging.error("def actobatSignAccessCheck: " + userinput + " is in a PENDING or LOCKED statue: Adobe API error: " + userinput + " was found in UserByEmail API... userId:" + userid + " but that ID gave a 404 error in the /users/\{userID\} API")
                return None, None
            userdata = json.loads(response.text) #.loads converts the JSON data into a Python Dictionary
            status = userdata["status"]
            if status == "ACTIVE":
                logging.info("def acrobatSignAccessCheck: " + userinput + "= Active User")
                return True, userid
            else:
                logging.info("def acrobatSignAccessCheck: " + userinput + "Inactive User")
                return None, "User is not created in an \'ACTIVE\' status"

        elif response.status_code == 404: # response is 404 then user email (x-email in header of API call) does not exist in UHG's Acrobat Sign
            logging.warn("404 error in users/userByEmail: " + userinput + " does not exist in UHG's Acrobat Sign")
            return None, None
        
        else: # If response code is not 200 or 404 then log code: and error message
            logging.error("users/userByEmail Response Error:",
                  jsondata["code"], jsondata["message"])
            # Alert User in UI
            return False, "users/userByEmail Response Error: "+ str(jsondata["code"]) + ": " + jsondata["message"]

    # Step 3
    def groupCheck(self, userID):
        "This function takes the user ID and runs it in an API call that returns (groupId (string); groupName (string); createdDate (date, optional); isDefaultGroup (boolean, optional)"

        # Make API call using Python requests package
        url = "https://" + host + endpoint + "/users/" + userID +"/groups"

        payload = {}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=5)
        except requests.exceptions.Timeout:
            logging.warn("def groupCheck: The following URL timed-out " + url)
            flash("The following URL timed-out " + url, "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)
        # Load JSON data into a variable
        jsondata = json.loads(response.text) #.loads converts the JSON data into a Python Dictionary

        # If response is not 200 then unkown error stop system
        if response.status_code != 200:
            logging.warn("def groupCheck: /group Response Error:" + 
                  str(jsondata["code"]) + jsondata["message"])
            # Flash error message to UI for user
            flash("/group Response Error: " +
                  str(jsondata["code"]) + ": " + jsondata["message"], "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)

        groupinfo = jsondata["groupInfoList"]
        returnedinfo = []
        for i in groupinfo:  # For each group the user is apart of grab the name and groupid
            nameandid = (i["name"], i["id"])
            returnedinfo.append(nameandid)
        return returnedinfo

    # Step 4
    def usersInGroup(self, groupID, groupName):
        "This function takes the Group ID(s) and runs it in an API call that returns (email (string):id (string): isGroupAdmin (boolean): company (string, optional): firstName (string, optional): lastName (string, optional):"
        # This only works if our Group Sizes stay under 5k
        url = "https://" + host + endpoint + "/groups/" + groupID +"/users" + "?pageSize=5000"

        payload = {}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=5)
        except requests.exceptions.Timeout:
            logging.warn("def usersInGroup: The following URL timed-out " + url)
            flash("The following URL timed-out " + url , "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)
            
        jsondata = json.loads(response.text) #.loads converts the JSON data into a Python Dictionary
        # If response is not 200 then unkown error stop system
        if response.status_code != 200:
            logging.warn("def usersInGroup: groups/" + str(groupID) + "/users Response Error:",
                  jsondata["code"], jsondata["message"])
            # Flash error message to user in UI
            flash("groups/" + groupID + "/users Response Error: " +
                  str(jsondata["code"]) + ": " + jsondata["message"] , "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)

        # Creates a dictionary for grabing admins:
        listofadmins = {groupName: []}
        # loops through all users in the group and if they are an admin adds them to the list of admins dictionary

        for i in jsondata["userInfoList"]:
            if i["isGroupAdmin"] == True:
                listofadmins[groupName].append(i)
        return listofadmins

    # Step 5
    def activeDirectoryCheck(self, email):
        "This function checks active directory to see the user is part of the required security group in Active Directory"

        # Active Directory server parameters
        ad_host = config.get("active_directory_server", "host")
        ad_endpoint = config.get("active_directory_server", "endpoint")
        ad_token_endpoint = config.get("active_directory_server", "token_endpoint")

        # Active Directory enterprise parameters
        client_id = config.get("active_directory_enterprise", "client_id")
        client_secret = config.get("active_directory_enterprise", "client_secret")
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
            response = requests.post(url, headers=headers, data=payload, verify=False, timeout=5) #Send HTTP request to AD to get access token
            jsondata = json.loads(response.text) #.loads converts the JSON data into a Python Dictionary
        except ConnectionError as conn:
                     raise RuntimeError(f'Connot connect to AD HTTP server for Access Token - {response.status_code}')
        finally:
            logging.warn(f'AD HTTP Connection Error - {response.status_code}')

        l = email.split("@")
        username, domainname = l[0], l[1]

        url = "https://" + ad_host + ad_endpoint + \
            username+"%40"+domainname

        payload = {}
        headers = {
            'Authorization': 'Bearer '+jsondata["access_token"] #Retrieved access token from above POST HTTP reequest
        }
        response = requests.get(url, headers=headers, data=payload, verify=False, timeout=5)
        
        jsondata = json.loads(response.text) #.loads converts the JSON data into a Python Dictionary

        if response.status_code == 200:  # API success look through JSON data pull member data
            print("hello")
            
        elif response.status_code == 404: # User not found in AD
                print ("User not found, this will be updated to display a flash message that the email doesn't exist in AD")
        else:
                logging.warn(f'AD HTTP Connection Error - {response.status_code}')
                    
    def jwt_token():
        #read confg file
        config_file_name = "acrobatsign.config"
        config = RawConfigParser()
        config.read(config_file_name)

        #read parameters
        ims_host = config.get("umapi_server", "ims_host")
        ims_endpoint_jwt = config.get("umap_server", "ims_endpoint_jwt")

        org_id = config.get("umapi_enterprise", "org_id")
        tech_acct = config.get("umapi_enterprise", "tech_acct")
        api_key = config.get("umapi_enterprise", "api_key")
        client_secret = config.get("umapi_enterprise", "client_secret")
        priv_key_filename = config.get("umapi_enterprise", "priv_key_filename")
        jwt_token = config.get("umapi_enterprise", "jwt_token")

        # Set the expiration time for the JSON Web Token to one day from the current time.
        expiry_time = int(time.time())+60*60*24

        #create payload
        payload = {
            'exp' : expiry_time,
            'iss' : org_id,
            'sub' : tech_acct,
            'aud' : "https://" + ims_host + "/c/" + api_key
        }

        #define scope
        scopes = [ "ent_user_sdk" ]

        #Add Scopes
        for scope in scopes:
            payload["https://" + ims_host + "/s/" +scope]
        
        # Read the private key we will use to sign the JWT
        priv_key_file = open(priv_key_filename)
        priv_key = priv_key_file.read
        priv_key_file.close

        # Create JSON Web Token, signing it with the private key
        jwt_token = jwt.encode(payload, priv_key, algorithm='R256')

        #method parameter. The credentials are place in the boy of the POST request. the "client_id value is the API key"
        url = "https://" + ims_host + ims_endpoint_jwt
        
        headers = {
             "Content-Type" : "application/x-www-form-urlencoded",
             "Cache-Control" : "no-cache"
        }
        
        body_credentials = {
             "client_id" : api_key,
             "client_secret" : client_secret,
             "jwt_token" : jwt_token
        }

        body = urlencode(body_credentials)

        #Send HTTP request
        response = requests.post(url, headers=headers, data=body)

        #evaluate resposne
        if response.status_code == 200:
             jwt_token = json.loads(response.text)['access_token']
             AcrobatData.savejwt(jwt_token) #Save JWT to file

    def savejwt(webtoken):
        "This function saves the JWT token to a file for reusage"
        config_file_name = "count.ini" #.ini file allows us to write to the file without the sever restarting ("unlike .config files")
        
        config.set("umapi", "jwt_token", webtoken)
        config_file = open(config_file_name, "w")
        config.write(config_file)
        config_file.close

    def send_email(userinput):
        "This function will send a welcom email to newly onboarded users of Adobe Acrobat Sign"

        msg = EmailMessage()
        msg['Subject'] = 'Adobe Acrobat Sign Access Notification'
        msg['From'] = 'esignaturedtm@optum.com'
        msg['To'] = userinput
        msg['Cc'] = ''

        htmlfile = 'app/templates/client/email-inline_welcome.html'
        mime_type, _ =mimetypes.guess_type(htmlfile, strict=True)

        #Read HTML file and embed the images to the email
        with open(htmlfile, 'rb') as fp:
             img_data = fp.read()
             msg.set_content(img_data, maintype=mime_type, subtype='html')

        # Send the email via our own SMTP server
        s = smtplib.SMTP('mailo2.uhc.com')
        s.send_message(msg)
        s.quit
# end of Request Modules===========================================================================================================

# Start of Find Admin Modules++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
    def creategrouplist(self):
        "this function creates a list of groups in Adobe Acrobat Sign"
        
        url = "https://" + host + endpoint + "/groups" + "?pageSize=750"

        payload = {}
        headers = {
            'Authorization': "Bearer " + access_token
        }
        try:
            response = requests.get(url, headers=headers, data=payload, timeout=5)
       
        except requests.exceptions.Timeout:
            logging.warn("def creategrouplist: The following URL timed-out " + url)
            flash("def creategrouplist: The following URL timed-out " + url , "alert")
            if request.url in VALID_REDIRECT:
                return redirect(request.url)

        if response.status_code != 200:
            logging.warn("def grouplist: " + host + endpoint + "/groups Response Error:",
                    str(jsondata["code"]) + jsondata["message"])
            # Alert UI with error
            return False, host + endpoint + "/groups Response Error: " + jsondata["code"] + ": " + jsondata["message"]
        
        jsondata = json.loads(response.text) #.loads converts the JSON data into a Python Dictionary

        counter = 0
        grouplist=[]
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
            response = requests.get(url, headers=headers, data=payload, timeout=5)
        except requests.exceptions.Timeout:
            logging.warn("The following URL timed-out " + url)
            return False, "The following URL timed-out " + url
        jsondata = json.loads(response.text) #.loads converts the JSON data into a Python Dictionary

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
    # End of Find Admin Modules++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# End of modules __________________________________________________________________________________________________________________________________________________


@app.route("/")
def home():
    logging.debug('-----------------------    HOME PAGE     --------------------------------')
    "This is the home page containing information and links to Adobe Acrobat Sign, most of this code is in the index.html file"
    return render_template("client/index.html")
# End Home Page____________________________________________________________________________________________________________________________________________________


@app.route("/request-access", methods=["GET", "POST"])
def signcheck():
    logging.debug('-----------------------    REQUEST ACCESS PAGE    --------------------------------')
    "This webpage is for running the Adobe Acrobat Sign Access Check for Users"
    # make a instance (object) of the class and use instance methods from now on
    ad = AcrobatData(claimed_domains_file="data_files/claimed_domains.csv",
                     users_esignatures_file="data_files/dtm_esignature_users.csv")
    
    #Read config file for writting globals to config
    config_object = ConfigParser()
    config_object.read("count.ini")
    global ACCESSUSAGECOUNT_MONTH
    global ACCESSUSAGECOUNT_YEAR
    if request.method == "POST":
        
        # The following code with for logging ACCESSS
        today = date.today()
        yesterday = today - timedelta(days = 1)
        todayyear = today.strftime('%Y')
        yesterdayyear = yesterday.strftime('%Y')
        todaymonth = today.strftime('%b')
        yesterdaymonth = yesterday.strftime('%b')
        if todaymonth != yesterdaymonth:
            ACCESSUSAGECOUNT_MONTH = 1
            #Get the USAGE COUNT from config
            count = config_object["usage_count"]

            #Update the month usage count
            count["request_month"] = str(ACCESSUSAGECOUNT_MONTH)
            #Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        else:
            ACCESSUSAGECOUNT_MONTH += 1 # Access check used
            logging.info("Current REQUEST ACCESS API Usage for the Month of " + todaymonth + ": is " + str(ACCESSUSAGECOUNT_MONTH))

            #Get the USAGE COUNT from config
            count = config_object["usage_count"]

            #Update the month usage count
            count["request_month"] = str(ACCESSUSAGECOUNT_MONTH)
            #Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        
        if todayyear != yesterdayyear:
            ACCESSUSAGECOUNT_YEAR = 1
            #Get the USAGE COUNT from config
            count = config_object["usage_count"]

            #Update the year usage count
            count["request_year"] = str(ACCESSUSAGECOUNT_YEAR)
            #Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        else:
            ACCESSUSAGECOUNT_YEAR += 1 # Access check used
            logging.info("Current REQUEST ACCESS API Usage YTD: " + str(ACCESSUSAGECOUNT_YEAR))
            #Get the USAGE COUNT from config
            count = config_object["usage_count"]

            #Update the YEAR usage count
            count["request_year"] = str(ACCESSUSAGECOUNT_YEAR)
            #Write changes back to file
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
                # Step 3 Failed: User is in Default Group
                # User is part of default group (needs to get added to a group)
                if len(groups) == 1 and group == "Default Group":
                    logging.warn("User " + userinput + " is in the Default Group")
                    flash(userinput, "default_group")
                    if request.url in VALID_REDIRECT:
                                return redirect(request.url)
                # Step 3 Passed: User is in a group and active
                else:
                    logging.debug(userinput + ": Passed Access Check!")
                    flash(userinput, "access_success")
                    if request.url in VALID_REDIRECT:
                                return redirect(request.url)
            elif result is None: #This is where we need to create a fed ID and assign that user to dtm_esignature group in the adobe console 
                # Step 4: Create Federated ID in the console with dtm_esignature group assignment (this has product entitlement to Adobe Sign Prod/SB)
                result, firstname, lastname, location = ad.activeDirectoryCheck(userinput) # This is going to verify if the email is legit and return the first and sur names
                
                if result == True: # This means the user exist in AD but does not have access
                    print("Code needed")
                   
                    if request.url in VALID_REDIRECT:
                                return redirect(request.url)
                # Step 4 Failed: User is not in the required security group
                elif result == None: # This means the user was not found in AD 404
                    print("Code Needed")
                else: # This means there was an error in AD and the code didnt run properly have notify the user to open a ticket
                    
                    flash(userinput, "adFail")
                    if request.url in VALID_REDIRECT:
                                return redirect(request.url)
            else:  # Error API call GET /user/userByEmail
                logging.warn(userinput + "had an error with the API call GET /users/userByEmail OR is not an 'Active' user in Adobe Acrobat Sign")
                flash(userId_message, "alert")
                if request.url in VALID_REDIRECT:
                                return redirect(request.url)
        # Step 1 Failed: users domain is not claimed in the UHG console
        elif bool is None:
            logging.warn(userinput + "failed domain check")
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
# End Request Page____________________________________________________________________________________________________________________________________________________


@app.route("/find-admin", methods=["GET", "POST"])
def findadmin():
    "This webpage is for users who don't know who their admin is"
    logging.debug('-----------------------    FIND ADMIN PAGE    --------------------------------')

    # make a instance (object) of the class and use instance methods from now on
    ad = AcrobatData(claimed_domains_file="data_files/claimed_domains.csv",  # This file stores all claimed domains
                     # This file stores all AD users in the dtm_esignature security group
                     users_esignatures_file="data_files/dtm_esignature_users.csv")
    grouplist, count = ad.creategrouplist() #This creates a group list that will be used to populate the search dropdown and validate the user input
    logging.info(f'We have {count} groups')
    admindict = {}  # Empty Dictionary that will be used to merge multiple Admin Dictionaries together
    
    config_object = ConfigParser()
    config_object.read("count.ini")
    global FINDADMINUSAGECOUNT_MONTH #Declare the global to use for Year count
    global FINDADMINUSAGECOUNT_YEAR # Declare the gloval to user for Month count

    if request.method == "POST":
        
        today = date.today() # Get todays date
        yesterday = today - timedelta(days = 1) # Get yesterdays date
        todayyear = today.strftime('%Y') # Get the year for today
        yesterdayyear = yesterday.strftime('%Y') # Get the year for yesterday
        todaymonth = today.strftime('%b')
        yesterdaymonth = yesterday.strftime('%b')
        if todaymonth != yesterdaymonth:
            FINDADMINUSAGECOUNT_MONTH = 1
            #Get the USAGE COUNT from config
            count = config_object["usage_count"]

            #Update the month usage count
            count["admin_month"] = str(FINDADMINUSAGECOUNT_MONTH)
            #Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        else:
            FINDADMINUSAGECOUNT_MONTH += 1
            logging.info("Current FIND ADMIN API Usage for the Month of " + todaymonth + ": is " + str(FINDADMINUSAGECOUNT_MONTH))
            #Get the USAGE COUNT from config
            count = config_object["usage_count"]

            #Update the month usage count
            count["admin_month"] = str(FINDADMINUSAGECOUNT_MONTH)
            #Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        if todayyear != yesterdayyear:
            FINDADMINUSAGECOUNT_YEAR = 1
            #Get the USAGE COUNT from config
            count = config_object["usage_count"]

            #Update the month usage count
            count["admin_year"] = str(FINDADMINUSAGECOUNT_YEAR)
            #Write changes back to file
            with open('count.ini', 'w') as conf:
                config_object.write(conf)
        else:
            FINDADMINUSAGECOUNT_YEAR += 1
            logging.info("Current FIND ADMIN API Usage YTD: " + str(FINDADMINUSAGECOUNT_YEAR))

            #Get the USAGE COUNT from config
            count = config_object["usage_count"]

            #Update the month usage count
            count["admin_year"] = str(FINDADMINUSAGECOUNT_YEAR)
            #Write changes back to file
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
                            logging.warn("User (" + email + ") in Default Group")
                            flash(email, "default_group")
                            if request.url in VALID_REDIRECT:
                                return redirect(request.url)
                        # Step 3 Passed: User is in a group and active
                        else:
                            # Create a dictionary of admin and render it to the HTML file
                            for i in groupnameandid:  # For each group and id in the list merge the admins from that group to a dictionary
                                # using the group ID, this call runs an API call to capture all users in that group and creates a list of admins to return
                                admindict = admindict | ad.usersInGroup(i[1], i[0])
                            logging.info("Group Lookup using EMAIL (" + email + "): Success")
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
                if group in grouplist: # user provided value is validated for security
                    result, groupid = ad.grouplist(group)
                    if result == True:
                        if groupid != "":
                            # using the group ID, this call runs an API call to capture all users in that group and creates a dictionary of admins to return
                            admindict = ad.usersInGroup(groupid, group)
                            if len(admindict[group]) != 0:
                                logging.info("Group Lookup (" + group + "): Success")
                                alert = "<div align=\"left\" class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\">Admin's Found!</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p class=\"ms-4\">Please contact one of the following admins to get added to your group, or make changes to your group settings.</p><ul>"
                                return render_template("client/admin_lookup.html", alert=alert, admindict=admindict, grouplist=grouplist)
                            else:
                                logging.warn("Group (" + group + "): No Admin For this group")
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