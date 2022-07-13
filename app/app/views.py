from app import app
from flask import render_template, request, redirect

# Modules are not running when seperated in a different python file
from crypt import methods
import requests
import sys
import json
import pandas as pd # for reading csv

# Start of Modules____________________________________________________________________________________
class AcrobatData(object):
    "Grouping of methods that takes a user input and checks their Acrobat Sign access as well as giving them information on potential solutions if they do not pass validation"

    def __init__(self, claimed_domains_file, users_esignatures_file, user_emails_cache, cached=False):  
        '''create instance and load data from local files. If emails_file is not N, this would be a cache
        claimed_domains_file (str): path to local file with claimed domains
        user_emails_cache (str): path to local cache emails file (if cached is True). If cached is False,  
            user email list will be downloaded and saved to that path so it can later be used as cache
        
        Note: if some the read or write file operations fail, I simply bail out
        '''

        # make file paths into instance attributes
        self.user_emails_cache = user_emails_cache
        self.users_esignatures_file = users_esignatures_file

        self.user_emails = None
        self.users_esignatures = None
        self.bearer_id = None

        self.cached = cached

        # using pandas to read in the csv file as a dataframe and then extract each column I need as a list
        try:
            domains_df = pd.read_csv(claimed_domains_file)
        except Exception as e:
            print("Error with opening", claimed_domains_file, e)
            sys.exit()  # This assumes that we can't run the app with this error, so I'm bailing out ..
        
        self.valid_domains = domains_df["Domain"].to_list()
        
        # set bearer ID from config file 
        self.bearer_id = app.config["SECRET_KEY"]


        if cached == True:
            # load emails from cache. Single column csv file with Cached_emails as header
            try:
                users_df = pd.read_csv(self.user_emails_cache)
            except Exception as e:
                print("Error with opening", self.user_emails_cache, e)
                sys.exit()  # This assumes that we can't run the app with this error, so I'm bailing out ..
            
            self.user_emails = users_df["Email"].to_list() # make emails list from that column
        
        else: # download emails and store as cache file
            self.user_emails = self.loadUserList()
            header = ["Email", "ID"] 
            df = pd.DataFrame(self.user_emails, 
                   columns=header)
            #df = pd.DataFrame({"Cached_emails": self.user_emails}) # column name is Cached_emails
            try:
                df.to_csv(self.user_emails_cache, index=False) # no index column
            except Exception as e:
                print("Error writing emails cache", self.user_emails_cache, e)
                # Not stopping here b/c technically we can continue, it's just that the next 
                # loading cache will fail.
            
    #Step 1
    def emailvalidation(self, email):
        "This function will take the users input and determine if it is a legit email and is formatted correctly, while also running a domain check"        
        
        # How many @ signs?
        num_at = email.count("@")
        if num_at != 1: return "email format invalid: must have only one \'@\' character"
        
        # How many chars in username?
        l = email.split("@")
        username, domainname = l[0], l[1]
        if len(username) < 3 or len(username) > 16: 
            return "email format invalid: local-part (\'before @ sign\') must contain 3 - 16 alfanumaric characters"
        
        # how many dots in domain name?
        if domainname.count(".") != 1:
            return "domain-name must have exactly one '.'!"
        
        # split into B and C 
        B, C = domainname.split(".")
        
        # how many chars in B?
        if len(B) < 2 or len(B) > 8:
            return "domain name before '.' must contain 2 - 8 alfanum chars"
        
        # is C legit?
        if C not in ["com", "edu", "org", "gov"]: 
            return "domain name must be one of the following: .com, .edu, .org, .gov"
    
        # is domain inside the valid_domains list?
        if domainname in self.valid_domains:
            return True, domainname     
        else:
            return "invalid_domain", domainname


    #Step 2
    def loadUserList(self):
        "This function loads the user list from the Adobe Sign Rest API"
        #These elements will be blank and used in the below while loop
        emails = tuple()
        nextcursor = ""

        while True:
        #If next cursor is blank this is the first time through the loop
            if nextcursor == "":
                url = "https://api.na3.adobesign.com/api/rest/v6/users?pagesize=5000"
            #If next cursor is NOT blank there is more pages to run through
            else:
                nextcursor = "?cursor=" + nextcursor
                url = "https://api.na3.adobesign.com/api/rest/v6/users"+nextcursor+"&pageSize=5000"
            
            payload={}
            headers = {
                'Authorization': self.bearer_id
            }
            #JSON Data
            response = requests.request("GET", url, headers=headers, data=payload)
            if response.status_code != 200:
                print(response.status_code)
                sys.exit
            #Run the emailist function to get a list of emails and a nextcursors from the JSON data and put it in lists
            useremailsandid, nextcursor = self.parseJSONUsers(response) # catch the 2 returns

            if nextcursor == None: # go no new cursor, so we're done
                return emails
            else: # collect new user emails and go agin with next cursor
                emails += useremailsandid

    def acrobatSignAccessCheck(self, user_email):
        "This Function takes the user input and returns boolean: True (if email finds a match in the Loaded User List) and User ID, or Boolean: False"

        if user_email in self.user_emails:
            try:
                users_df = pd.read_csv(self.user_emails_cache)
            except Exception as e:
                print("Error with opening", self.user_emails_cache, e)
                sys.exit()  # This assumes that we can't run the app with this error, so I'm bailing out ..
            userid = users_df.query('Email==@ user_email')['ID'] #query the dataframe to find the ID that corresponds with the email
            useridstr = str(userid.values[0]) #turn panda array of 1 value into string to return
            return True, useridstr

        return False, None # _ is a valid variable name, short for IDC

    def parseJSONUsers(self, jsondata):
        "This function will return an [email and ID] list, and nextcursor if applicable"
        #Parse JSON response into a Dictionary of two items (userInfoList:, Page:)
        api_users = json.loads(jsondata.text)

        #This list will be used to capture all the emails in the 'user' dictionary later on
        emailandIDlist = [] 

        #This variable is a list of Dictionaries, inside each item is the follow dictionary keys (email:, company:, id:, isAccountAdmin:, accountId:)
        users = api_users["userInfoList"]

        #This for loop goes through each item in the variable list(users) and grabs the email and saves it to the variable list(emailandIDlist)
        emailandIDlist = [(d['email'], d['id']) for d in users]

        #Page is a dictionary item with another dictionary item inside it called nextCursor. The next cursor is captured and used in subsequent API calls to get the next page.
        page = api_users["page"]  
        if len(page) != 0:
            nextcursor = page["nextCursor"]
            return emailandIDlist, nextcursor #There is more pages
        else:
            return emailandIDlist, None

    #Step 3
    def groupCheck(self, userID):
        "This function takes the user ID and runs it in an API call that returns (groupId (string); groupName (string); createdDate (date, optional); isDefaultGroup (boolean, optional)"
        #Run API GET
        url = "https://api.na3.adobesign.com/api/rest/v6/users/"+userID+"/groups"

        payload={}
        headers = {
            'Authorization': self.bearer_id
        }

        response = requests.request("GET", url, headers=headers, data=payload)

        #Parse JSON data into Dictionary
        groupsinfo = json.loads(response.text) 

        info = groupsinfo["groupInfoList"]
        returnedinfo = []
        for i in info: # For each group the user is apart of grab the name and groupid
            #returnedinfo.append([i["name"],i["id"]]) # Maybe this is wrong but I don't think you need the outer [] as append will do that anyway
            nameandid = (i["name"],i["id"])
            returnedinfo.append(nameandid) # this could be wrong ...
        return returnedinfo

    #Step 4
    def usersInGroup(self, groupIDList):
        "This function takes the Group ID(s) and runs it in an API call that returns (email (string):id (string): isGroupAdmin (boolean): company (string, optional): firstName (string, optional): lastName (string, optional):"
        adminlist = []
        for i in groupIDList:
            group = i[0]
            groupid = i[1]
            url = "https://api.na3.adobesign.com/api/rest/v6/groups/"+groupid+"/users"

            payload={}
            headers = {
                'Authorization': self.bearer_id
            }

            response = requests.request("GET", url, headers=headers, data=payload)

            groupusers = json.loads(response.text)

            userlist = groupusers["userInfoList"]
            for i in userlist:
                if i["isGroupAdmin"] == True:
                    tempvar = i["firstName"], i["lastName"], i["email"]
                    adminlist.append([group, tempvar])
            
        return adminlist

    #Step 5
    def activeDirectoryCheck(self, email):
        "This function checks active directory to see the user is part of the required security group in Active Directory"
        #Import csv file
        try:
            df = pd.read_csv(self.users_esignatures_file)
        except Exception as e:
                print("Error reading users esignature file", self.self.users_esignatures_file, e)
                sys.exit()
        self.users_esignatures = df["Mail"].to_list()


        #Run through row in the csv file and check the email against the csv file of users in the dtm_esignature security group
        if email in self.users_esignatures:
            return True, email       # Why even return the email?
    
        return False, email

