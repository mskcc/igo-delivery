import base64
import sys
import copy
import traceback
from collections import defaultdict
import ssl
import os

import setaccess
import LinkProjectToSamples
from DeliveryHelpers import *
from EmailLogic import *
from DeliveryConstants import emailGroups, emailAddresses

# main function part
# TODO clean code to get rid of all old logic/function that didn't work
# TODO remove dev mode
# TODO put all constant variable into deliveryconstants file
# TODO merge notifier?

class HandleMappings:
    def __init__(self):
        self.nameMapping = {}
        self.groupMapping = {}
        self.addressMapping = {}
    
    def mapEmail(self, email):
        if email in self.nameMapping:
            return self.nameMapping[email]
        return email


class HandleFileBasedMapping(HandleMappings):
    def __init__(self):
        HandleMappings.__init__(self)

    def populate(self):
        self.populateGroupsMapping()
        self.populateAddessesMapping()

    def populateGroupsMapping(self):
        with(open("DeliveryGroups.txt")) as emailGroupLists:
            for line in emailGroupLists:
                groupArray = line.strip("\n").split(":")
                self.groupMapping[groupArray[0]] = groupArray[1].split(",")

    def populateAddessesMapping(self):
        with(open("DeliveryEmails.txt")) as emailAddresses:
            for line in emailAddresses:
                emailArray = line.strip("\n").split(":")
                self.addressMapping[emailArray[0]] = []
                for group in emailArray[1].split(","):
                    self.addressMapping[emailArray[0]] = (
                        self.addressMapping[emailArray[0]] + self.groupMapping[group]
                    )


def mapRecipientLists(emailGroups, emailAddresses):
    emailList = dict()
    for key in emailGroups:
        try:
            # trim whitespaces and split comma-separated string into array
            # chose to keep constants as comma-separated strings to make them easier to edit
            emailGroupsArray = emailGroups[key].replace(" ", "").split(",")
            emailList[key] = []
            for group in emailGroupsArray:
                if group in emailAddresses:
                    emailAdressArray = emailAddresses[group].replace(" ", "").split(",")
                    emailList[key] = emailList[key] + emailAdressArray
                else:
                    # "raw" group, for example, does not have a value, it only needs the standard recipients
                    emailList[key] = emailList[key]
        except:
            e = sys.exc_info()[0]
            print(e)
    return emailList


ssl._create_default_https_context = ssl._create_unverified_context # ?

# change to main function and read command line arguments
mode = "TEST"
if len(sys.argv) > 1:
    mode = sys.argv[1]
elif mode == "TEST":
    deliveryInfo = TestDeliveryInfo()
    notifier = DevEmail()
else:
    deliveryInfo = ProdDeliveryInfo()
    notifier = ProdEmail()

minutes = 30
if len(sys.argv) == 3:
    minutes = sys.argv[2]

print("Email logic running in mode: {}, searching for deliveries for the past {} minutes".format(mode, minutes))

# TODO SHIFT ALL EMAILS TO NEW LOGIC
mapHandler = HandleFileBasedMapping()
mapHandler.populate()
addressMap = mapHandler.addressMapping

newAddressMap = mapRecipientLists(emailGroups, emailAddresses)

with (open("ConnectLimsRest.txt")) as connectInfo:
    username = connectInfo.readline().strip()
    password = connectInfo.readline().strip()
tracker = LinkProjectToSamples.TestTracker()
deliveryInfo.setAliases(aliases)
user_pass = username + ":" + password
deliveries = deliveryInfo.recentDeliveries(base64.standard_b64encode(user_pass.encode('utf-8')), minutes)

for delivered in deliveries:
    try:
        samples = []
        runType = recipe2RunType(delivered.recipe)
        species = delivered.species
        pm = delivered.pm
        for possibleSample in delivered.samples:
            sampleName = possibleSample.fullId()
            if len(possibleSample.passing_runs) > 0 and sampleName not in samples:
                samples.append(sampleName)
        template = getTemplate(runType, delivered, getAllTemplates())
        print("Project: " + delivered.requestId)
        
        # PI and Investigator always start out as recipients
        recipients = list(filter(lambda x: x != "", [delivered.piEmail, delivered.investigatorEmail]))

        # maybe can be deleted
        additionalRecipients = list(filter(lambda mail: mail not in recipients, delivered.dataAccessEmails.lower().split(",")))
        print("recipients {}, additional recipients {}".format(recipients, additionalRecipients))
        recipients = recipients + additionalRecipients
      
        email = determineDataAccessContent(delivered, runType)
        (toList, ccList) = determineDataAccessRecipients(delivered, copy.deepcopy(newAddressMap), recipients)
        if runType == "DLP":
            # query ngs_stats DB for all fastq paths for the project
            request_metadata = setaccess.get_request_metadata(delivered.requestId)
            # from all fastq paths get the fastq.gz folder only (probably 1 folder with all fastq.gz files)
            fastq_directories = set()
            for fastq in request_metadata.fastqs:
                fastq_directories.add(os.path.dirname(fastq))
            sampleDirs = "<br><br>Fastq directories are:<br> {} <br>".format(fastq_directories)
            email["content"] = email["content"] + sampleDirs + FOOTER;
        else:
            sampleList = "<br><br>Samples are:<br>"+"<br>".join(sorted(samples, key=lambda x: int(x.split("_")[-1])))
            email["content"] = email["content"] + sampleList + FOOTER

        notifier.newNotify(runType, delivered, email, toList, ccList)

    except:
        e = sys.exc_info()[0]
        print(e)
        traceback.print_exc(file=sys.stdout)
        try:
             notifier.alert(delivered)
        except NameError:
            fields = defaultdict(str)
            fields["requestId"] = "None"
            delivered = DeliveryDescription(fields)
            notifier.alert(delivered)