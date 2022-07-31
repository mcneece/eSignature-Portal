from app import app
from flask import render_template, request, redirect

# Modules are not running when seperated in a different python file
from crypt import methods
import requests
import sys
import json
import pandas as pd  # for reading csv

# Start of Modules____________________________________________________________________________________


class AcrobatData(object):
    "Grouping of methods that takes a user input and checks their Acrobat Sign access as well as giving them information on potential solutions if they do not pass validation"
    # Start of Request Modules========================================================================

    def __init__(self, claimed_domains_file, users_esignatures_file, cached=False):
        '''create instance and load data from local files. If emails_file is not N, this would be a cache
        claimed_domains_file (str): path to local file with claimed domains

        Note: if some the read or write file operations fail, I simply bail out
        '''

        # make file paths into instance attributes
        self.users_esignatures_file = users_esignatures_file
        self.users_esignatures = None
        self.bearer_id = None
        self.cached = cached

        # using pandas to read in the csv file as a dataframe and then extract each column I need as a list
        try:
            domains_df = pd.read_csv(claimed_domains_file)
        except Exception as e:
            print("Error with opening", claimed_domains_file, e)
            # This assumes that we can't run the app with this error, so I'm bailing out ..
            sys.exit()

        self.valid_domains = domains_df["Domain"].to_list()

        # set bearer ID and URL from config file
        self.bearer_id = app.config["SECRET_KEY"]

    # Step 1
    def emailvalidation(self, email):
        "This function will take the users input and determine if it is a legit email and is formatted correctly, while also running a domain check"

        # How many @ signs?
        num_at = email.count("@")
        if num_at != 1:
            return "email format invalid: must have only one \'@\' character", None

        # Split username and domainname
        l = email.split("@")
        username, domainname = l[0], l[1]

        # how many dots in domain name?
        if domainname.count(".") != 1:
            return "domain-name must have exactly one '.'!", None

        # split into B and C
        B, C = domainname.split(".")

        # is C legit?
        if C not in ["com", "edu", "org", "gov"]:
            return "domain name must be one of the following: .com, .edu, .org, .gov", domainname

        # is domain inside the valid_domains list?
        if domainname in self.valid_domains:
            return True, domainname
        else:
            return "invalid_domain", domainname

    # Step 2
    def acrobatSignAccessCheck(self, userinput):
        "This function takes an email as a parameter and runs a GET user/userEmail API call to Acrobat Sign returning email:'', id:'',isAccountAdmin:''"

        # Make API call using Python requests package
        url = app.config["REQUEST_URL_USERS"]

        payload = {}
        headers = {
            'x-email': userinput,
            'Authorization': self.bearer_id
        }
        response = requests.request("GET", url, headers=headers, data=payload)
        jsondata = json.loads(response.text)

        # Handeling Errors
        # If response is 404 then user email does not exist in Adobe Sign
        if response.status_code == 404:
            return False, None
        # If response is not 404 and still not 200 then print code: and message: provided by adobe to console
        elif response.status_code != 200:
            # add code for alerting error for UI
            print("users/userByEmail Response Error:",
                  jsondata["code"], jsondata["message"])
            # This breaks the site need to add code instead to flash this message.
            sys.exit()
        userid = jsondata["userId"]
        return True, userid

    # Step 3
    def groupCheck(self, userID):
        "This function takes the user ID and runs it in an API call that returns (groupId (string); groupName (string); createdDate (date, optional); isDefaultGroup (boolean, optional)"

        # Make API call using Python requests package
        url = app.config["REQUEST_URL_GROUPS"]

        payload = {}
        headers = {
            'Authorization': self.bearer_id
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        # Parse JSON data into Dictionary
        jsondata = json.loads(response.text)

        # If response is not 200 then unkown error stop system
        if response.status_code != 200:
            # add code for alerting error for UI
            print("users/userByEmail Response Error:",
                  jsondata["code"], jsondata["message"])
            # This breaks the site need to add code instead to flash this message.
            sys.exit()

        groupinfo = jsondata["groupInfoList"]
        returnedinfo = []
        for i in groupinfo:  # For each group the user is apart of grab the name and groupid
            nameandid = (i["groupName"], i["groupId"])
            returnedinfo.append(nameandid)
        return returnedinfo

    # Step 4
    def usersInGroup(self, groupID, groupName):
        "This function takes the Group ID(s) and runs it in an API call that returns (email (string):id (string): isGroupAdmin (boolean): company (string, optional): firstName (string, optional): lastName (string, optional):"

        url = app.config["REQUEST_URL_GROUPS"]+"/"+groupID+"/users"

        payload = {}
        headers = {
            'Authorization': self.bearer_id
        }

        response = requests.request("GET", url, headers=headers, data=payload)
        jsondata = json.loads(response.text)
        # If response is not 200 then unkown error stop system
        if response.status_code != 200:
            # add code for UI alert
            print("groups/"+groupID+"/users Response Error:",
                  jsondata["code"], jsondata["message"])
            # This breaks the site need to add code instead to flash this message.
            sys.exit()

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
        # Import csv file
        try:
            df = pd.read_csv(self.users_esignatures_file)
        except Exception as e:
            print("Error reading users esignature file",
                  self.self.users_esignatures_file, e)
            sys.exit()
        self.users_esignatures = df["Mail"].to_list()

        # Run through row in the csv file and check the email against the csv file of users in the dtm_esignature security group
        if email in self.users_esignatures:
            return True, email       # Why even return the email?
        return False, email
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
            # add code for UI alert
            print("users/userByEmail Response Error:",
                  jsondata["code"], jsondata["message"])
            # This breaks the site need to add code instead to flash this message.
            sys.exit()

        groupID = ""

        for i in jsondata["groupInfoList"]:
            if groupName.lower() == i["groupName"].lower():
                groupID = i["groupId"]
        return groupID
    # End of Find Admin Modules++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++
# End of modules __________________________________________________________________________________________________________________________________________________


@app.route("/")
def home():
    "This is the home page containing information and links to Adobe Acrobat Sign, most of this code is in the index.html file"
    return render_template("client/index.html")
# End Home Page____________________________________________________________________________________________________________________________________________________


@app.route("/request-access", methods=["GET", "POST"])
def signcheck():
    "This webpage is for running the Adobe Acrobat Sign Access Check for Users"
    # make a instance (object) of the class and use instance methods from now on
    ad = AcrobatData(claimed_domains_file="data_files/claimed_domains.csv",
                     users_esignatures_file="data_files/dtm_esignature_users.csv",
                     cached=True)  # will use this value later on when I implement powershell script for AD lookup

    if request.method == "POST":
        userinput = request.form["useremail"]

        print("Access Check", userinput)
        # Step 1: Email Validation, this check will verify if the user input is a valid email
        result, domain = ad.emailvalidation(userinput)
        if result == True:  # Runs email through function that checks if it is formatted correctly, if so returns True, if not returns error message
            # Step 2: Adobe Acrobat Sign Access Check, this check will look through a list of users in Adobe sign that are active and validate if the user input email is part of that list
            # Returns True and user ID if their is a match, returns false if their isn't a match
            result, userId = ad.acrobatSignAccessCheck(userinput)
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
                # User is part of default group (needs to get added to a group)
                if len(groups) == 1 and group == "Default Group":
                    alert = "<div class=\"alert alert-warning alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Warning:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Missing Group Assignment</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user <strong>" + \
                        userinput+"</strong> has an account in Acrobat Sign but by default all accounts created in Acrobat Sign will not have the ability to send.</p><p class=\"mb-1\">You will need to contact your group admin to add you to the appropriate group.</p>Don't know your group admin? No Problem! Find your group admin with this <a href=\"/find-admin\" class=\"alert-link\">link to our Find Group Admin Tool</a></div></div>"
                    print("User in Default Group")
                    # renders HTML template and passed Alert which is HTML that gets appended
                    return render_template("client/request_access_check.html", alert=alert)
                # Step 3 Passed: Using is in a group and active
                else:
                    alert = "<div class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Setup Complete</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following email <strong>" + \
                        userinput+"</strong> has an active account in Adobe Acrobat Sign!</p><p class=\"mb-1\">Please follow the link below to login. You will need your MSID and MS Password for login</p><a target=\"_blank\" rel=\"noopener noreferrer\" class=\"alert-link\" href=\" https://unitedhg.na3.adobesign.com/account/homeJS\">Adobe Acrobat Sign</a></div>"
                    print("Success: Active User in Group")
                    # renders HTML template and passed Alert which is HTML that gets appended
                    return render_template("client/request_access_check.html", alert=alert)
            # Step 2 Failed: Adobe Acrobat Sign Access Check failed
            else:
                result = ad.activeDirectoryCheck(userinput)
                # Step 4: Check Security Group (dtm_esignature)
                # Step 4 passed: user is in the correct security group
                if result == True:
                    alert = "<div class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Unknown Failure</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user <strong>" + \
                        userinput+"</strong> was not successfully provisioned in Acrobat Sign despite following the proper provisioning procedures. Please open a ticket with the eSignature Support Team</p><p class=\"mb-1\">Please follow the link to <a target=\"_blank\" rel=\"noopener noreferrer\" class=\"alert-link\" href=\"https://atlas.uhg.com/contactLanding/openTicket#\">open a ticket</a></p></div>"
                    print("Failed: Uknown Failure")
                    # renders HTML template and passed Alert which is HTML that gets appended
                    return render_template("client/request_access_check.html", alert=alert)
                # Step 4 Failed: User is not in the required security group
                else:
                    alert = "<div class=\"alert alert-warning alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Warning:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Request Process Not Completed</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user <strong>"+userinput + \
                        "</strong> is not part of the required AD Security Group for Acrobat Sign. This can be requested following the steps below:</p>If your group is already setup for Acrobat Sign submit a <a target=\"_blank\" href=\"https://secure.uhc.com\" class=\"alert-link\">secure</a> request<ol type=\"1\" class=\"mb-1\"><li>Click Add Group Membership..</li><li>Enter dtm_esignature in the Search groups by groupname box.</li><li>Click Search.</li><li>Click dtm_esignature to highlight.</li><li>Click the left arrow to move it to the Selected Groups box.</li><li>Click Next.</li><li>Verify the information.</li><li>Add a Business Justification.</li><li>Click Submit.</li><hr class=\"mb-2\"><h5>After Submission:</h5><p>Wait for your request to be approved (Your secure request needs approval from your manager and the eSignature Support Team).</p><p>Once your reqest is approved the system will automatically create a disabled account in Adobe Acrobat Sign. This automated sync process can take up to three hours.</p><hr class=\"mb-2\"><h5>How to Verify:</h5><p>To verify next steps in the request process, simply submit your email again using this tool. If you get this same alert that means one of the following: Your request was not submitted correctly, your request has not yet been approved or was denied, the automatted sync tool is still running.</p></div></div>"
                    # renders HTML template and passed Alert which is HTML that gets appended
                    return render_template("client/request_access_check.html", alert=alert)
        # Step 1 Failed: users domain is not claimed in the UHG console
        elif result == "invalid_domain":
            alert = "<div class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Unclaimed Domain</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following domain <strong>" + \
                domain+"</strong> is not a claimed domain in UHG's Adobe Console.</p><p class=\"mb-1\">Currently only users with claimed domains can be provisioned in Adobe Acrobat Sign. If you would like to discuss next steps please open a ticket with the eSignature Support Team</p><p class=\"mb-1\">Please follow the link to <a target=\"_blank\" rel=\"noopener noreferrer\" class=\"alert-link\" href=\"https://atlas.uhg.com/contactLanding/openTicket#\">open a ticket</a></p></div>"
            print("Access Check: Unclaimed Domain")
            return render_template("client/request_access_check.html", alert=alert)
        # Step 1 Failed: User inputed email in a invalid format
        else:
            warning = str(ad.emailvalidation(userinput))
            print(warning)
    # Loads Orign HTML Template for Webpage
    return render_template("client/request_access_check.html")
# End Request Page____________________________________________________________________________________________________________________________________________________


@app.route("/find-admin", methods=["GET", "POST"])
def findadmin():
    "This webpage is for users who don't know who their admin is"
    # make a instance (object) of the class and use instance methods from now on
    ad = AcrobatData(claimed_domains_file="data_files/claimed_domains.csv",  # This file stores all claimed domains
                     # This file stores all AD users in the dtm_esignature security group
                     users_esignatures_file="data_files/dtm_esignature_users.csv",
                     cached=True)  # will use this value later on when I implement powershell script for AD lookup

    admindict = {}  # Empty Dictionary that will be used to merge multiple Admin Dictionaries together

    if request.method == "POST":
        email = request.form["email"]
        group = request.form["group"]
        # If the user input something
        if email or group != "":
            # If the user submited information in the email search run email search code:
            if len(email) > len(group):
                # Step 1: Email Validation, this check will verify if the user input is a valid email
                result, domain = ad.emailvalidation(email)
                if result == True:  # Runs email through function that checks if it is formatted correctly, if so returns True, if not returns error message
                    # Step 2: Adobe Acrobat Sign Access Check, this check will look through a list of users in Adobe sign that are active and validate if the user input email is part of that list
                    # Returns True and user ID if their is a match, returns false if their isn't a match
                    result, userId = ad.acrobatSignAccessCheck(email)
                    # Step 2 Passed: Adobe Acrobat Sign Access Check, user has an Adobe Acrobat Sign Account
                    if result == True:
                        print("pass step 2")
                        # Step 3: Run a group check on the user that passed Adobe Acrobat Sign Access Check
                        # using the user ID, return the group (name, Id) that they are apart of
                        groupnameandid = ad.groupCheck(userId)
                        groups = []
                        for i in groupnameandid:
                            group = str(i[0])
                            groups.append(group)
                        # Step 3 Failed: User is in Default Group
                        if len(groups) == 1 and group == "Default Group":
                            print("Step 3 fail")
                            alert = "<div class=\"alert alert-warning alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Warning:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Missing Group Assignment</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user <strong>" + \
                                email+"</strong> has an account in Acrobat Sign but is not part of a group.</p><p>Try using another colleague's email or search by group name.</div>"
                            print("User in Default Group")
                            # renders HTML template and passed Alert which is HTML that gets appended
                            return render_template("client/admin_lookup.html", alert=alert)
                        # Step 3 Passed: User is in a group and active
                        else:
                            print("pass step 3")
                            # Create a dictionary of admin and render it to the HTML file
                            for i in groupnameandid:  # For each group and id in the list merge the admins from that group to a dictionary
                                # using the group ID, this call runs an API call to capture all users in that group and creates a list of admins to return
                                admindict = admindict | ad.usersInGroup(i[1], i[0])
                            print(admindict)
                            alert = "<div align=\"left\" class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Admin's Found!</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>Please contact one of the following admins to get added to your group:</p><ul>"
                            return render_template("client/admin_lookup.html", alert=alert, admindict=admindict)
                    # Step 1 Failed: User does not have an Acrobat Sign Account
                    else:
                        alert = "<div class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">No Account Found</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following email <strong>" + \
                            email+"</strong> does not have an account in Adobe Acrobat Sign.</p><p class=\"mb-1\">Please try a different colleague email.</p></div>"
                        print("Failed: No Account For Colleague")
                        return render_template("client/admin_lookup.html", alert=alert)
                # Step 1 Failed: users domain is not claimed in the UHG console
                elif result == "invalid_domain":
                    alert = "<div align=\"left\" class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Unclaimed Domain</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following domain <strong>" + \
                        domain+"</strong> is not a claimed domain in UHG's Adobe Console.</p><p class=\"mb-1\">Currently only users with claimed domains can be provisioned in Adobe Acrobat Sign, because of this <strong>" + \
                            email+"</strong> does not have an active account in Adobe Acrobat Sign.</p></div>"
                    print("Access Check: Unclaimed Domain")
                    return render_template("client/admin_lookup.html", alert=alert)
                else:
                    print("Need to add code at end of admin lookup module")
            # If the user submited information in the group search run group search code:
            else:
                groupid = ad.grouplist(group)
                if groupid != "":
                    # using the group ID, this call runs an API call to capture all users in that group and creates a dictionary of admins to return
                    admindict = ad.usersInGroup(groupid, group)
                    if len(admindict[group]) != 0:
                        print(admindict)
                        alert = "<div align=\"left\" class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\">Admin's Found!</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p class=\"ms-4\">Please contact one of the following admins to get added to your group, or make changes to your group settings.</p><ul>"
                        return render_template("client/admin_lookup.html", alert=alert, admindict=admindict)
                    else:
                        alert = "<div class=\"alert alert-warning alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Warning:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Admin Not Found</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following group <strong>" + \
                            group+"</strong> does exist, but there is currently not an admin.</p><p>Please <a href=\"/find-admin\" class=\"alert-link\">open a ticket</a>with the eSignature Support Team to resolve. Or try using another group name or search by email.</p></div>"
                else:
                    alert = "<div class=\"alert alert-warning alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Warning:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Group Not Found</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following group <strong>" + \
                        group+"</strong> does not exist in UHG's Acobat Sign account.</p><p>Try using another group name or search by email.</div>"
                    return render_template("client/admin_lookup.html", alert=alert)
    return render_template("client/admin_lookup.html")
# End Find Admin Page_________________________________________________________________________________________________________________________________________________


@app.route("/cancel-agreements", methods=["GET", "POST"])
def cancelnator():
    "This function cancels agreements based on the agreement ID's fed"
    # Step 1 take in a file
    # Here is a sample file
    # Insert agreement IDs
    # Step 2 run through the file
    # The body of the HTML call
    # {
    #  state: canceled
    #   comment: ""
    # }
    # Step 4 For Loop
    # For each ID in file
    # URL/"agreementID"/state

    # Step 3 give output

    # response != 200 give error
    # Else give response
    # Output will be the response
    # click run
    # if no file then give error
    # if no comment give error

    return render_template("client/cancelnator.html")

@app.route("/open-ticket")
def openticket():
    "This is the weppage users will visit to open one of the following tickets (Incident, Net New, Enhancement)"
    return render_template("client/openticket.html")