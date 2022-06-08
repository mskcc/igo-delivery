import datetime
import json
import urllib.request
import sys
import smtplib
from email.mime.text import MIMEText
from DeliveryConstants import NO_PM, MSKCC_ADDRESS, DEFAULT_ADDRESS, SKI_SENDER_ADDRESS


class SampleDescription:
   def __init__(self, queryDict):
        self.cmoId = queryDict["cmoId"]
        self.sampleId = queryDict["baseId"]
        self.passing_runs = []
        self.passing_dates = {}
        if "basicQcs" not in queryDict:
            print(queryDict)
            queryDict["basicQcs"] = []
        for qcStatus in queryDict["basicQcs"]:
            if qcStatus["qcStatus"] != "Under-Review" and not qcStatus["qcStatus"].startswith("Failed"):
                self.passing_runs = qcStatus["run"]
                if "reviewedDates" in qcStatus:
                    self.passing_dates[qcStatus["run"]] = max([x["timestamp"] for x in qcStatus["reviewedDates"]]) 
   def fullId(self):
        return self.cmoId + "_IGO_" + self.sampleId


class DeliveryDescription:
    def __init__(self, queryDict):
        self.requestId = queryDict["requestId"]
        self.pm = ""
        if "projectManager" in queryDict and queryDict["projectManager"] != NO_PM:
            self.pm = queryDict["projectManager"]
        self.analysisRequested = queryDict["analysisRequested"]
        self.deliveryDate = queryDict["deliveryDate"]
        self.analysisType = ""
        if "analysisType" in queryDict:
            self.analysisType = queryDict["analysisType"]
        self.samples = []
        self.recipe = ""
        self.species = ""
        self.projectName = ""
        for sample in queryDict["samples"]:
            self.samples.append(SampleDescription(sample))
            if "recipe" in sample and sample["recipe"] != "":
                self.recipe = sample["recipe"]
            if "species" in sample and sample["species"] != "":
                self.species = sample["species"]
        self.piEmail = ""
        self.investigatorEmail = ""
        self.additionalEmails = ""
        self.dataAccessEmails = ""
        self.userName = ""

    def setUserName(self, nicknameMapping):
        userName = self.piEmail.split("@")[0]
        institute = "UNKNOWN"
        if "@" in self.piEmail:
            institute = self.piEmail.split("@")[1]
        if institute != "mskcc.org": #sometimes people use their ski address in submission but the samba link is off their mskcc address
            userName = MSKCC_ADDRESS
            if institute == "ski.mskcc.org" and self.piEmail in nicknameMapping:
                userName = nicknameMapping[self.piEmail]
                print("NEW USERNAME:" + userName)
        self.userName = userName


class DeliveryInfo:
    def __init__(self):
        self.server = "https://igolims.mskcc.org:8443/LimsRest"
        self.deliveryDescriptions = []
    
    def recentDeliveries(self, base64string, minutes):
        print(datetime.datetime.now())
        hdr = {'Authorization': "Basic %s" % base64string.decode('utf-8')}
        url = self.server + "/getRecentDeliveries?time="+str(minutes)+"&units=m"
        print("Getting recent deliveries: " + url)
        req = urllib.request.Request(url, headers=hdr)
        response = urllib.request.urlopen(req)
        deliveries = json.loads(response.read())
        for delivery in deliveries:
            deliveryDescription = DeliveryDescription(delivery)
            emailDetails = self.getEmailDetails(deliveryDescription.requestId, base64string)
            deliveryDescription.piEmail = emailDetails["piEmail"]
            deliveryDescription.investigatorEmail = emailDetails["investigatorEmail"]
            deliveryDescription.additionalEmails = emailDetails["additionalEmails"]
            deliveryDescription.dataAccessEmails = emailDetails["dataAccessEmails"]
            deliveryDescription.projectName = emailDetails["projectName"]
            deliveryDescription.setUserName(self.skiMapping)
            self.deliveryDescriptions.append(deliveryDescription)
        return self.deliveryDescriptions

    def getEmailDetails(self, proj, base64string):
        requestQuery = self.server + "/getProjectDetailed?project=" + proj
        print("Getting Project Details: " + requestQuery)
        detReq = urllib.request.Request(requestQuery)
        detReq.add_header("Authorization", "Basic %s" % base64string.decode('utf-8'))
        detReq.add_header("Content-Type", "application/json")
        detailResponse = urllib.request.urlopen(detReq)
        details = json.loads(detailResponse.read())
        emailDetails = {}
        try:
            emailDetails["piEmail"] = details["detailedRequests"][0]["piEmail"].lower()
        except KeyError:
            emailDetails["piEmail"] = DEFAULT_ADDRESS
        try:
            emailDetails["investigatorEmail"] = details["detailedRequests"][0]["investigatorEmail"].lower()
        except KeyError:
            emailDetails["investigatorEmail"] = ""
        try:
            emailDetails["additionalEmails"] = details["detailedRequests"][0]["mailTo"].lower()
        except KeyError:
            emailDetails["additionalEmails"] = ""
        try:
            emailDetails["dataAccessEmails"] = details["detailedRequests"][0]["dataAccessEmails"].lower()
        except KeyError:
            emailDetails["dataAccessEmails"] = ""
        try:
            emailDetails["projectName"] = details["projectName"]
        except KeyError:
            emailDetails["projectName"] = ""
        return emailDetails

    def setAliases(self, aliases):
        self.skiMapping = aliases

class ProdEmail():
    def notify(self, runType, delivered, email, mainContacts, additionalContacts):
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
        msg['From'] = SKI_SENDER_ADDRESS
        msg['To'] = ",".join(toList)
        msg['Cc'] = ",".join(ccList)
        s = smtplib.SMTP('localhost')
        s.sendmail(SKI_SENDER_ADDRESS,toList + ccList, msg.as_string())
        s.close()

class TestEmail():
    def notify(self, runType, delivered, email, mainContacts, additionalContacts):
        print("-----------")
        print("Subject: " + email["subject"])
        print("From", SKI_SENDER_ADDRESS)
        print("To", ",".join(mainContacts))
        print("Cc", ",".join(additionalContacts))
        print(email["content"])

    def alert(self, delivered):
        print(delivered)
