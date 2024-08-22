"""Script to find a study hall or commons class for each student and exports to txt file for re-upload into custom fields in PowerSchool.

https://github.com/Philip-Greyson/D118-Studyhall-Field-Population

Looks through enrollments for each student in only the current term, also tries to filter out some duplicate study hall sections that our students have for IEP manager purposes.
Outputs and uploads a .txt file to our SFTP server for AutoComm input into PowerSchool.

See the following pages for the relevant tables used in the queries in this script:
https://ps.powerschool-docs.com/pssis-data-dictionary/latest/cc-4-ver3-6-1
https://ps.powerschool-docs.com/pssis-data-dictionary/latest/terms-13-ver3-6-1
https://ps.powerschool-docs.com/pssis-data-dictionary/latest/students-1-ver3-6-1
"""

# importing module
import datetime  # needed to get current date to check what term we are in
import os  # needed to get environment variables
from datetime import *

import oracledb  # needed for connection to PowerSchool (oracle database)
import pysftp  # needed for sftp file upload

un = os.environ.get('POWERSCHOOL_READ_USER')  # username for read-only database user
pw = os.environ.get('POWERSCHOOL_DB_PASSWORD')  # the password for the database account
cs = os.environ.get('POWERSCHOOL_PROD_DB')  # the IP address, port, and database name to connect to

#set up sftp login info
sftpUN = os.environ.get('D118_SFTP_USERNAME')
sftpPW = os.environ.get('D118_SFTP_PASSWORD')
sftpHOST = os.environ.get('D118_SFTP_ADDRESS')
cnopts = pysftp.CnOpts(knownhosts='known_hosts')  # connection options to use the known_hosts file for key validation

print(f"DBUG: Username: {un} |Password: {pw} |Server: {cs}")  # debug so we can see where oracle is trying to connect to/with
print(f"DBUG: SFTP Username: {sftpUN} |SFTP Password: {sftpPW} |SFTP Server: {sftpHOST}")  # debug so we can see what sftp info is being used for connection
badnames = ['use', 'user', 'teststudent', 'test student', 'testtt', 'testtest', 'karentest', 'tester']

OUTPUT_FILE_NAME = 'studyhalls.txt'
OUTPUT_FILE_DIRECTORY = '/sftp/studyhalls/'
IGNORED_SCHOOLS = ['5']

