# Script to find a study hall/commons class for each student
# Looks at only the current term(s) and tries to filter out the duplicate SHs that some students have for IEP manager purposes
# Outputs to a file and uploads to sftp server for autocomm into PS overnight

# See the following for table information
# https://docs.powerschool.com/PSDD/powerschool-tables/cc-4-ver3-6-1
# https://docs.powerschool.com/PSDD/powerschool-tables/terms-13-ver3-6-1
# https://docs.powerschool.com/PSDD/powerschool-tables/students-1-ver3-6-1

# importing module
import oracledb # needed for connection to PowerSchool (oracle database)
import sys # needed for non scrolling text output
import datetime # needed to get current date to check what term we are in
import os # needed to get environment variables
import pysftp # needed for sftp file upload
from datetime import *

un = 'PSNavigator' #PSNavigator is read only, PS is read/write
pw = os.environ.get('POWERSCHOOL_DB_PASSWORD') #the password for the PSNavigator account
cs = os.environ.get('POWERSCHOOL_PROD_DB') #the IP address, port, and database name to connect to

#set up sftp login info
sftpUN = os.environ.get('D118_SFTP_USERNAME')
sftpPW = os.environ.get('D118_SFTP_PASSWORD')
sftpHOST = os.environ.get('D118_SFTP_ADDRESS')
cnopts = pysftp.CnOpts(knownhosts='known_hosts') # connection options to use the known_hosts file for key validation

print("Username: " + str(un) + " |Password: " + str(pw) + " |Server: " + str(cs)) #debug so we can see where oracle is trying to connect to/with
print("SFTP Username: " + str(sftpUN) + " |SFTP Password: " + str(sftpPW) + " |SFTP Server: " + str(sftpHOST)) #debug so we can see what credentials are being used

