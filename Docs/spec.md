### General description of the Adobe Sign Access Tool
- The Acrobat Sign access tool is a tool that will help service the eSignature Operational Support Team at Optum Technology. 
    * This tool will give clients the information and instructions (or next steps) to successfully provision an account in Adobe Acrobat Sign, without the assistance of a trained eSign support employee.
    * This will be useful for the eSign Support Team as the majority of operational support tickets are related to provisioning a user’s account in Adobe Acrobat Sign.
    * Additionally, this tool will be useful for Acrobat Sign users on the UnitedHealth Group instance (umbrella company of Optum Technology) because it will give a novice user the required hand holding that would be necessary to get them successfully provisioned into Acrobat Sign.
    * This meets the eSign Support Team's goal of making Adobe Acrobat Sign a self-service product by creating a tool that makes it easy for potential Acrobat Sign users to follow the correct steps to get access.

- What is Adobe Acrobat Sign
    * Adobe Acrobat Sign is a cloud-based e-signature service that allows a user to send, sign, track, and manage signature processes using a browser (Firefox, Chrome, Edge, etc...)

- UHG's Adobe Acrobat Sign Provisioning Steps
1. You must be part of the required security group in Active Directory (dtm_esignature).
2. You must have a claimed email domain (ex: @uhg.com) in UHG's Adobe Admin Console.
    * Most users from a newly acquired business run into this issue and need to be informed that their domain must be claimed by their network team, or they must get email migrated to a previously claimed domain such as @uhg.com or @optum.com.
3. They must NOT be dual entitled.
    * This issue happens when a user has their work email associated with a free trial or on a different instance of Acrobat Sign that is not the UHG instance. You can determine if this has happened by them being in the required security group but not active in Acrobat Sign production. For this they must open a ticket with our internal IT team to get their account deleted a reprovisioned on our instance (UHG Instance)
4. They need to be part of a group in Adobe Acrobat Sign
    * By default, everyone provisioned in Acrobat Sign is part of a 'default' group that does NOT have send access for sending out documents for signature.

- Project Sketch
    * Select (<a href="https://github.com/mcneece/eSign-Access-Tool/tree/main/Assets/acrobat_sign_tool.png" download>Download</a>) to view a low fidelity mockup of the purposed tool

- External mechanisms (major packages, API, email, twitter, etc.) I will use:
    * I plan to use Active Directory data (group member data)
        * I will pull this using a PowerShell Script.
    * I plan to also use Adobe Acrobat Sign data either automated via a rest API or manually via a downloaded CSV file
        * This will contain Acrobat Sign group member data such as: email, group name, and send access (Y, N)
        
- Ideal GUI for Acrobat Sign Tool
    * The ideal GUI would likely need to be web-based so anyone across the organization could access it via the company's Intranet.
    * For a minimal viable product, I will first create the logic with a Python file that takes a user input and prints the logic out in the console.
    * In the second version (customer facing version) I will use HTML, CSS, and JavaScript along with a tool (TBD) to interact with previously created python file.
        * The goal is that the python file will have all the necessary backend capabilities and I can plug it in with my HTML, CSS, and JavaScript that will be my front-end solution.
        * I also plan to make the web page bootstrap responsive so it can be displayed on any display size and adapt and maintain its usability.
-----------------------------------------------------------------------------------------
### Acrobat Sign Tool Task Vignettes (User activity "flow")

- Project Prototype
    * Please refer to the high-fidelity prototype for user flow, this was created using Sketch, a computer application and vector graphics editor for macOS. It was then uploaded to Invision a prototyping tool.
    * <a href = "https://team06.invisionapp.com/console/share/7ZW5KX2RQDT">Link to Invision Prototype</a>

1) User input (email)

John Doe is looking to get access to Acrobat Sign because he is working on a project that requires multiple parties to receive and sign documents. John searches Acrobat Sign on the internal Intranet site and comes across the web-based Acrobat Sign Access Tool.

The tool prompts John to enter his email to verify what steps he needs to take in order to get access.

Security Group Details: 
- If the email matches an email on the PowerShell script for members in the required AD security group (dtm_esignature) then this is good! if not he must follow the below steps to request access.
    * Submit a secure request at https://secure.uhc.com for the dtm_esignature global group
    * This group is required because our sync tool (used for automated provisioning) communicates with this group and takes all member credentials (email and name) and creates an account for them in Acrobat Sign if they do not already exist.

Domain Details:
- If the user email entered matches a claimed domain, then the user can access Acrobat Sign, if not they will not be able to access Acrobat Sign.
    * A claimed domain is required because anyone with an email domain that is claimed will be forwarded to our internal Single Sign On authentication process. This is required for security reasons.
    * If you do not have a claimed domain, we would recommend that you meet with our architect to discuss steps to move forward whether that is getting your own contract, creating your own Adobe Acrobat Sign Console, getting email migrated, or not having the ability to use eSign capabilities.