#End of modules __________________________________________________________________________________________________________________________________________________


@app.route("/")
def home():
    "This is the home webpage"
    return render_template("client/index.html")


@app.route("/request-access", methods=["GET", "POST"])
def signcheck():
    "This webpage is for running the Adobe Acrobat Sign Access Check for Users"
    # make a instance (object) of the class and use instance methods from now on
    ad = AcrobatData(claimed_domains_file="data_files/claimed_domains.csv",
            users_esignatures_file="data_files/dtm_esignature_users.csv",
            user_emails_cache="data_files/user_info.csv",
            cached=True)

    if request.method == "POST":
        userinput = request.form["useremail"]

        print("Access Check", userinput)                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     
        #Step 1: Email Validation, this check will verify if the user input is a valid email
        result, domain = ad.emailvalidation(userinput)
        if result == True: # Runs email through function that checks if it is formatted correctly, if so returns True, if not returns error message
            # Step 2: Adobe Acrobat Sign Access Check, this check will look through a list of users in Adobe sign that are active and validate if the user input email is part of that list
            result, userId = ad.acrobatSignAccessCheck(userinput) #Returns True and user ID if their is a match, returns false if their isn't a match
            #Step 2 Passed: Adobe Acrobat Sign Access Check, user has an Adobe Acrobat Sign Account   
            if result == True: 
                # Step 3: Run a group check on the user that passed Adobe Acrobat Sign Access Check
                groupnameandid = ad.groupCheck(userId) #using the user ID, return the group (name, Id) that they are apart of
                groups = []
                for i in groupnameandid:
                    group = str(i[0])
                    groups.append(group)
                # Step 3 Failed: User is in Default Group        
                if len(groups) == 1 and group == "Default Group": #User is part of default group (needs to get added to a group)
                    alert = "<div class=\"alert alert-warning alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Warning:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Missing Group Assignment</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user "+userinput+" has an account in Acrobat Sign but by default all accounts created in Acrobat Sign will not have the ability to send.</p><p class=\"mb-1\">You will need to contact your group admin to add you to the appropriate group.</p>Don't know your group admin? No Problem! Find your group admin with this <a href=\"/groupadmin\" class=\"alert-link\">link to our Find Group Admin Tool</a></div></div>"                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 
                    print("User in Default Group")
                    return render_template("client/request_access_check.html", alert = alert) #renders HTML template and passed Alert which is HTML that gets appended
                # Step 3 Passed: Using is in a group and active            
                else:
                    alert="<div class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Setup Complete</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following email has an active account in Adobe Acrobat Sign!</p><p class=\"mb-1\">Please follow the link below to login. You will need your MSID and MS Password for login</p><a target=\"_blank\" rel=\"noopener noreferrer\" href=\" https://unitedhg.na3.adobesign.com/account/homeJS\">Adobe Acrobat Sign</a></div>"
                    print("Success: Active User in Group")
                    return render_template("client/request_access_check.html", alert = alert) #renders HTML template and passed Alert which is HTML that gets appended
            #Step 2 Failed: Adobe Acrobat Sign Access Check failed
            else: 
                result = ad.activeDirectoryCheck(userinput)
                # Step 4: Check Security Group (dtm_esignature)
                # Step 4 passed: user is in the correct security group    
                if result == True:
                    alert="<div class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Unknown Failure</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user "+userinput+" was not successfully provisioned in Acrobat Sign despite following the proper provisioning procedures. Please open a ticket with the eSignature Support Team</p><p class=\"mb-1\">Please follow the link to <a target=\"_blank\" rel=\"noopener noreferrer\" href=\"https://atlas.uhg.com/contactLanding/openTicket#\">open a ticket</a></p></div>"
                    print("Failed: Uknown Failure")
                    return render_template("client/request_access_check.html", alert = alert) #renders HTML template and passed Alert which is HTML that gets appended
                # Step 4 Failed: User is not in the required security group
                else:
                    alert = "<div class=\"alert alert-warning alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Warning:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Request Process Not Completed</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user "+userinput+" is not part of the required AD Security Group for Acrobat Sign. This can be requested following the steps below:</p>If your group is already setup for Acrobat Sign submit a <a target=\"_blank\" href=\"https://secure.uhc.com\" class=\"alert-link\">secure</a> request<ol type=\"1\" class=\"mb-1\"><li>Click Add Group Membership..</li><li>Enter dtm_esignature in the Search groups by groupname box.</li><li>Click Search.</li><li>Click dtm_esignature to highlight.</li><li>Click the left arrow to move it to the Selected Groups box.</li><li>Click Next.</li><li>Verify the information.</li><li>Add a Business Justification.</li><li>Click Submit.</li><hr class=\"mb-2\"><h5>After Submission:</h5><p>Wait for your request to be approved (Your secure request needs approval from your manager and the eSignature Support Team).</p><p>Once your reqest is approved the system will automatically create a disabled account in Adobe Acrobat Sign. This automated sync process can take up to three hours.</p><hr class=\"mb-2\"><h5>How to Verify:</h5><p>To verify next steps in the request process, simply submit your email again using this tool. If you get this same alert that means one of the following: Your request was not submitted correctly, your request has not yet been approved or was denied, the automatted sync tool is still running.</p></div></div>"
                    return render_template("client/request_access_check.html", alert = alert) #renders HTML template and passed Alert which is HTML that gets appended
        # Step 1 Failed: users domain is not claimed in the UHG console
        elif result == "invalid_domain":
            alert="<div class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Unclaimed Domain</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following domain "+domain+" is not a claimed domain in UHG's Adobe Console.</p><p class=\"mb-1\">Currently only users with claimed domains can be provisioned in Adobe Acrobat Sign. If you would like to discuss next steps please open a ticket with the eSignature Support Team</p><p class=\"mb-1\">Please follow the link to <a target=\"_blank\" rel=\"noopener noreferrer\" href=\"https://atlas.uhg.com/contactLanding/openTicket#\">open a ticket</a></p></div>"
            print("Access Check: Unclaimed Domain")
            return render_template("client/request_access_check.html", alert = alert)
        # Step 1 Failed: User inputed email in a invalid format
        else:
            warning = str(ad.emailvalidation(userinput))
            print(warning)
    # Loads Orign HTML Template for Webpage
    return render_template("client/request_access_check.html")