# create the connecton to the database
with oracledb.connect(user=un, password=pw, dsn=cs) as con:
    with con.cursor() as cur:  # start an entry cursor
        with open('studyhall_log.txt', 'w') as outputLog:  # open the logging file
            with open('studyhalls.txt', 'w') as output: # open the output file
                print("Connection established: " + con.version)
                print("Connection established: " + con.version, file=outputLog)
                today = datetime.now() #get todays date and store it for finding the correct term later
                print("today = " + str(today))  # debug
                print("today = " + str(today), file=outputLog)  # debug

                cur.execute('SELECT student_number, dcid, id, schoolid, enroll_status, grade_level FROM students ORDER BY student_number DESC')
                rows = cur.fetchall()
                for count, student in enumerate(rows):
                    try:
                        sys.stdout.write('\rProccessing student entry %i' % count) # sort of fancy text to display progress of how many students are being processed without making newlines
                        sys.stdout.flush()
                        # print('\n' + str(student[0])) # debug
                        studyhall_teacher = ''  # reset to blank every user otherwise might get carryover
                        period = ''
                        idNum = int(student[0]) #what we would refer to as their "ID Number" aka 6 digit number starting with 22xxxx or 21xxxx
                        stuDCID = str(student[1])
                        internalID = int(student[2]) #get the internal id of the student that is referenced in the classes entries
                        schoolID = str(student[3])
                        status = str(student[4]) #active on 0, inactive 1 or 2, 3 for graduated
                        grade = int(student[5])
                        if status == '0': # only active students will get processed, otherwise just blanked out
                            #do another query to get their classes, filter to just the current year and only course numbers that contain SH
                            try:
                                cur.execute("SELECT id, firstday, lastday, schoolid, dcid FROM terms WHERE schoolid = " + schoolID + " ORDER BY dcid DESC")  # get a list of terms for the school, filtering to not full years
                                terms = cur.fetchall()
                                for termEntry in terms:  # go through every term result
                                    #compare todays date to the start and end dates with 2 days before start so it populates before the first day of the term
                                    if ((termEntry[1] - timedelta(days=2) < today) and (termEntry[2] + timedelta(days=1) > today)):
                                        termid = str(termEntry[0])
                                        termDCID = str(termEntry[4])
                                        # print("Found good term for student " + str(idNum) + ": " + termid + " | " + termDCID)
                                        print("Found good term for student " + str(idNum) + ": " + termid + " | " + termDCID, file=outputLog)
                                        if (grade > 5 and grade < 9): # process for middle schoolers
                                            # now for each term that is valid, do a query for all their courses that have SH in their course_number
                                            cur.execute("SELECT schoolid, course_number, sectionid, section_number, expression, teacherid FROM cc WHERE instr(course_number, 'SH') > 0 AND studentid = " + str(internalID) + " AND termid = " + termid + " ORDER BY course_number")
                                            userClasses = cur.fetchall()
                                        elif (grade > 8): # process for high schoolers
                                            # now for each term that is valid, do a query for all their courses that have Commons in their course_number
                                            cur.execute("SELECT schoolid, course_number, sectionid, section_number, expression, teacherid FROM cc WHERE instr(course_number, 'Commons') > 0 AND studentid = " + str(internalID) + " AND termid = " + termid + " ORDER BY course_number")
                                            userClasses = cur.fetchall()
                                        else: # if they are a grade schooler we just want to set our results to an empty list to skip them
                                            userClasses = []
                                        # print(len(userClasses), file=outputLog) # debug
                                        if len(userClasses) > 0: # only process the students who actually get results 
                                            if len(userClasses) > 1: # sometimes students will be in 2 study halls for IEP purposes. HS students can also have more than 1 commons but we ignore that
                                                print('Student ' + str(idNum) + ' has more than one study hall listed, finding correct one', file=outputLog)
                                                for classEntry in userClasses:
                                                    if 'IN' not in str(classEntry[1]): # the extra studyhalls have a 'IN' after their normal course number
                                                        teacherID = str(classEntry[5]) #store the unique id of the teacher
                                                        sectionID = str(classEntry[2]) #store the unique id of the section, used to get classroom number later
                                                        # print (classEntry) # debug
                                                        print (classEntry, file=outputLog) # debug
                                            else:
                                                for classEntry in userClasses:
                                                    teacherID = str(classEntry[5]) #store the unique id of the teacher
                                                    sectionID = str(classEntry[2]) #store the unique id of the section, used to get classroom number later
                                                    # print (classEntry) # debug
                                                    print (classEntry, file=outputLog) # debug

                                            cur.execute("SELECT users_dcid FROM schoolstaff WHERE id = " + teacherID) #get the user dcid from the teacherid in schoolstaff
                                            schoolStaffInfo = cur.fetchall()
                                            teacherDCID = str(schoolStaffInfo[0][0]) #just get the result directly without converting to list or doing loop

                                            cur.execute("SELECT last_name, first_name FROM users WHERE dcid = " + teacherDCID)
                                            teacherName = cur.fetchall()
                                            last = str(teacherName[0][0])
                                            first = str(teacherName[0][1])
                                            studyhall_teacher = last + ', ' + first[0:1] # take their last name and join to first initial

                                            #now that we found the studyhall and teacher name, also get the room number & period
                                            cur.execute("SELECT room, expression FROM sections WHERE id = " + sectionID) #get the room number assigned to the sectionid correlating to our home_room
                                            sectionInfo = cur.fetchall()
                                            studyhall_number = str(sectionInfo[0][0])
                                            period = str(sectionInfo[0][1])

                                            print('Student: ' + str(idNum) + ' | Studyhall teacher: ' + studyhall_teacher + ' |Room: ' + studyhall_number + ' |Period: ' + period, file=outputLog) # debug
                            except Exception as er:
                                print('Error getting courses on ' + str(idNum) + ': ' + str(er))
                        if(studyhall_teacher != ''): # have two cases so we can have fancier formatting for results while still blanking out students without
                            print(str(idNum) + '\t' + studyhall_teacher + ' - ' + period, file=output)
                        else:
                            print(str(idNum) + '\t' + '', file=output)

                    except Exception as er:
                        print('Error on ' + str(student[0]) + ': ' + str(er))
                print('') # spacer after the sys.stdout

            #after all the output file is done writing and now closed, open an sftp connection to the server and place the file on there
            with pysftp.Connection(sftpHOST, username=sftpUN, password=sftpPW, cnopts=cnopts) as sftp:
                print('SFTP connection established')
                print('SFTP connection established', file=outputLog)
                # print(sftp.pwd)  # debug to show current directory
                # print(sftp.listdir())  # debug to show files and directories in our location
                sftp.chdir('/sftp/studyhalls/')
                # print(sftp.pwd) # debug to show current directory
                # print(sftp.listdir())  # debug to show files and directories in our location
                sftp.put('studyhalls.txt') #upload the file onto the sftp server
                print("Schedule file placed on remote server for " + str(today))
                print("Schedule file placed on remote server for " + str(today), file=outputLog)
