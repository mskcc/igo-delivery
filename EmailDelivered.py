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

RNA_recipe_type = ["RNA_SMARTer-Cells", "RNA_SMARTer-RNA", "RNA_Capture", "User_RNA", "RNA_PolyA", "RNA_Ribodeplete"]

# add additional recipients based on project(05500 only), recipe and analysis type
def determineDataAccessRecipients(deliveryDesc, recipients, recipe, addressMap):
    toList = recipients
    # standard email ccList only contains ski_igo_delivery group
    ccList = addressMap['standard']
    analysisType = deliveryDesc.analysisType
    recipe = recipe.upper()
    # BY PROJECT
    if "05500" in deliveryDesc.requestId:
        ccList += addressMap["ski"]
    # BY RECIPE
    elif (("IMPACT" in recipe or "HEMEPACT" in recipe) and "-Mouse" not in recipe) or "CAS" in analysisType:
        ccList += addressMap['impact']
    elif "ACCESS" in recipe:
        ccList += addressMap["access"]
    elif "CMOCH" in recipe:
        ccList += addressMap["CMO-CH"]
    elif "TCR_IGO" in recipe:
        ccList += addressMap["TCRSeq"]
    elif "DLP" in recipe:
        ccList += addressMap["DLP"]
    # BY ANALYSIS TYPE
    elif "BIC" in analysisType:
        ccList += addressMap['pipelineDefault']
    elif "CCS" in analysisType:
        ccList += addressMap['ccs']

    return (toList, ccList)

def determineDataAccessContent(deliveryDesc):
    analysisType = deliveryDesc.analysisType
    recipe = deliveryDesc.recipe
    if recipe in DeliveryConstants.recipe_dict.keys():
        updated_recipe = DeliveryConstants.recipe_dict[recipe]
    else:
        updated_recipe = recipe
    
    email = {
        "content": "",
        "subject": (
            DeliveryConstants.genericSubject
            % (updated_recipe, deliveryDesc.requestId)
        ),
    }

    # generate email content using different templates based on recipe and analysis type, check whether user is outside first.
    
    # check whether the investigator is within MSK or not
    if deliveryDesc.userName != "YOUR_MSKCC_ADDRESS":
        # BY recipe
        if (("IMPACT" in recipe or "HEMEPACT" in recipe) and "-Mouse" not in recipe) or "CAS" in analysisType:
            email["content"] = (DeliveryConstants.impactContent) % ( 
                updated_recipe,
                deliveryDesc.requestId,
                deliveryDesc.userName
                )
        elif "ACCESS" in recipe or "CMOCH" in recipe:
            email["content"] = (DeliveryConstants.accessContent) % (
                updated_recipe,
                deliveryDesc.requestId,
                deliveryDesc.userName
            )

        # BY ANALYSIS TYPE
        elif "WES" in recipe and "CCS" in analysisType:
            email["content"] = (DeliveryConstants.wesWithCCSContent) % (
                recipe,
                deliveryDesc.requestId,
                deliveryDesc.userName
            )
        elif analysisType == "FASTQ ONLY":
            email["content"] = DeliveryConstants.genericContent % (
                updated_recipe,
                deliveryDesc.requestId,
                deliveryDesc.userName,
            )
        
        # Analysis catchall
        elif analysisType != "":
            email["content"] = (DeliveryConstants.genericAnalysisContent) % (
                updated_recipe,
                deliveryDesc.requestId,
                deliveryDesc.userName
            )

        # NO RULE APPLIED
        else:
            email["content"] = DeliveryConstants.genericContent % (
                updated_recipe,
                deliveryDesc.requestId,
                deliveryDesc.userName,
            )
    else:
        email["content"] = DeliveryConstants.nonMSKContent % (
            updated_recipe,
            deliveryDesc.requestId,
            deliveryDesc.piEmail,
        )

    # ADDONS
    if recipe == "DNA_CRISPR":
        email["content"] += DeliveryConstants.crisprAddon
    # BAM illustration for RNASeq
    if recipe in RNA_recipe_type:
        email["content"] += DeliveryConstants.RNASeqAddon

    # Add sample pick up instructions at end for all delivery emails
    if "UserLibrary" in deliveryDesc.requestType:
        email["content"] += DeliveryConstants.UserSamplePickUpAddon
    else:  
        email["content"] += DeliveryConstants.SamplePickUpAddon

    # Add data storage policy for all delivery emails
    email["content"] += DeliveryConstants.DataStoragePolicyAddon

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
            recipe = delivered.recipe
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
        
            email = determineDataAccessContent(delivered)
            (toList, ccList) = determineDataAccessRecipients(delivered, recipients, recipe, copy.deepcopy(DeliveryConstants.addressMap))
            if recipe == "SC_DLP":
                # query ngs_stats DB for all fastq paths for the project
                request_metadata = setaccess.get_request_metadata(delivered.requestId, "none")
                # from all fastq paths get the fastq.gz folder only (probably 1 folder with all fastq.gz files)
                fastq_directories = set()
                for fastq in request_metadata.fastqs:
                    fastq_directories.add(os.path.dirname(fastq))
                sampleDirs = "<br><br>Fastq directories are:<br> {} <br>".format(fastq_directories)
                email["content"] = email["content"] + sampleDirs + DeliveryConstants.FOOTER

            elif recipe.startswith("Nanopore_"):
                email["content"] = email["content"] + DeliveryConstants.FOOTER

            else:
                sampleList = "<br><br>Samples are:<br>"+"<br>".join(sorted(samples, key=lambda x: int(x.split("_")[-1])))
                email["content"] = email["content"] + sampleList + DeliveryConstants.FOOTER

            notifier.notify(recipe, delivered, email, toList, ccList)

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