if __name__ == '__main__':  # main file execution
    with open('studyhall_log.txt', 'w') as log:  # open the logging file
        startTime = datetime.now()
        startTime = startTime.strftime('%H:%M:%S')
        print(f'INFO: Execution started at {startTime}')
        print(f'INFO: Execution started at {startTime}', file=log)
        with oracledb.connect(user=un, password=pw, dsn=cs) as con:  # create the connecton to the database
            with con.cursor() as cur:  # start an entry cursor
                print(f'INFO: Connection established to PS database on version: {con.version}')
                print(f'INFO: Connection established to PS database on version: {con.version}', file=log)
                with open(OUTPUT_FILE_NAME, 'w') as output:  # open the output file
                    today = datetime.now()  # get todays date and store it for finding the correct term later
                    cur.execute('SELECT stu.student_number, stu.dcid, stu.id, stu.schoolid, stu.enroll_status, stu.grade_level, ext.studyhall FROM students stu LEFT JOIN u_def_ext_students0 ext ON stu.dcid = ext.studentsdcid ORDER BY student_number DESC')
                    students = cur.fetchall()
                    for student in students:
                        try:
                            # print('\n' + str(student[0])) # debug
                            studyhall_teacher = ''  # reset to blank every user otherwise might get carryover
                            period = ''
                            idNum = int(student[0])  # what we would refer to as their "ID Number" aka 6 digit number starting with 22xxxx or 21xxxx
                            stuDCID = str(student[1])
                            internalID = int(student[2])  # get the internal id of the student that is referenced in the classes entries
                            schoolID = str(student[3])
                            status = str(student[4])  # active on 0, inactive 1 or 2, 3 for graduated
                            grade = int(student[5])
                            currentStudyhall = str(student[6]) if student[6] else None
                            if status == '0':  # only active students will get processed, otherwise just blanked out
                                # do another query to get their classes, filter to just the current year and only course numbers that contain SH
                                try:
                                     # get a list of terms for the school, filtering to NOT full years
                                    cur.execute("SELECT id, firstday, lastday, schoolid, dcid FROM terms WHERE schoolid = :school ORDER BY dcid DESC", school=schoolID)  # Use bind variables. https://python-oracledb.readthedocs.io/en/latest/user_guide/bind.html#bind
                                    terms = cur.fetchall()
                                    for termEntry in terms:  # go through every term result
                                        # compare todays date to the start and end dates with 2 days before start so it populates before the first day of the term
                                        if ((termEntry[1] - timedelta(days=2) < today) and (termEntry[2] + timedelta(days=1) > today)):
                                            termid = str(termEntry[0])
                                            termDCID = str(termEntry[4])
                                            # print(f'DBUG: Found good term for student {idNum}: term ID {termid} | term DCID {termDCID}')
                                            # print(f'DBUG: Found good term for student {idNum}: term ID {termid} | term DCID {termDCID}', file=log)  # debug
                                            if (grade > 5 and grade < 9):  # process for middle schoolers
                                                # now for each term that is valid, do a query for all their courses that have SH in their course_number
                                                cur.execute("SELECT schoolid, course_number, sectionid, section_number, expression, teacherid FROM cc WHERE instr(course_number, 'SH') > 0 AND studentid = :internalID AND termid = :term ORDER BY course_number", internalID = internalID, term = termid)
                                                userClasses = cur.fetchall()
                                            elif (grade > 8):  # process for high schoolers
                                                # now for each term that is valid, do a query for all their courses that have Commons in their course_number
                                                cur.execute("SELECT schoolid, course_number, sectionid, section_number, expression, teacherid FROM cc WHERE instr(course_number, 'ommons') > 0 AND studentid = :internalID AND termid = :term ORDER BY course_number",  internalID = internalID, term = termid)
                                                userClasses = cur.fetchall()
                                            else:  # if they are a grade schooler we just want to set our results to an empty list to skip them
                                                userClasses = []
                                            # print(len(userClasses), file=log) # debug
                                            if len(userClasses) > 0:  # only process the students who actually get results
                                                if len(userClasses) > 1:  # sometimes students will be in 2 study halls for IEP purposes. HS students can also have more than 1 commons but we ignore that
                                                    print(f'WARN: Student {idNum} has more than one study hall listed, finding correct one')
                                                    print(f'WARN: Student {idNum} has more than one study hall listed, finding correct one', file=log)
                                                    for classEntry in userClasses:
                                                        if 'IN' not in str(classEntry[1]):  # the extra studyhalls have a 'IN' after their normal course number
                                                            teacherID = str(classEntry[5])  # store the unique id of the teacher
                                                            sectionID = str(classEntry[2])  # store the unique id of the section, used to get classroom number later
                                                            # print (classEntry) # debug
                                                            # print (classEntry, file=log)  # debug
                                                else:
                                                    for classEntry in userClasses:
                                                        teacherID = str(classEntry[5])  # store the unique id of the teacher
                                                        sectionID = str(classEntry[2])  # store the unique id of the section, used to get classroom number later
                                                        # print (classEntry) # debug
                                                        # print (classEntry, file=log)  # debug

                                                cur.execute("SELECT users_dcid FROM schoolstaff WHERE id = :teacherID", teacherID = teacherID)  # get the user dcid from the teacherid in schoolstaff
                                                schoolStaffInfo = cur.fetchall()
                                                teacherDCID = str(schoolStaffInfo[0][0])  # just get the result directly without converting to list or doing loop

                                                cur.execute("SELECT last_name, first_name FROM users WHERE dcid = :teacherDCID", teacherDCID = teacherDCID)
                                                teacherName = cur.fetchall()
                                                last = str(teacherName[0][0])
                                                first = str(teacherName[0][1])
                                                studyhall_teacher = last + ', ' + first[0:1]  # take their last name and join to first initial

                                                # now that we found the studyhall and teacher name, also get the room number & period
                                                cur.execute("SELECT room, expression FROM sections WHERE id = :section", section = sectionID)  # get the room number assigned to the sectionid correlating to our home_room
                                                sectionInfo = cur.fetchall()
                                                studyhall_number = str(sectionInfo[0][0])
                                                period = str(sectionInfo[0][1])

                                                print(f'DBUG: Student: {idNum} | Term ID: {termid} | Studyhall teacher: {studyhall_teacher} | Room: {studyhall_number} | Period: {period}')  # debug
                                                print(f'DBUG: Student: {idNum} | Term ID: {termid} | Studyhall teacher: {studyhall_teacher} | Room: {studyhall_number} | Period: {period}', file=log)  # debug

                                                # do final output, but only if it is different than whats already there
                                                if currentStudyhall != (studyhall_teacher + ' - ' + period):
                                                    if schoolID not in IGNORED_SCHOOLS:
                                                        print(f'{idNum}\t{studyhall_teacher} - {period}', file=output)  # Do final output to txt file
                                                    else:
                                                        print(f'WARN: Student {idNum} at school {schoolID} currently has study hall listed as {currentStudyhall} but found new study hall {studyhall_teacher}')
                                                        print(f'WARN: Student {idNum} at school {schoolID} currently has study hall listed as {currentStudyhall} but found new study hall {studyhall_teacher}', file=log)
                                            else:
                                                print(f'DBUG: Student: {idNum} - No study halls or commons found for term {termid}')
                                                print(f'DBUG: Student: {idNum} - No study halls or commons found for term {termid}', file=log)

                                except Exception as er:
                                    print(f'ERROR getting courses for student {idNum}: {er} ')
                                    print(f'ERROR getting courses for student {idNum}: {er} ', file=log)

                            else:  # inactive students
                                if currentStudyhall != None:
                                    print(f'{idNum}\t', file=output)

                        except Exception as er:
                            print(f'ERROR while processing student {student[0]} : {er}')
                            print(f'ERROR while processing student {student[0]} : {er}', file=log)

        #after all the output file is done writing and now closed, open an sftp connection to the server and place the file on there
        with pysftp.Connection(sftpHOST, username=sftpUN, password=sftpPW, cnopts=cnopts) as sftp:
            print(f'INFO: SFTP connection established to {sftpHOST}')
            print(f'INFO: SFTP connection established to {sftpHOST}', file=log)
            # print(sftp.pwd)  # debug to show current directory
            # print(sftp.listdir())  # debug to show files and directories in our location
            sftp.chdir(OUTPUT_FILE_DIRECTORY)
            # print(sftp.pwd) # debug to show current directory
            # print(sftp.listdir())  # debug to show files and directories in our location
            sftp.put(OUTPUT_FILE_NAME)  # upload the file onto the sftp server
            print(f"INFO: Study hall file placed on remote server for {today}")
            print(f"INFO: Study hall file placed on remote server for {today}", file=log)
