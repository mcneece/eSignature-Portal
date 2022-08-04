# Overview

The eSignature Support Portal was built to service UnitedHealth Group's employees with their eSignature support needs. The goal of the tool is to automate solutions for common service requests to the internal Optum eSignature Support Team, and give employees access to vital information and functionality in a simplified manner so that they can be self sufficient when utilizing eSignature for their business(es).

# Structure of the project:

The project is primarily python and HTML files with some JavaScript. The run.py file communicates with the views.py and the admin_views.py files to run the project based on configurations from the config.py file in a users preferred browser. Right now there is little to no code in the admin_views file as this is something that will be developed in the future to create functionality only for the operations support team (ex: a dashboard for admin related metrics). So all of the current project runs through the views.py file. In this file you will see the imported python functions at the top that are required for this project and as you scroll down you will see some methods that the file uses to process certain functionality, then lastly you will see the containers for each webpage. This will be reviewed later in this document under the product flow section. When it comes to using visuals the static folder holds all the images, css, and JavaScript for the project. While the templates folder has all of the HTML files required to give the user a GUI that works with the views.py file.


# Additional Install Requirements

After the repository has been cloned and the config.py file is copied from the user guid, you will still need to login to Adobe Acrobat Sign to obtain the required Adobe request URLs for API calls as well as access tokens required for your API call. Since different organization run on different servers the request URLs will be different depending on what organization is running the tool. This all will be configured in the config.py file which is hidden from the repository by the .gitignore file.

## Request URL:
	The request url can be found by completing the following steps:

* Login to Adobe Acrobat Sign
* Selecting ‘Account’ or ‘Group’ from the top navigation (this depended on whether the developer has account admin or group admin privileges).
* Select ‘API Information’ from the left navigation pane
* Select ‘Rest API documentation’ from the body of the web page
* This launches Adobe’s swagger application which will show different request URLs for different API calls.
	
The request URLs you want are GET /users and GET /groups.

* Set REQUEST_URL_USERS = GET /users (in the config.py file)
* Set REQUEST_URL_GROUPS = GET /groups (in the config.py file)

The request URLs for production and sandbox differ and you should add the Sandbox URL to the Development and Test configurations in the config.py file while the Production URL should be set to the production base config.py function. The same goes for access tokens. Sandbox access tokens only work with Sandbox request URLs similar to Production tokens only work with Production URLs

## Access Token:

To get an access token you will follow the same procedures in Adobe Acrobat Sign Production environment and Sandbox environment.
 
You will login
* Select ‘Group’ or ‘Account’ (again depending on your access)
* Select ‘Personal Profile’ from the left navigation
* Select ‘Access Token’ from the left navigation

In this webpage you can create an access token and you will want to create one with “user read” access. From here you can set the SECRET_KEY in the config.py file for production to your production access token, and subsequently set the SECRET_KEY in test and development to the sandbox access token.

# Product Flow

## Home Screen:

The Home Screen is ran by the views.py file. In this file you will see the @app.route("/") and def home() function. This runs all the code for this file which is primarily HTML. You can see that this function renders a HTML template index.html (this is in the return render template function). This is where all the code lies for this webpage. The views.py file renders that index.html file in the browser to power the homepage.

## Open a ticket:

Similar to the Home Screen most of the code involved with opening tickets is HTML. There really isn’t any difference from this page than the home page, it is also ran by the views.py and renders the openticket.html file. That HTML file comprises of three sets of Bootstrap cards that hold text and buttons to link users to three possible ServiceNow request forms. These requests make their way to the operational support team (incident, net new, and enhancement requests).

## Request Access:
The request access and find group admin are the meat and potatoes of this project. When a user navigates to the request access page it renders two possible HTML files. This is because inside the body of the requestaccess.html there is an additinonal navigation pane that allows the user to bounce back for forth between the requestaccess.html and requestaccesscheck.html files.

#### Request Access HTML File:

The request access HTML file has a tutorial video showing a user step by step instructions on how to request services from secure.uhc.com as well as a link to secure.uhc.com.

#### Request Access Check HTML:

This webpage has many functions in order to verify a user has access. This code can be found in the views.py file under the def signcheck function. The following python code runs through four different methods to validate where a user is in the request access process.

Emalvalidation() : The email validation check takes the users input as a parameter and runs the email validation function. In this function it will check if the email has the appropriate structure for a valid email address (ex: only one @ sign). After that it will parse the username and domain and run the domain against a .csv file of claimed domains for UHG. If the .csv file has a match we are good and will continue the verify process. If not it will alert the user that they entered an invalid domain and to open a ticket with our operations team to see if claiming that domain is feasible.

Acrobatsignaccesscheck() :  The Acrobat sign access check function takes the same user inputted email that was used in the email validation function and adds it as a header in an API call to adobe. If that email is found the Adobe will return a 200 request code and the name and user ID for that email. If it is not found the API will return a 404 code. If a 404 code is returned then we know the user does not have an account. While 200 means they do. Any other request code returned is printed to the terminal and sys.exit is performed.

Groupcheck() : is a function that takes the user ID of an existing user found in the acrobatsignaccesscheck() function and uses that ID in the request URL to return the group that use is apart of. That is then validated whether it is the default group. If it is not part of the default group then the user passes the request check and is notified that they are good to go! Otherwise they are notified they are part of the default group and should reach out to a group admin (using the group admin lookup tool)

## Find Group Admin

The find group admin tool is used by employees of UHG to find a group admin of Acrobat Sign devoted to a specific business (group in Acrobat Sign) that they must contact to get access granted to the tool. The tool is broken up into two sections, 1. Searching for an admin using a group name, 2. Searching for an admin using a colleagues email who that want to mirror that access. 

#### Search by group:

When searching by group a user inputs a group name that group name is ran against a list of all groups in UHG’s instance of acrobat sign. This is done by making a API call to Adobe using GET /groups with a page size of 500 (there is currently 350 groups at UHG, this could be lowered for other organizations that have less groups). If there is a group match that group ID is pulled and ran against group admins (a nested dictionary is created in python with group name being at level one and admins being at level 2, this is required encase multiple admins are found). 

#### Search by email

Similar to search by group a user input is ran against information retrieved by an API call this time GET /users/{email}/usersByEmail. If there is a match that users ID is ran against to GET groups API call to capture the admins in a python dictionary. If the user is part of multiple groups then the dictionary will be nested with each group name at level one and under each group name is list of admins. The admins will be returned to the user with their email which is retrieved from the GET groups/{group id}/users.





# Known Issues

Currently the only known issue is if the user types in a invalid email they are not alerted. This is something that was not finished due to time constraints.

# Future Work

Future additions to the eSignature Support Portal that are customer facing will be the addition of bulk canceling of inflight documents, and the ability to look up web forms based on a group or email. There is already know API calls that Adobe shares publicly for PUSH /agreements that can cancel an agreement if you feed the agreement ID in the header of the request. The same goes for the web from lookup. PUSH /widget allows a user to find a web form and it can be utilized with group and user API calls to find a specific user or groups web forms. 