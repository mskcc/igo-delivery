import sys
import smtplib
from email.mime.text import MIMEText
from MailStaticStrings import DEFAULT_ADDRESS, NEW_DEFAULT_ADDRESS, SENDER_ADDRESS, SKI_SENDER_ADDRESS

class ProdEmail():
    # TO DEPRECATE
    def notify(self, runType, delivered, text, mainContacts, additionalContacts):
        subjectType = runType
        msg = MIMEText(text)
        msg['Subject'] = "Delivery: " + delivered.userName + " sequencing data - " + subjectType + " project " + delivered.requestId
        msg['From'] = SENDER_ADDRESS
        msg['To'] = ",".join(mainContacts)
        msg['Cc'] = ",".join(additionalContacts)
        s = smtplib.SMTP('localhost')
        s.sendmail(SENDER_ADDRESS, mainContacts + additionalContacts, msg.as_string())
        s.close()
    
    def newNotify(self, runType, delivered, email, mainContacts, additionalContacts):
        msg = MIMEText(email["content"], "html")
        msg['Subject'] = email["subject"]
        msg['From'] = SKI_SENDER_ADDRESS
        msg['To'] = ",".join(mainContacts)
        msg['Cc'] = ",".join(additionalContacts)
        s = smtplib.SMTP('localhost')
        s.sendmail(SKI_SENDER_ADDRESS, mainContacts + additionalContacts, msg.as_string())
        s.close()

    def alert(self, delivered):
        e = sys.exc_info()[0]
        toList = [DEFAULT_ADDRESS] 
        ccList = [DEFAULT_ADDRESS]
        msg = MIMEText("An error occurred for the request " + delivered.requestId + " and user was not notified")
        msg['Subject'] = 'Error in delivery ' + delivered.requestId
        msg['From'] = SENDER_ADDRESS
        msg['To'] = ",".join(toList)
        msg['Cc'] = ",".join(ccList)
        s = smtplib.SMTP('localhost')
        s.sendmail(SENDER_ADDRESS,toList + ccList, msg.as_string())
        s.close()

    def newAlert(self, delivered):
        e = sys.exc_info()[0]
        toList = [NEW_DEFAULT_ADDRESS] 
        ccList = [NEW_DEFAULT_ADDRESS]
        msg = MIMEText("An error occurred for the request " + delivered.requestId + " and user was not notified")
        msg['Subject'] = 'Error in delivery ' + delivered.requestId
        msg['From'] = SKI_SENDER_ADDRESS
        msg['To'] = ",".join(toList)
        msg['Cc'] = ",".join(ccList)
        s = smtplib.SMTP('localhost')
        s.sendmail(SKI_SENDER_ADDRESS,toList + ccList, msg.as_string())
        s.close()

class DevEmail():
    def notify(self, runType, delivered, text, mainContacts, additionalContacts):
        subjectType = runType
        print("-----------")
        print("Subject: Delivery:", delivered.userName, "sequencing data -", subjectType, "project", delivered.requestId)
        print("From", SENDER_ADDRESS)
        print("To", ",".join(mainContacts))
        print("Cc", ",".join(additionalContacts))
        print(text)

    def newNotify(self, runType, delivered, email, mainContacts, additionalContacts):
        print("-----------")
        print("Subject: " + email["subject"])
        print("From", SKI_SENDER_ADDRESS)
        print("To", ",".join(mainContacts))
        print("Cc", ",".join(additionalContacts))
        print(email["content"])

    def alert(self, delivered):
        print(delivered)