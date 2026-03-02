import requests
from requests.exceptions import HTTPError
import re
import socket
from os import listdir
import os.path
import subprocess
import time
import sys
import setaccess
from splunk_logging import setup_logging, flush_and_shutdown
logger = setup_logging("LinkProjectToSamples")
import LinkDLPProjectToSamples

NGS_STATS_ENDPOINT = "http://igodb.mskcc.org:8080/ngs-stats/permissions/getRequestPermissions/"
LIMS_ENDPOINT = "https://igolims.mskcc.org:8443/LimsRest"
FASTQ_ROOT = "/igo/delivery/FASTQ/%s/Project_%s/%s" # (runID, requestID, Sample)
DELIVERY_ROOT = "/igo/delivery/share/%s/Project_%s/%s" # (labName, requestID, trimmedRun)
DELIVERY = "/igo/delivery/"
NANOPORE_DELIVERY = "/igo/delivery/nanopore/"
SDC=False

file1 = open('ConnectLimsRest.txt', 'r')
allLines = file1.readlines()
username = allLines[0].strip()
password = allLines[1].strip()

if socket.gethostname().startswith("isvigoacl01"):
    logger.info("Setting default paths for SDC")
    SDC = True
    FASTQ_ROOT = "/ifs/datadelivery/igo_core/FASTQ/%s/Project_%s/%s" # (runID, requestID, Sample)
    DELIVERY_ROOT = "/ifs/datadelivery/igo_core/share/%s/Project_%s/%s" # (labName, requestID, trimmedRun)
    DELIVERY = "/ifs/datadelivery/igo_core/"
    NANOPORE_DELIVERY = "/ifs/datadelivery/igo_core/nanopore/"

# given requestID as input and get json dictionary as return
def get_NGS_stats(reqID):
    ngs_query_url = NGS_STATS_ENDPOINT + reqID
    response = requests.get(ngs_query_url, verify=False)
    return(response.json())

def get_qc_stats(reqID):
    qc_query_url = LIMS_ENDPOINT + "/getProjectQc?project=" + reqID
    try:
        response = requests.get(qc_query_url, auth=(username, password), verify=False)
        response.raise_for_status()
        run_sample_qc_info ={}
        resp_json = response.json()
        if not resp_json or "samples" not in resp_json[0]:
            logger.error("No sample data in QC response for request %s", reqID)
            return run_sample_qc_info

        json_info = resp_json[0]["samples"]

        for i in json_info:
            qc = i.get("qc", {})
            run = qc.get("run")
            sample_name_part = qc.get("sampleName")
            base_id = i.get("baseId")
            if not run or not sample_name_part or not base_id:
                logger.warning("Skipping sample with missing qc/run/sampleName/baseId in request %s: %s", reqID, i)
                continue
            sample_name = "Sample_" + sample_name_part + "_IGO_" + base_id
            recipe = i.get("recipe")
            qcstatus = qc.get("qcStatus")
            if run not in run_sample_qc_info:
                run_sample_qc_info[run] = {}
            run_sample_qc_info[run][sample_name] = {"recipe": recipe, "qcstatus": qcstatus}
        return run_sample_qc_info

    except HTTPError as http_err:
        logger.error("Request ID: %s", reqID)
        logger.error("HTTP error occurred: %s", http_err)
    except (KeyError, IndexError, TypeError) as err:
        logger.error("Error parsing QC data for request %s: %s", reqID, err)
    
# NGS_Stats class, need json from ngs endpoint to create.
class NGS_Stats:
    def __init__(self, stats_json):
        self.labName = stats_json.get("labName", "")
        self.fastq_list = stats_json.get("fastqs", [])
        self.samples = self.get_sample_run_dict()
        self.requestName = stats_json.get("requestName", "")
        self.isDLP = stats_json.get("isDLP", False) or self.requestName == "DNALibraryPrep"
        self.request = stats_json.get("request", "")
        if not self.labName:
            logger.warning("NGS_Stats missing labName: %s", stats_json)
        if not self.fastq_list:
            logger.warning("NGS_Stats missing fastqs: %s", stats_json)


    # get dictionary of sample -> run by fastq_list
    def get_sample_run_dict(self):
        samples = {}
        for fastq in self.fastq_list:
            info_list = fastq.split("/")
            run = info_list[4]
            sample = info_list[6]
            if sample in samples.keys():
                if run not in samples[sample]:
                    samples[sample].append(run)
            else:
                samples[sample] = [run]
        return samples

