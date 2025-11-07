This yet to be named application is intended to help civic groups like local political parties, special interest groups, community service organizations, Political Action Committees, etc.

Some of the primary features are:

- Member management 
    - status (active/inactive )
    - Dues tracking 
    - Certification/ credential tracking 
    - Training tracking (not a full training management but just a status track. Ex: taken, hasn’t taken, expired, failed, etc )
    - Contact details 
    - Profile 
    - Photo
    - 
- voter/contact databases 
    - vote history 
    - Contact information 
    - Voter registration status 
    - Photo
    - Profile
- multiple Calendars 
    - both public and private 
    - Subscribe links (caldav, .ics, etc) for mobile and other devices.
- Document management
    - both public and private docs
    - Private docs should have fine grained role based access controls 
    - Public docs should have at least two ways to share one way is an easy to find somehow listen on the website option and then a long, random hash string of a URL for private link sharing
    - Full text search
    - Knowledge graph search
    - Vector based search
    - Grouping of dock related documents by tag and or category or file type.
- link redirects 
    - functions similar to a URL shortener service 
    - Has analytics for hit/click tracking. 
- Basic CMS
    - pages
    - Multiple blogs/news
    - Configurable navigation menus (top navbar, footer links, etc)
    - customizable footer text, icons, etc
    - Multiple page/post layouts
- Newsletter 
- Elected official database 
- Government/quasi-government database 
- Photo management 
- task management 
    - Team/group tasks 
    - Individual tasks 
- Robust GIS system 
    - point tracking for addresses, events, etc. For example: where a polling place is. 
    - Polygons for areas. For example: ingesting shapefiles from government sources of election districts. 
    - Public and private sharing of maps with collections of geo types. This includes both web maps as well as standard formats for GIS data like KML/KMZ (linked or static ), shapefiles, geojson, WMS, etc.

Any data types like location, document, photo, author, person, etc should be shared. For example a member, voter, and elected official are all persons. A person could be all 3 of those things. This is to prevent data duplication and maintain relational data between entities. 

The application should be modular with as much functionality in optionally installed packages. Installed packages should be able to be enabled or disabled (not uninstalled) from the UI by a user with sufficient privileges. 

The application should function as a Software as a Service. As such it needs to support multiple organizations, each with their own staff, content, etc.

Even though this is primarily a SaaS product, it will be open source and should be easily installable for self hosting. 

There should be an administrative organization for the company that is hosting, running, and administering the overall system. 

The system should track resource usage and infrastructure cost so that organizations can be optionally be billed for their usage. For example, each photo will need to be stored. There will be some cost associated with that (like S3, CloudFlare images, etc). Members with appropriate permissions, of the administrative organization, should then be able to enable billing, with an options for direct costs only, costs + % of margin, or flat rate. 

The app will have similar features as a business Customer Relationship Management (CRM) tool.

The Ghost publishing platform (open source and SaaS) is a good example of how the blog/newsletter functions should work. 

Pages and blog/news posts should be able to be private or public. Private posts should have role based access controls. An example of this would be a post that is only available to member who have paid dues, active, or have some special training. 

The web user interface should be just as functional, accessible, and attractive on a mobile device like a phone or tablet, as it is on a computer screen. 

The backend should be API first with all UIs calling the API. The UIs shouldn’t have any special access points that are not part of a fully documented and standardized API. Only exception to this rule is if there is a built in management UI for debugging, similar to Django’s built in admin interface. 

Organizations should have the option to use common standards for Authentication, authorization, and provisioning their uses such as SCIM and SAML. Organizational admins should be able to enable or disable this for their own organizations. 

Tasks should be able to be assigned to groups and individuals in a hierarchy. An example would be assigning a team a list of people to call or addresses to visit, then the team administrators can then assign tasks to team members. 


