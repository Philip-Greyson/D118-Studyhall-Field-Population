
# D118-Studyhall-Field-Population

Finds the study hall or commons section for a student in the current term, finds the teacher and classroom information, aand exports it to a .txt file that is placed on our SFTP server for upload into PowerSchool.

## Overview

The script first does a query for all students in PowerSchool getting the basic information that is needed to find their courses like school, grade level, internal ID, etc.
The students are then processed one at a time, the current date is compared to terms from the terms table to find one that is currently active. Once a valid term is found, a query is made for courses that either contain "SH" (study hall) or "Commons" depending on grade level. In our setup, some students may have more than one SH class that has a .IN after it, so if there is more than one result for classes those are filtered out. Otherwise, any classes that match are processed further, finding the section and teacher ID which is then used to find the teacher's first and last name as well as the room number from the users and sections table respectively. If the student is inactive or does not have a study hall/commons the field is just left blank.

Then it takes the data and exports it to a tab delimited .txt file, which is then uploaded via SFTP to our local server where it will be imported into PowerSchool custom fields from.

## Requirements

The following Environment Variables must be set on the machine running the script:

- POWERSCHOOL_READ_USER
- POWERSCHOOL_DB_PASSWORD
- POWERSCHOOL_PROD_DB
- D118_SFTP_USERNAME - *This can be replaced with an environment variable of the username of your specific SFTP server*
- D118_SFTP_PASSWORD - *This can be replaced with an environment variable of the password of your specific SFTP server*
- D118_SFTP_ADDRESS - *This can be replaced with an environment variable of the host address of your specific SFTP server*

These are fairly self explanatory, and just relate to the usernames, passwords, and host IP/URLs for PowerSchool and the output SFTP server. If you wish to directly edit the script and include these credentials, you can.

Additionally, the following Python libraries must be installed on the host machine (links to the installation guide):

- [Python-oracledb](https://python-oracledb.readthedocs.io/en/latest/user_guide/installation.html)
- [pysftp](https://pypi.org/project/pysftp/)

**As part of the pysftp connection to the output SFTP server, you must include the server host key in a file** with no extension named "known_hosts" in the same directory as the Python script. You can see [here](https://pysftp.readthedocs.io/en/release_0.2.9/cookbook.html#pysftp-cnopts) for details on how it is used, but the easiest way to include this I have found is to create an SSH connection from a linux machine using the login info and then find the key (the newest entry should be on the bottom) in ~/.ssh/known_hosts and copy and paste that into a new file named "known_hosts" in the script directory.

You will also need a SFTP server running and accessible that is able to have files written to it in the directory /sftp/studyhalls/ or you will need to customize the script (see below). That setup is a bit out of the scope of this readme.
In order to import the information into PowerSchool, a scheduled AutoComm job should be setup, that uses the managed connection to your SFTP server, and imports into student_number, and whichever custom fields you need based on the data, using tab as a field delimiter, LF as the record delimiter with the UTF-8 character set.

## Customization

This script is very customized to our school district as it uses searches for specific course "numbers" which correlate to our study halls and commons at certain grade levels. It will require a bit of coding to change this to work with your specific district, but some things you will likely want to change are listed below:

- If your students have different grade level breakpoints where they will have study halls vs commons, look to edit the `if (grade > 5 and grade < 9)` and `elif (grade > 8)` blocks to fit your grades
- If you need to ignore a building from the output for some reason, add its PowerSchool school ID to the `IGNORED_SCHOOLS` list as a string.
- Inside those if statements, you will want to edit the SQL query, specifically the `WHERE instr(course_number, 'SH')` and change the 'SH'/'ommons' to match the name of your courses.
- You will also probably want to change or remove the block that has `if len(userClasses) > 1` where I ignore classes that have 'IN' in them as those are our duplicate study halls for IEP meeting purposes.
- You can change the filename and output SFTP directory by editing `OUTPUT_FILE_NAME` and `OUTPUT_FILE_DIRECTORY`, and then setup PowerSchool for the import.