@app.route("/find-admin", methods=["GET", "POST"])
def clienttools():
    "This webpage is for users who don't know who their admin is"
        # make a instance (object) of the class and use instance methods from now on
    ad = AcrobatData(claimed_domains_file="data_files/claimed_domains.csv",
            users_esignatures_file="data_files/dtm_esignature_users.csv",
            user_emails_cache="data_files/user_info.csv",
            cached=True)
    if request.method == "POST":
        userinput = request.form["useremail"]
        print("Group Admin Check", userinput)

         #Step 1: Email Validation, this check will verify if the user input is a valid email
        result, domain = ad.emailvalidation(userinput)
        if result == True: # Runs email through function that checks if it is formatted correctly, if so returns True, if not returns error message

            # Step 2: Adobe Acrobat Sign Access Check, this check will look through a list of users in Adobe sign that are active and validate if the user input email is part of that list
            result, userId = ad.acrobatSignAccessCheck(userinput) #Returns True and user ID if their is a match, returns false if their isn't a match
            #Step 2 Passed: Adobe Acrobat Sign Access Check, user has an Adobe Acrobat Sign Account   
            if result == True: 
                # Step 3: Run a group check on the user that passed Adobe Acrobat Sign Access Check
                groupnameandid = ad.groupCheck(userId) #using the user ID, return the group (name, Id) that they are apart of
                groups = []
                for i in groupnameandid:
                    group = str(i[0])
                    groups.append(group)
                # Step 3 Failed: User is in Default Group        
                if len(groups) == 1 and group == "Default Group": #User is part of default group (needs to get added to a group)
                    alert = "<div class=\"alert alert-warning alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Warning:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Missing Group Assignment</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user "+userinput+" has an account in Acrobat Sign but by default all accounts created in Acrobat Sign will not have the ability to send.</p><p class=\"mb-1\">You will need to contact your group admin to add you to the appropriate group.</p>Don't know your group admin? No Problem! Find your group admin with this <a href=\"/groupadmin\" class=\"alert-link\">link to our Find Group Admin Tool</a></div></div>"                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 
                    print("User in Default Group")
                    return render_template("client/admin_lookup.html", alert = alert) #renders HTML template and passed Alert which is HTML that gets appended
                # Step 3 Passed: Using is in a group and active            
                else:
                    # Create a list of IDs
                    adminlist = ad.usersInGroup(groupnameandid) #using the group ID, this call runs an API call to capture all users in that group and creates a list of admins to return
                    alert="<div class=\"alert alert-success alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Success:\"><use xlink:href=\"#check-circle-fill\" /></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Admin's Found!</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>Please contact one of the following admins to get added to your group:</p>"
            # Step 1 Failed: User does not have an Acrobat Sign Account
            else:
                alert="<div class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">No Account Found</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following user "+userinput+" does not have an account in Adobe Acrobat Sign.</p><p class=\"mb-1\">Please try a different colleague.</p></div>"
                print("Failed: No Account For Colleague")
                return render_template("client/admin_lookup.html", alert = alert)
        # Step 1 Failed: users domain is not claimed in the UHG console
        elif result == "invalid_domain":
            alert="<div class=\"alert alert-danger alert-dismissible fade show mx-3\" role=\"alert\"><div><svg style=\"display:inline\" class=\"bi flex-shrink-0 me-2 mb-2\" width=\"24\" height=\"24\" role=\"img\" aria-label=\"Danger:\"><use xlink:href=\"#exclamation-triangle-fill\"/></svg><h4 style=\"display:inline\" class=\"alert-heading pt-2\">Unclaimed Domain</h4></div><button type=\"button\" class=\"btn-close\" data-bs-dismiss=\"alert\" aria-label=\"Close\"></button><p>The following domain "+domain+" is not a claimed domain in UHG's Adobe Console.</p><p class=\"mb-1\">Currently only users with claimed domains can be provisioned in Adobe Acrobat Sign. If you would like to discuss next steps please open a ticket with the eSignature Support Team</p><p class=\"mb-1\">Please follow the link to <a target=\"_blank\" rel=\"noopener noreferrer\" href=\"https://atlas.uhg.com/contactLanding/openTicket#\">open a ticket</a></p></div>"
            print("Access Check: Unclaimed Domain")
            return render_template("client/admin_lookup.html", alert = alert)
        else: 
            print("Need to add code at end of admin lookup module")
    
    return render_template("client/admin_lookup.html")