Not in Acrobat Sign Details:
- On rare occasions users will run into an issue where they have followed all the proper provisioning steps but still don't have access to Adobe Acrobat Sign. In this instance it is likely due to being dual entitled.
    * Dual Entitled = Their work email is entitled to a separate instance that is not the UHG instance of Acrobat Sign. This could have happened from signing up for a free trial with their work email or having an old EchoSign account that was purchased and rebranded as Adobe Sign and now Adobe Acrobat Sign.
    * In this case if we run the users inputted email and see that they are part of the security group, they pass the domain check, but their email is not found in a list of Acrobat Sign users then they are dual entitled. We would prompt them to send an email to our operational support mailbox asking that their account be deleted and once done they will be provisioned in Acrobat Sign automatically.

No Send Access Details:
- By default, when a user has the correct domain, has access to the security group, and is not dual entitled they will be provisioned in Acrobat Sign. But that doesn't finish the process and they will by default have limited/no abilities in Acrobat Sign. They will need to contact a group admin to get assigned to their proper group.
    * The issue with this is that most employees don't know who their group admin is or what group they should be a part of. Because of this we have a second input.

2) User input (Colleagues Email)
- For users that are provisioned in Acrobat Sign but have no send access they need to be added to a group to get send access. This is done by a group admin, and as stated above some users don't know their group admin. Therefore, they will need to provide a user’s email which they want to mimic their access. By doing so we will use that email to find a match in our data and see what group that user is in and return the contacts for the group admins they will need to reach out to for access.

Colleague Email Input Details:
- If the user doesn’t have a colleague's email to mimic this may mean that they need to create their own group. We would then direct them to our ticket service where once a ticket is created a ops team member will reach out to kick off a new group creation in Acrobat Sign.
- If the user knows a colleague's email, then they will enter it.
    * If that colleague is in Adobe Acrobat Sign the interface will return a list of group admin contacts and the group name they are in.
    * If that colleague is NOT in Adobe Acrobat Sign, then the interface will notify them that the email does not exist in Acrobat Sign and to enter a different email
--------------------------------------------------------------------

### Technical "flow"

- All eSign data will be either pulled from Active Directory or Adobe Acrobat Sign
- Active Directory data will tell us who is part of the required security group and pull their email, name, and employee ID
- Adobe Sign member data can be pulled through a CSV export or a Rest API tool for development and the MVP will pull the data via a CSV.
    * How the data will be stored is undetermined. It could be stored in a dictionary, array, database table, etc... An exploratory session is required to determine the easiest and most functional approach.

- Version 1: Will be created as python file with user input and console output.
    * Function EmailValidation (){}
        * This function will take the users input and determine if it is a legit email and is formatted correctly
    * Funciton DomainCheck (){}
        * This function will take the user email input parse out just the domain portion and check it against a dataset of all claimed domains.
        * If there is a domain match then move on to run ActiveDirectoryCheck function, Else: prompt the user with a link to open a ticket with the support team to discuss next steps (reference Domain Details in the user flow above).  
    * Function ActiveDirectoryCheck (){}
        * This function will take the user inputted email and check it against a dataset containing a list of active directory users with the specified security group (dtm_esignature).
        * If there is an email match then move on to AcrobatSignAccessCheck, Else: the user needs to follow the required steps to get access.
    * Function AcrobatSignAccessCheck () {}
        * This function will take the user inputted email and check it against a dataset containing a list of users in Adobe Acrobat Sign and collect their group name.
        * If there is an email match AND the user group! = 'default' then they are done, prompt the user with the required link to access Adobe Acrobat Sign and give them a link to training material for how to get started.
        * If there is an email match AND the user group == 'default' then has them enter a colleague’s email to get the appropriate group admin to reach out to for getting added to the needed group.
        * If there is NOT an email match then there are most likely dual entitlement issues. Have them open a ticket with the ops team and supply them verbiage to add to the ticket (ex: Please delete my dual entitled account code:1105)
    * Function ColleagueEmailCheck () {}
        * This function is similar to AcrobatSignAccessCheck but instead if there is a email match it will return all names and emails of the group admins of that users group.
        * If it does not find a match, alert the user and have them try again.

- Version 2: Will be implemented as a web app (tool to marry HTML and python will require a discovery session).
- (Somewhat) unknowns:
    - Will python and html talk to each other, if not can I recreate the code in JavaScript.
    - How will the data be stored (array, dictionary, database, etc.?).
    - How will the webpage be published on the company Intranet (I have a contact for this to work with after I complete my development: Charles Molkentine).
------------------------------------------------------------