def trimRunID(runID):
    trimmedRun = re.match("([A-Za-z0-9]+_[0-9]+).*", runID).groups()[0]
    logger.info("Trimmed Run: %s", trimmedRun)
    return trimmedRun

# given reqID, sample and list of runs, if trimmedRun are same, keep only latest runID
def updateRun(runs, reqID, sample):
    trimmedRun_run_dict = {}
    updatedRuns = []
    for run in runs:
        trimmedRun = trimRunID(run)
        if trimmedRun in trimmedRun_run_dict.keys():
            trimmedRun_run_dict[trimmedRun].append(run)
        else:
            trimmedRun_run_dict[trimmedRun] = [run]

    for trimmedRun, runID in trimmedRun_run_dict.items():
        if len(runID) == 1:
            updatedRuns.append(runID[0])
        else:
            source = runID[0]
            for possibleRun in runID:
                source_path = DELIVERY + "FASTQ/{}/Project_{}/{}".format(source, reqID, sample)
                possibleRun_path = DELIVERY + "FASTQ/{}/Project_{}/{}".format(possibleRun, reqID, sample)
                # check if folder exists before create link for cases that project contains old samples eg: 08822
                if os.path.exists(source_path) and os.path.exists(possibleRun_path):
                    if os.path.getmtime(possibleRun_path) > os.path.getmtime(source_path):
                        source = possibleRun
            updatedRuns.append(source)

    return updatedRuns

def link_special_project_to_samples(reqID):
    subprocess.run(["python3", "LinkSpecialProjectToSamples.py", reqID])

