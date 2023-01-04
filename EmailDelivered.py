import base64
import sys
import copy
import traceback
from collections import defaultdict
import ssl
import os
import jinja2
import setaccess
import LinkProjectToSamples
import DeliveryConstants
from DeliveryHelpers import *
import setaccess

def recipe2RunType(recipe):
    runType = recipe
    if (
        runType == "WholeExome-KAPALib"
        or runType == "WholeExomeSequencing"
        or runType == "Agilent_v4_51MB_Human"
        or runType == "IDT_Exome_v1_FP"
        or runType == "IDT_Exome_v2_FP_Viral_Probes"
    ):
        runType = "WESAnalysis"
    if runType == "Agilent_MouseAllExonV1":
        runType = "WESAnalyis-Mouse"
    return runType

# add additional recipients based on project(05500 only), RunType(updated base on recipe by recipe2RunType) and analysis type
def determineDataAccessRecipients(deliveryDesc, recipients, runType, addressMap):
    toList = recipients
    # standard email ccList only contains ski_igo_delivery group
    ccList = addressMap['standard']
    analysisType = deliveryDesc.analysisType
    runType = runType.upper()
    # BY PROJECT
    if "05500" in deliveryDesc.requestId:
        ccList += addressMap["ski"]
    # BY RECIPE
    elif (("IMPACT" in runType or "HEMEPACT" in runType) and "M-" not in runType) or "CAS" in analysisType:
        ccList += addressMap['impact']
    elif "ACCESS" in runType:
        ccList += addressMap["access"]
    elif "CMO-CH" in runType:
        ccList += addressMap["CMO-CH"]
    elif "TCRSEQ" in runType:
        ccList += addressMap["TCRSeq"]
    # WES WITH CCS ANALYSIS ?
    elif "WES" in runType and "CCS" in analysisType:
        ccList += addressMap['wesWithCCS']
    # BY ANALYSIS TYPE
    elif "BIC" in analysisType:
        ccList += addressMap['pipelineDefault']
    elif "CCS" in analysisType:
        ccList += addressMap['ccs']

    return (toList, ccList)

def determineDataAccessContent(deliveryDesc, runType):
    analysisType = deliveryDesc.analysisType
 
    # replace all different versions of WES recipe with WholeExomeSequencing
    runType = runType.upper()
    if runType == "WESANALYSIS":
        recipe = "WholeExomeSequencing"
    else:
        recipe = deliveryDesc.recipe
    
    email = {
        "content": "",
        "subject": (
            DeliveryConstants.genericSubject
            % (recipe, deliveryDesc.requestId)
        ),
    }

    # generate email content using different templates based on runtype and analysis type

    # BY RunType
    if (("IMPACT" in runType or "HEMEPACT" in runType) and "M-" not in runType) or "CAS" in analysisType:
        email["content"] = (DeliveryConstants.impactContent) % ( 
            recipe,
            deliveryDesc.requestId,
            deliveryDesc.userName
            )
    elif "ACCESS" in runType or "CMO-CH" in runType:
        email["content"] = (DeliveryConstants.accessContent) % (
            recipe,
            deliveryDesc.requestId,
            deliveryDesc.userName
        )

    # BY ANALYSIS TYPE
    elif "WES" in runType and "CCS" in analysisType:
        email["content"] = (DeliveryConstants.wesWithCCSContent) % (
            recipe,
            deliveryDesc.requestId,
            deliveryDesc.userName
        )
    elif analysisType == "FASTQ ONLY":
        # check whether the investigator is within MSK or not
        if deliveryDesc.userName != "YOUR_MSKCC_ADDRESS":
            email["content"] = DeliveryConstants.genericContent % (
                recipe,
                deliveryDesc.requestId,
                deliveryDesc.userName,
            )
        else:
            email["content"] = DeliveryConstants.nonMSKContent % (
                recipe,
                deliveryDesc.requestId,
                deliveryDesc.piEmail,
            )
    # Analysis catchall
    elif analysisType != "":
        email["content"] = (DeliveryConstants.genericAnalysisContent) % (
            recipe,
            deliveryDesc.requestId,
            deliveryDesc.userName
        )

    # NO RULE APPLIED
    else:
        # check whether the investigator is within MSK or not
        if deliveryDesc.userName != "YOUR_MSKCC_ADDRESS":
            email["content"] = DeliveryConstants.genericContent % (
                recipe,
                deliveryDesc.requestId,
                deliveryDesc.userName,
            )
        else:
            email["content"] = DeliveryConstants.nonMSKContent % (
                recipe,
                deliveryDesc.requestId,
                deliveryDesc.piEmail,
            )

    # ADDONS
    if "CRISPRSEQ" in runType:
        email["content"] += DeliveryConstants.crisprAddon
    # BAM illustration for RNASeq
    if "RNASEQ" in runType or "SMARTER" in runType:
        email["content"] += DeliveryConstants.RNASeqAddon

    # Add sample pick up instructions at end for all delivery emails
    if "Investigator Prepared" in deliveryDesc.requestType:
        email["content"] += DeliveryConstants.UserSamplePickUpAddon
    else:  
        email["content"] += DeliveryConstants.SamplePickUpAddon

    return email

