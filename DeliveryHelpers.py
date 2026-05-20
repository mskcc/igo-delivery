import datetime
import json
import urllib.request
import sys
import smtplib
from email.mime.text import MIMEText
from DeliveryConstants import NO_PM, MSKCC_ADDRESS, DEFAULT_ADDRESS, SKI_SENDER_ADDRESS
from splunk_logging import setup_logging

logger = setup_logging("DeliveryHelpers")


class SampleDescription:
   def __init__(self, queryDict):
        self.cmoId = queryDict.get("cmoId") or ""
        self.sampleId = queryDict.get("baseId") or ""
        self.passing_runs = []
        self.passing_dates = {}
        if not self.cmoId or not self.sampleId:
            logger.warning(
                "Sample missing required ids (cmoId=%r, baseId=%r); record: %s",
                self.cmoId, self.sampleId, queryDict
            )
        if "basicQcs" not in queryDict:
            logger.warning("No basicQcs in queryDict for sample %s: %s", self.sampleId, queryDict)
            queryDict["basicQcs"] = []
        for qcStatus in queryDict["basicQcs"]:
            status = qcStatus.get("qcStatus", "")
            run = qcStatus.get("run", "")
            if status and status != "Under-Review" and not status.startswith("Failed"):
                self.passing_runs = run
                reviewed = qcStatus.get("reviewedDates") or []
                if reviewed:
                    self.passing_dates[run] = max(x["timestamp"] for x in reviewed if "timestamp" in x)

   def fullId(self):
        return self.cmoId + "_IGO_" + self.sampleId


class DeliveryDescription:
    def __init__(self, queryDict):
        self.requestId = queryDict.get("requestId", "")
        if not self.requestId:
            logger.warning("Delivery missing requestId: %s", queryDict)
        self.pm = ""
        pm = queryDict.get("projectManager")
        if pm and pm != NO_PM:
            self.pm = pm
        self.analysisRequested = queryDict.get("analysisRequested", False)
        self.deliveryDate = queryDict.get("deliveryDate")
        self.analysisType = queryDict.get("analysisType", "")
        self.samples = []
        self.recipe = ""
        self.species = ""
        self.projectName = ""
        for sample in queryDict.get("samples") or []:
            try:
                self.samples.append(SampleDescription(sample))
            except Exception as e:
                logger.exception(
                    "Skipping unparseable sample in request %s: %s (sample=%s)",
                    self.requestId, e, sample
                )
                continue
            if sample.get("recipe"):
                self.recipe = sample["recipe"]
            if sample.get("species"):
                self.species = sample["species"]
        self.piEmail = ""
        self.investigatorEmail = ""
        self.additionalEmails = ""
        self.dataAccessEmails = ""
        self.userName = ""
        self.requestType = queryDict.get("requestType", "")
        self.isNeoAg = queryDict.get("isNeoAg", False)

    def setUserName(self, nicknameMapping):
        userName = self.piEmail.split("@")[0]
        institute = "UNKNOWN"
        if "@" in self.piEmail:
            institute = self.piEmail.split("@")[1]
        if institute != "mskcc.org": #sometimes people use their ski address in submission but the samba link is off their mskcc address
            userName = MSKCC_ADDRESS
            if institute == "ski.mskcc.org" and self.piEmail in nicknameMapping:
                userName = nicknameMapping[self.piEmail]
                logger.info("NEW USERNAME: %s", userName)
        self.userName = userName


class DeliveryInfo:
    def __init__(self):
        self.server = "https://igolims.mskcc.org:8443/LimsRest"
        self.deliveryDescriptions = []
    
    def recentDeliveries(self, base64string, minutes):
        logger.info("Current time: %s", datetime.datetime.now())
        hdr = {'Authorization': "Basic %s" % base64string.decode('utf-8')}
        url = self.server + "/getRecentDeliveries?time="+str(minutes)+"&units=m"
        logger.info("Getting recent deliveries: %s", url)
        req = urllib.request.Request(url, headers=hdr)
        response = urllib.request.urlopen(req)
        deliveries = json.loads(response.read())
        for delivery in deliveries:
            requestId = delivery.get("requestId", "<unknown>")
            try:
                deliveryDescription = DeliveryDescription(delivery)
                emailDetails = self.getEmailDetails(deliveryDescription.requestId, base64string)
                deliveryDescription.piEmail = emailDetails["piEmail"]
                deliveryDescription.investigatorEmail = emailDetails["investigatorEmail"]
                deliveryDescription.additionalEmails = emailDetails["additionalEmails"]
                deliveryDescription.dataAccessEmails = emailDetails["dataAccessEmails"]
                deliveryDescription.projectName = emailDetails["projectName"]
                deliveryDescription.setUserName(self.skiMapping)
                self.deliveryDescriptions.append(deliveryDescription)
            except Exception as e:
                logger.exception(
                    "Skipping delivery %s after error: %s", requestId, e
                )
                continue
        return self.deliveryDescriptions

    def getEmailDetails(self, proj, base64string):
        requestQuery = self.server + "/getProjectDetailed?project=" + proj
        logger.info("Getting Project Details: %s", requestQuery)
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
        logger.info("-----------")
        logger.info("Subject: %s", email["subject"])
        logger.info("From: %s", SKI_SENDER_ADDRESS)
        logger.info("To: %s", ",".join(mainContacts))
        logger.info("Cc: %s", ",".join(additionalContacts))
        logger.info("Content: %s", email["content"])

    def alert(self, delivered):
        logger.error("Alert for delivery: %s", delivered)
