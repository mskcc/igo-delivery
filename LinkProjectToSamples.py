import requests
from requests.exceptions import HTTPError
import re
from os import listdir
import os.path
import subprocess
import time
import sys
import setaccess

NGS_STATS_ENDPOINT = "http://delphi.mskcc.org:8080/ngs-stats/permissions/getRequestPermissions/"
FASTQ_ROOT = "/igo/delivery/FASTQ/%s/Project_%s/%s" # (runID, requestID, Sample)
DELIVERY_ROOT = "/igo/delivery/share/%s/Project_%s/%s" # (labName, requestID, trimmedRun)

# given requestID as input and get json dictionary as return
def get_NGS_stats(reqID):
    ngs_query_url = NGS_STATS_ENDPOINT + reqID
    response = requests.get(ngs_query_url, verify=False)
    return(response.json())

# NGS_Stats class, need json from ngs endpoint to create.
class NGS_Stats:
    def __init__(self, stats_json):
        self.labName = stats_json["labName"]      # name of delivery folder
        self.fastq_list = stats_json["fastqs"]    # list of original fastq files need to be linked
        self.samples = self.get_sample_run_dict() # dictionary of sample -> runs from fastq list
        self.requestName = stats_json["requestName"] # requestName in order to seperate DLP from others

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
                source_path = "/igo/delivery/FASTQ/{}/Project_{}/{}".format(source, reqID, sample)
                possibleRun_path = "/igo/delivery/FASTQ/{}/Project_{}/{}".format(possibleRun, reqID, sample)
                if os.path.getmtime(possibleRun_path) > os.path.getmtime(source_path):
                    source = possibleRun
            updatedRuns.append(source)

    return updatedRuns

# DLP has different rule for linking no linking for samples
# step 1 get project ID as input, query from db to get fastq list eg :http://delphi.mskcc.org:8080/ngs-stats/permissions/getRequestPermissions/13117_B
# step 2 create symbol links eg: ln -sf /igo/delivery/FASTQ/RUTH_0089_AHHLYJDSX3/Project_13117_B/Sample_HCTWT1_IGO_13117_B_1 /igo/delivery/share/bakhoums/Project_13117_B/RUTH_0089
# step 3 call setaccess
def link_by_request(reqID):
    json_info = get_NGS_stats(reqID)
    stats = NGS_Stats(json_info)
    labName = stats.labName
    recipe = stats.requestName
    
    # check if lab folder exist, if not create one
    labDir = "/igo/delivery/share/%s" % (labName)
    projDir = "/igo/delivery/share/%s/Project_%s" % (labName, reqID)
    if not os.path.exists(labDir):
        cmd = "mkdir " + labDir
        subprocess.run(cmd, shell=True)
        cmd = "chmod +rx " + labDir  
        subprocess.run(cmd, shell=True) # piDir is always readable by all, Project dirs are not

    # then change project dirs to not world readable
    mask = 0o007
    # Set the current umask value and get the previous umask value
    umask = os.umask(mask)
    print("Current umask:", mask)
    print("Previous umask:", umask)

    if not os.path.exists(projDir):
        cmd = "mkdir " + projDir
        subprocess.run(cmd, shell=True)

    madeDir = []
    # create symbol links for each sample
    # if it is DLP only create link for the run not each sample
    if recipe == "DLP":
        # get fastq file folder path instead of each fastq
        fastq_directories = set()
        for fastq in stats.fastq_list:
            fastq_directories.add(os.path.dirname(fastq))
        
        # create link for each folder path
        for fastq_dir in fastq_directories:
            dlink = projDir
            slink = fastq_dir
            cmd = "ln -sf {} {}".format(slink, dlink)
            print(cmd)
            subprocess.run(cmd, shell=True)
    else:
        for sample, runs in stats.samples.items():
            updated_runs = updateRun(runs, reqID, sample)
            for run in updated_runs:
                dlink = DELIVERY_ROOT % (labName, reqID, trimRunID(run))
                # check if lab/project/run folder exist, if not create one
                if not os.path.exists(dlink) and dlink not in madeDir:
                    cmd = "mkdir " + dlink
                    print (cmd)
                    madeDir.append(dlink)
                    subprocess.run(cmd, shell=True)
                slink = FASTQ_ROOT % (run, reqID, sample)
                cmd = "ln -sf {} {}".format(slink, dlink)
                print (cmd)
                subprocess.run(cmd, shell=True)
    
    setaccess.set_request_acls(reqID, "")

# loop link_by_request method by time peirod, time as argument, unit will be min
# step 1 get project list within time period by given time interval from LIMS eg: "https://igolims.mskcc.org:8443/LimsRest/getRecentDeliveries?time=30&units=m"
# step 2 update the project list by removing the projects without sample information(DLP)
# step 3 call link_by_request for each project in the updated list

def get_recent_delivery(time):
    file1 = open('ConnectLimsRest.txt', 'r')
    allLines = file1.readlines()
    username = allLines[0].strip()
    password = allLines[1].strip()
    url = "https://igolims.mskcc.org:8443/LimsRest/getRecentDeliveries?time={}&units=m".format(time)
    try:
        response = requests.get(url, auth=(username, password), verify=False)
        response.raise_for_status()
        return response.json()

    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')

def link_by_time(time):
    deliver_list_orig = get_recent_delivery(time)
    if deliver_list_orig is None:
        print("check input")
        return
    else:
        toDeliver = []
        for possibleDelivered in deliver_list_orig:
            if "samples" not in possibleDelivered:
                continue
            toDeliver.append(possibleDelivered['requestId'])
        if len(toDeliver) == 0:
            print("No projects need to deliver during last {} mins".format(time))
        else:
            for req in toDeliver:
                link_by_request(req)
            print("{} projects are delivered".format(len(toDeliver)))

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