# TODO add arguments for unit eg, d for day, m for minutes
def main(mode, minutes):
    ssl._create_default_https_context = ssl._create_unverified_context
    deliveryInfo = DeliveryInfo() 
    if mode == "TEST":
        notifier = TestEmail()
    else:
        notifier = ProdEmail()
    minutes = minutes

    print("Email logic running in mode: {}, searching for deliveries for the past {} minutes".format(mode, minutes))
    
    # get recent delivery information from LIMS
    with (open("ConnectLimsRest.txt")) as connectInfo:
        username = connectInfo.readline().strip()
        password = connectInfo.readline().strip()
    deliveryInfo.setAliases(DeliveryConstants.aliases)
    user_pass = username + ":" + password
    deliveries = deliveryInfo.recentDeliveries(base64.standard_b64encode(user_pass.encode('utf-8')), minutes)

    # send email for each delivery
    for delivered in deliveries:
        try:
            samples = []
            runType = recipe2RunType(delivered.recipe)
            species = delivered.species
            pm = delivered.pm
            # get sample list for the project
            for possibleSample in delivered.samples:
                sampleName = possibleSample.fullId()
                if len(possibleSample.passing_runs) > 0 and sampleName not in samples:
                    samples.append(sampleName)
            print("Project: " + delivered.requestId)
            
            # PI and Investigator always start out as recipients
            # TODO remove duplciate from recipients when pi and investigator is same person
            recipients = list(filter(lambda x: x != "", [delivered.piEmail, delivered.investigatorEmail]))
            additionalRecipients = list(filter(lambda mail: mail not in recipients, delivered.dataAccessEmails.lower().split(",")))
            print("recipients {}, additional recipients {}".format(recipients, additionalRecipients))
            recipients = recipients + additionalRecipients
        
            email = determineDataAccessContent(delivered, runType)
            (toList, ccList) = determineDataAccessRecipients(delivered, recipients, runType, copy.deepcopy(DeliveryConstants.addressMap))
            if runType == "DLP":
                # query ngs_stats DB for all fastq paths for the project
                request_metadata = setaccess.get_request_metadata(delivered.requestId, "none")
                # from all fastq paths get the fastq.gz folder only (probably 1 folder with all fastq.gz files)
                fastq_directories = set()
                for fastq in request_metadata.fastqs:
                    fastq_directories.add(os.path.dirname(fastq))
                sampleDirs = "<br><br>Fastq directories are:<br> {} <br>".format(fastq_directories)
                email["content"] = email["content"] + sampleDirs + DeliveryConstants.FOOTER
            else:
                sampleList = "<br><br>Samples are:<br>"+"<br>".join(sorted(samples, key=lambda x: int(x.split("_")[-1])))
                email["content"] = email["content"] + sampleList + DeliveryConstants.FOOTER

            notifier.notify(runType, delivered, email, toList, ccList)

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

# usage: python3 EmailDelivered.py TEST|PROD TIMELENGTH
# default as test mode and 30 minutes length
if __name__ == '__main__':
    mode = "TEST"
    if len(sys.argv) > 1:
        mode = sys.argv[1]
    minutes = 30
    if len(sys.argv) == 3:
        minutes = sys.argv[2]

    main(mode, minutes)