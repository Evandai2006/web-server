# Python Web Server
Author @Evan Dai
# Highlighted Features:
Real-time responding console, full auto logging.

Restricted and sensible data protection. A blacklist for normally user unaccessible files, and a whitelist for eligible users who can access those files. Users are recorded as IP addresses. 

Threading control with a variable maximum allowed thread count(preset is 50), comes with a active client table.

Auto restart connection when bad request and other error/exceptions, to avoid one-time unstability.

Auto updated last-modified date with manually configurable time zone settings.
# Get Started:
run the simpleHTMLServer.py to start. Start from the commandline tool or IDE are both acceptable.
(Starting from MacOS and Linux environment isn't tested, and performance isn't guaranteed.)
# About testing pages
the testing pages consists of a series of html webpages and an icon. if not specified, the webpage will be nevigated to index(root.html) upon first access.

the log file(server.log) will be created once the server is running. if already exists, the log will follow the previous record.

please be noted that if it's not your first time accessing the server, it's necessary to clear the record of your web browser to get the response of the server.