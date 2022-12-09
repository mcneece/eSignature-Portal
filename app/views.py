import pandas as pd  # for reading csv files (domains, AD group backup file)
import json  # for capturing JSON data in Adobe API calls
import requests  # for making API call to Adobe
from app import app  # for running Flask app
# for running python Flask app
from flask import render_template, request, redirect, flash

# Setup Logging For Debugging
import datetime
now = datetime.datetime.now()
debuglogfile = now.strftime('Logs/%b %d %Y DEBUG.log')
infologfile = now.strftime('Logs/%b %d %Y INFO.log')
import logging
logging.basicConfig(filename=(debuglogfile), encoding='utf-8', level=logging.DEBUG)
# Logic to delete log files after 2 days
import os
files = os.listdir("Logs")
if len(files) > 3:
    os.remove('Logs/'+files[1])

# Suppress only the single warning from urllib3 needed.
# This code is required to disable SSL cert verification for AD Lookup API call
from urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

                                                                                                                                                                                                                                                                                                                                                                                                                       
# Start of Modules____________________________________________________________________________________
class AcrobatData(object):
    "Grouping of methods that takes a user input and checks their Acrobat Sign access as well as giving them information on potential solutions if they do not pass validation"
    # Start of Request Modules========================================================================

    def __init__(self, claimed_domains_file, users_esignatures_file, cached=False):
        '''create instance and load data from local files. If emails_file is not N, this would be a cache
        claimed_domains_file (str): path to local file with claimed domains'''

        # make file paths into instance attributes
        self.users_esignatures_file = users_esignatures_file
        self.users_esignatures = None
        self.bearer_id = None
        self.groups = None

        # using pandas to read in the csv file as a dataframe and then extract each column I need as a list
        try:
            domains_df = pd.read_csv(claimed_domains_file)
        except Exception as e:
            logging.error('Error with opening claimed fomains File __init__')
            flash("Error with opening "+claimed_domains_file+" "+e, "alert")
            # Redirection from remote source (validate user input to reduce phising attempts)
            return redirect(request.url)

        self.valid_domains = domains_df["Domain"].to_list()

        # set bearer ID and URL from config file
        self.bearer_id = app.config["SECRET_KEY"]

    # Step 1
    def emailvalidation(self, email):
        "This function will take the users input and determine if it is a legit email (email is formatted correctly), and also run a domain check"
        # HTML already catches the appropraite email format for only one @ sign

        # If email = blank
        if email == "":
            return False, "No email given!"

        # Split username and domainname
        l = email.split("@")
        username, domainname = l[0], l[1]

        # how many dots in domain name?
        if domainname.count(".") != 1:
            return False, "domain-name must have exactly one '.'!"

        # split into subdomain and top-level domain (TLD)
        subdomain, topleveldomain = domainname.split(".")

        # is top-level domain (TLD) legit?
        if topleveldomain not in ["com", "edu", "org", "gov", "net"]:
            return False, "domain name must have one of the following top-level-domains: .com, .edu, .org, .gov, .net"

        # is domain inside the valid_domains list (is it claimed in Adobe root console for UHG)?
        if domainname in self.valid_domains:
            return True, None
        else:
            return None, domainname

    # Step 2
    def acrobatSignAccessCheck(self, userinput):
        "This function takes an email as a parameter and runs a GET user/userByEmail API call to Acrobat Sign returning email:'example@example.com', id:'1234567',isAccountAdmin:'(True, False)'"

        # Make API call using Python requests package, Adobe v6 rest API Get /userByEmail
        url = app.config["REQUEST_URL_USERS"]+"/userByEmail"

        payload = {}
        headers = {
            # email is required in the header to only retrieve data for that specific email
            'x-email': userinput,
            'Authorization': self.bearer_id
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        # Load JSON data into a variable
        jsondata = json.loads(response.text)

        # If response is 404 then user email (x-email in header of API call) does not exist in UHG's Acrobat Sign
        if response.status_code == 404:
            logging.debug("404 error in users/userByEmail: User email does not exist in UHG's Acrobat Sign")
            return None, None
        # If response is not 404 and still not 200 then log code: and message
        elif response.status_code != 200:
            logging.warn("users/userByEmail Response Error:",
                  jsondata["code"], jsondata["message"])
            # Alert User in UI
            return False, "users/userByEmail Response Error: "+jsondata["code"]+": "+jsondata["message"], "alert"
        # response was 200 (email was found) return True and user's ID
        userid = jsondata["userId"]

        # Make API call using Python requests package, Adobe v6 rest API GET USER/{USERID}
        url = app.config["REQUEST_URL_USERS"]+"/"+userid

        payload = {}
        headers = {
            'Authorization': self.bearer_id
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        jsondata = json.loads(response.text)
        status = jsondata["status"]
        if status == "ACTIVE":
            logging.debug("Active User")
            return True, userid
        else:
            logging.debug("Inactive User")
            return False, "User is not created in an \'ACTIVE\' status"

    # Step 3
    def groupCheck(self, userID):
        "This function takes the user ID and runs it in an API call that returns (groupId (string); groupName (string); createdDate (date, optional); isDefaultGroup (boolean, optional)"

        # Make API call using Python requests package
        url = app.config["REQUEST_URL_USERS"]+"/"+userID+"/groups"

        payload = {}
        headers = {
            'Authorization': self.bearer_id
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        # Load JSON data into a variable
        jsondata = json.loads(response.text)

        # If response is not 200 then unkown error stop system
        if response.status_code != 200:
            logging.warn("users/userByEmail Response Error:",
                  jsondata["code"], jsondata["message"])
            # Flash error message to UI for user
            flash("users/userByEmail Response Error: " +
                  jsondata["code"]+": "+jsondata["message"], "alert")
            # Redirection from remote source (validate user input to reduce phising attempts)
            target = request.url
            if target == request.url:
                return redirect(target)

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
        url = app.config["REQUEST_URL_GROUPS"] + \
            "/"+groupID+"/users?pageSize=5000"

        payload = {}
        headers = {
            'Authorization': self.bearer_id
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        jsondata = json.loads(response.text)
        # If response is not 200 then unkown error stop system
        if response.status_code != 200:
            logging.warn("groups/"+groupID+"/users Response Error:",
                  jsondata["code"], jsondata["message"])
            # Flash error message to user in UI
            flash("groups/"+groupID+"/users Response Error: " +
                  jsondata["code"]+": "+jsondata["message"], "alert")
            
            # Redirection from remote source (validate user input to reduce phising attempts)
            target = request.url
            if target == request.url:
                return redirect(target)

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
        # API AD Lookup
        url = app.config["AD_REQUEST_URL_GETTOKEN"]

        payload = json.dumps({
            "client_id": app.config["CLIENTID"],
            "client_secret": app.config["CLIENTSECRET"],
            "grant_type": "client_credentials"
        })

        headers = {
            'Content-Type': 'application/json'
        }
        try:
            response = requests.request(
                "POST", url, headers=headers, data=payload, verify=False)
            jsondata = json.loads(response.text)

            if response.status_code == 200:

                l = email.split("@")
                username, domainname = l[0], l[1]

                url = app.config["AD_REQUEST_URL_USERDETAILS"] + \
                    username+"%40"+domainname

                payload = {}
                headers = {
                    'Authorization': 'Bearer '+jsondata["access_token"]
                }

                response = requests.request(
                    "GET", url, headers=headers, data=payload, verify=False)

                jsondata = json.loads(response.text)

                if response.status_code == 200:  # API success look through JSON data for group membership
                    temp = jsondata['resource']
                    temp2 = temp['user']

                    for each in temp2["memberOf"]:
                        if each["name"] == "dtm_esignature":
                            logging.debug('Used AD API, dtm_esignature found for '+email)
                            return True
                    logging.debug('Used AD API, dtm_esiganture not found for'+email)
                    return False
                elif response.status_code == 404:
                    logging.debug('Used AD API, email ('+email+') not found in active directory')
                    return False
        except Exception as fail:
            logging.warn('Did not use AD API')
        
        # If API call fails run backup CSV file
        # Backup CSV file AD Lookup
            try:
                df = pd.read_csv(self.users_esignatures_file)
            except Exception as e:
                logging.warn("Error reading users Active Directory (dtm_esignature) file")
                flash("Error reading users Active Directory (dtm_esignature) file", "alert")
                # Redirection from remote source (validate user input to reduce phising attempts)
                target = request.url
                if target == request.url:
                    return redirect(target)
            logging.debug("Ran Backup CSV file")
            self.users_esignatures = df["Mail"].to_list()

            # Run through row in the csv file and check the email against the csv file of users in the dtm_esignature security group
            if email in self.users_esignatures:
                logging.debug('Used backup CSV file, Pass')
                return True
            else:
                logging.debug('Used backup CSV file, Fail')
                return False

    def creategrouplist(self):
        "this function creates a list of groups in Adobe Acrobat Sign"
        
        url = app.config["REQUEST_URL_GROUPS"]+"?pageSize=750"

        payload = {}
        headers = {
            'Authorization': self.bearer_id
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        jsondata = json.loads(response.text)

        counter = 0
        grouplist=[]
        for each in jsondata["groupInfoList"]:
            grouplist.append(each["groupName"])
            counter += 1
        logging.debug(str(counter)+' groups in account')
        return grouplist
# end of Request Modules===========================================================================================================
# Start of Find Admin Modules++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++


    def grouplist(self, groupName):
        url = app.config["REQUEST_URL_GROUPS"]+"?pageSize=500"

        payload = {}
        headers = {
            'Authorization': self.bearer_id
            }
        response = requests.request("GET", url, headers=headers, data=payload)
        jsondata = json.loads(response.text)

        if response.status_code != 200:
            logging.warn("users/userByEmail Response Error:",
                    jsondata["code"], jsondata["message"])
            # Alert UI with error
            return False, "users/userByEmail Response Error: "+jsondata["code"]+": "+jsondata["message"]

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
                     users_esignatures_file="data_files/dtm_esignature_users.csv",
                     cached=True)  # will use this value later on when I implement powershell script for AD lookup

    if request.method == "POST":
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
                    logging.debug("User in Default Group")
                    flash(userinput, "default_group")
                    return redirect(request.url)
                # Step 3 Passed: User is in a group and active
                else:
                    logging.debug("Passed Access Check")
                    flash(userinput, "access_success")
                    return redirect(request.url)
            elif result is None:
                result = ad.activeDirectoryCheck(userinput)
                # Step 4: Check Security Group (dtm_esignature)
                # Step 4 passed: user is in the correct security group
                if result == True:
                    logging.debug("Failed: Uknown Failure")
                    flash(userinput, "unknown")
                    return redirect(request.url)
                # Step 4 Failed: User is not in the required security group
                else:
                    logging.debug("Not in AD Group")
                    flash(userinput, "adFail")
                    return redirect(request.url)
            else:  # Error API call GET /user/userByEmail
                logging.warn("Error with API call GET /users/userByEmail or error with 'Active' user status")
                flash(userId_message, "alert")
                return redirect(request.url)
        # Step 1 Failed: users domain is not claimed in the UHG console
        elif bool is None:
            logging.warn("Failed domain check")
            flash(message, "domain_fail")
            return redirect(request.url)
        # Step 1 Failed: User inputed email in a invalid format
        else:
            logging.debug("Invalid email format")
            flash(message, "email")
            # Redirection from remote source (validate user input to reduce phising attempts)
            target = request.url
            if target == request.url:
                return redirect(target)
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
                     users_esignatures_file="data_files/dtm_esignature_users.csv",
                     cached=True)  # will use this value later on when I implement powershell script for AD lookup
    grouplist = ad.creategrouplist() #This creates a group list that will be used to populate the search dropdown
    admindict = {}  # Empty Dictionary that will be used to merge multiple Admin Dictionaries together

    if request.method == "POST":
        email = request.form["email"]
        group = request.form["group"]
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
                            logging.debug("User ("+email+") in Default Group")
                            flash(email, "default_group")
                            return redirect(request.url)
                        # Step 3 Passed: User is in a group and active
                        else:
                            # Create a dictionary of admin and render it to the HTML file
                            for i in groupnameandid:  # For each group and id in the list merge the admins from that group to a dictionary
                                # using the group ID, this call runs an API call to capture all users in that group and creates a list of admins to return
                                admindict = admindict | ad.usersInGroup(i[1], i[0])
                            logging.debug("Group Lookup using EMAIL ("+email+"): Success")
                            alert = "<div align=\"left\" class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Admin's Found!</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>Please contact one of the following admins to get added to your group:</p><ul>"
                            return render_template("client/admin_lookup.html", alert=alert, admindict=admindict, grouplist=grouplist)
                    # Step 1 Failed: User does not have an Acrobat Sign Account
                    else:
                        logging.debug("Email ("+email+"): No Account Found")
                        flash(email, "emailNotFound")
                        return redirect(request.url)
                # Step 1 Failed: users domain is not claimed in the UHG console
                elif bool is None:
                    alert = "<div align=\"left\" class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Unclaimed Domain</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following domain <strong>" + \
                        message+"</strong> is not a claimed domain in UHG's Adobe Console.</p><p class=\"mb-1\">Currently only users with claimed domains can be provisioned in Adobe Acrobat Sign, because of this <strong>" + \
                            email+"</strong> does not have an active account in Adobe Acrobat Sign.</p></div>"
                    logging.debug("Access Check: Unclaimed Domain")
                    return render_template("client/admin_lookup.html", alert=alert, grouplist=grouplist)
                else:
                    logging.debug("Invalid email format: "+message)
                    flash(message, "email")
                    return redirect(request.url)
            else:
                result, groupid = ad.grouplist(group)
                if result == True:
                    if groupid != "":
                        # using the group ID, this call runs an API call to capture all users in that group and creates a dictionary of admins to return
                        admindict = ad.usersInGroup(groupid, group)
                        if len(admindict[group]) != 0:
                            logging.debug("Group Lookup ("+group+"): Success")
                            alert = "<div align=\"left\" class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\">Admin's Found!</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p class=\"ms-4\">Please contact one of the following admins to get added to your group, or make changes to your group settings.</p><ul>"
                            return render_template("client/admin_lookup.html", alert=alert, admindict=admindict, grouplist=grouplist)
                        else:
                            logging.warn("Group ("+group+"): No Admin For this group")
                            flash(group, "noAdmin")
                            return redirect(request.url)
                    else:
                        logging.warn("Group ("+group+"): Not found")
                        flash(group, "groupNotFound")
                        return redirect(request.url)
                else:
                    flash(groupid, "alert")
                    return redirect(request.url)
    return render_template("client/admin_lookup.html", grouplist=grouplist)
# End Find Admin Page_________________________________________________________________________________________________________________________________________________

@app.route("/open-ticket")
def openticket():
    "This is the weppage users will visit to open one of the following tickets (Incident, Net New, Enhancement)"
    return render_template("client/openticket.html")