# DLP has different rule for linking no linking for samples
# step 1 get project ID as input, query from db to get fastq list eg :http://igodb.mskcc.org:8080/ngs-stats/permissions/getRequestPermissions/13117_B
# step 2 create symbol links eg: ln -sf /igo/delivery/FASTQ/RUTH_0089_AHHLYJDSX3/Project_13117_B/Sample_HCTWT1_IGO_13117_B_1 /igo/delivery/share/bakhoums/Project_13117_B/RUTH_0089
# step 3 call setaccess
def link_by_request(reqID):
    json_info = get_NGS_stats(reqID)
    stats = NGS_Stats(json_info)
    print(vars(stats))
    labName = stats.labName
    request_name = stats.requestName # ie PEDPEG, SingleCell, etc.
    isDLP = stats.isDLP
    logger.info("RequestName: %s", request_name)

    # check if lab folder exist, if not create one
    labDir = DELIVERY + "share/%s" % (labName)
    projDir = DELIVERY + "share/%s/Project_%s" % (labName, reqID)
    if not os.path.exists(labDir):
        cmd = "mkdir " + labDir
        subprocess.run(cmd, shell=True)
        cmd = "chmod +rx " + labDir
        subprocess.run(cmd, shell=True) # piDir is always readable by all, Project dirs are not

    # then change project dirs to not world readable
    mask = 0o007
    # Set the current umask value and get the previous umask value
    umask = os.umask(mask)
    logger.info("Current umask: %s", mask)
    logger.info("Previous umask: %s", umask)

    if not os.path.exists(projDir):
        cmd = "mkdir " + projDir
        subprocess.run(cmd, shell=True)

    if SDC: # replace all paths /igo/delivery/FASTQ with /ifs/datadelivery/igo_core/FASTQ
        logger.info("Replacing all paths for SDC")
        stats.fastq_list = [s.replace("/igo/delivery/FASTQ", "/ifs/datadelivery/igo_core/FASTQ") for s in stats.fastq_list]

    madeDir = []
    # create symbol links for each sample
    # if it is DLP only create link for the run not each sample
    


    if isDLP:
        LinkDLPProjectToSamples.main(["REQUEST=", reqID])
    else:
        run_sample_qc = get_qc_stats(reqID)
        
    # if it is nanopore date, search under folder /igo/delivery/nanopore for project data path. The name for the folder should start with "Project_12345__"
    if (request_name == "Nanopore") and (not isDLP):
        # find project data folder
        parent_dir = NANOPORE_DELIVERY
        project_list = os.listdir(parent_dir)
        project_folder = "Project_" + reqID
        for project_dir in project_list:
            if project_folder == project_dir:
                # create symbol link
                slink = parent_dir + project_dir
                dlink = projDir
                cmd = "ln -sf {} {}".format(slink, dlink)
                logger.info(cmd)
                subprocess.run(cmd, shell=True)
    elif (not isDLP):
        for sample, runs in stats.samples.items():
            updated_runs = updateRun(runs, reqID, sample)
            for run in updated_runs:
                dlink = DELIVERY_ROOT % (labName, reqID, trimRunID(run))
                slink = FASTQ_ROOT % (run, reqID, sample)
                # check if the file has status of failed
                run_key = "_".join(run.split("_")[:3])
                qcstatus = (
                    run_sample_qc
                    .get(run_key, {})   # run might not exist
                    .get(sample, {})    # sample might not exist
                    .get("qcstatus")    # qcstatus might not exist
                )
                if qcstatus is None or qcstatus == "Failed":
                    logger.warning("%s from run %s failed, don't deliver", sample, run)
                else:
                    # check if folder exists before create link for cases that project contains old samples eg: 08822
                    if os.path.exists(slink):
                        recipe = (
                            run_sample_qc
                            .get(run_key, {})
                            .get(sample, {})
                            .get("recipe")
                        )
                        if recipe == "SC_Chromium-Multiome-GEX":
                            dlink = dlink + "_GEX"
                        if recipe == "SC_Chromium-Multiome-ATAC":
                            dlink = dlink + "_ATAC"

                        # check if lab/project/run folder exist, if not create one
                        if not os.path.exists(dlink) and dlink not in madeDir:
                            cmd = "mkdir " + dlink
                            logger.info(cmd)
                            madeDir.append(dlink)
                            subprocess.run(cmd, shell=True)
                        cmd = "ln -sf {} {}".format(slink, dlink)
                        logger.info(cmd)
                        subprocess.run(cmd, shell=True)
                    else:
                        logger.warning("%s does not exist", slink)

    setaccess.set_request_acls(reqID, "")

# loop link_by_request method by time peirod, time as argument, unit will be min
# step 1 get project list within time period by given time interval from LIMS eg: "https://igolims.mskcc.org:8443/LimsRest/getRecentDeliveries?time=30&units=m"
# step 2 update the project list by removing the projects without sample information(DLP)
# step 3 call link_by_request for each project in the updated list

def get_recent_delivery(time):
    url = "{}/getRecentDeliveries?time={}&units=m".format(LIMS_ENDPOINT, time)
    try:
        response = requests.get(url, auth=(username, password), verify=False)
        response.raise_for_status()
        return response.json()

    except HTTPError as http_err:
        logger.error("HTTP error occurred: %s", http_err)

def link_by_time(time):
    deliver_list_orig = get_recent_delivery(time)
    if deliver_list_orig is None:
        logger.error("No delivery data returned -- check input")
        return
    else:
        toDeliver = []
        for possibleDelivered in deliver_list_orig:
            if "samples" not in possibleDelivered:
                continue
            req_id = possibleDelivered.get('requestId')
            if not req_id:
                logger.warning("Delivery entry missing requestId: %s", possibleDelivered)
                continue
            toDeliver.append(req_id)
        if len(toDeliver) == 0:
            logger.info("No projects need to deliver during last %s mins", time)
        else:
            for req in toDeliver:
                link_by_request(req)
            logger.info("%d projects are delivered", len(toDeliver))

if __name__ == '__main__':
    if (len(sys.argv) != 2):
        print("Usage: python3 LinkProjectToSamples.py REQUEST=<request> | TIME=<minutes>")
    else:
        args = sys.argv[1]
        if args.startswith("REQUEST="):
            request = args[8:]
            link_by_request(request)

        if args.startswith("TIME="):
            time = args[5:]
            link_by_time(time)
    flush_and_shutdown()
