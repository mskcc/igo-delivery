from MailStaticStrings import DEFAULT_ADDRESS, MSKCC_ADDRESS
import DeliveryConstants
import jinja2

def newSampleInfo(deliveryDesc, mostRecentEmailDate):
    if len(deliveryDesc.deliveryDate) == 0:
        return False
    elif len(deliveryDesc.deliveryDate) == 1:
        mostRecentDelivery = 0
    else:
        mostRecentDelivery = max(deliveryDesc.deliveryDate[0:-1])
    decisionDate = max(mostRecentDelivery, mostRecentEmailDate)
    print("picking between", mostRecentDelivery, mostRecentEmailDate)
    print(decisionDate)
    for sample in deliveryDesc.samples:
        for passing_run, passing_date in sample.passing_dates.iteritems():
            if passing_date >= decisionDate:
                return True
    return False

def determineDataAccessRecipients(deliveryDesc, newAddressMap, recipients):
    toList = recipients
    ccList = newAddressMap['standard']
    analysisType = deliveryDesc.analysisType
    runType = recipe2RunType(deliveryDesc.recipe).upper()
    # BY PROJECT
    if "05500" in deliveryDesc.requestId:
        ccList += newAddressMap["ski"]
    # BY RECIPE
    elif (("IMPACT" in runType or "HEMEPACT" in runType) and "M-" not in runType) or "CAS" in analysisType:
        ccList += newAddressMap['impact']
    elif "ACCESS" in runType:
        ccList += newAddressMap["access"]
    # WES WITH CCS ANALYSIS
    elif "WES" in runType and "CCS" in analysisType:
        ccList += newAddressMap['wesWithCCS']
    # BY ANALYSIS TYPE
    elif "BIC" in analysisType:
        ccList += newAddressMap['pipelineDefault']

    elif "CCS" in analysisType:
        ccList += newAddressMap['ccs']
    # RAW DATA, FASTQ ONLY
    elif "FASTQ" in analysisType:
        ccList += newAddressMap["raw"]
    return (toList, ccList)


def determineDataAccessContent(deliveryDesc, runType):
    analysisType = deliveryDesc.analysisType
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

    # BY RECIPE
    if (("IMPACT" in runType or "HEMEPACT" in runType) and "M-" not in runType) or "CAS" in analysisType:
        email["content"] = (DeliveryConstants.impactContent) % ( 
            recipe,
            deliveryDesc.requestId,
            deliveryDesc.userName
            )
    elif "ACCESS" in runType:
        email["content"] = (DeliveryConstants.accessContent) % (
            recipe,
            deliveryDesc.requestId,
        )

    # BY ANALYSIS TYPE
    elif "WES" in runType and "CCS" in analysisType:
        email["content"] = (DeliveryConstants.wesWithCCSContent) % (
            recipe,
            deliveryDesc.requestId,
        )

    elif analysisType == "FASTQ ONLY":
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
        )

    # NO RULE APPLIED
    else:
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

    return email


def recipe2RunType(recipe):
    runType = recipe
    if (
        runType == "WholeExome-KAPALib"
        or runType == "WholeExomeSequencing"
        or runType == "Agilent_v4_51MB_Human"
        or runType == "IDT_Exome_v1_FP"
    ):
        runType = "WESAnalysis"
    if runType == "Agilent_MouseAllExonV1":
        runType = "WESAnalyis-Mouse"
    return runType
