import requests
from requests.exceptions import HTTPError
import json
import re
from os import listdir
import os.path
import glob
import subprocess
import time
from collections import defaultdict
import sys
import smtplib
from email.mime.text import MIMEText
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

# Adding pytest, pytest cov
# DLP has different rule for linking no linking for samples
# MissionBio DNA+ protein as test case(11116_S)

# step 1 get project ID as input, query from db to get fastq list eg :http://delphi.mskcc.org:8080/ngs-stats/permissions/getRequestPermissions/13117_B
# step 2 create symbol links eg: ln -sf /igo/delivery/FASTQ/RUTH_0089_AHHLYJDSX3/Project_13117_B/Sample_HCTWT1_IGO_13117_B_1 /igo/delivery/share/bakhoums/Project_13117_B/RUTH_0089
# step 3 call setaccess
def main():
    if (len(sys.argv) != 2):
        print("Usage: python3 LinkProjectToSamples.py requestID")
        return

    reqID = sys.argv[1]
    json_info = get_NGS_stats(reqID)
    stats = NGS_Stats(json_info)
    labName = stats.labName
    madeDir = []
    # create symbol links for each sample
    for sample, runs in stats.samples.items():
        updated_runs = updateRun(runs, reqID, sample)
        for run in updated_runs:
            dlink = DELIVERY_ROOT % (labName, reqID, trimRunID(run))
            # check if lab/project/run folder exist, if not create one
            if not os.path.exists(dlink) and dlink not in madeDir:
                cmd = "mkdir -p " + dlink
                print (cmd)
                madeDir.append(dlink)
                subprocess.run(cmd)
            slink = FASTQ_ROOT % (run, reqID, sample)
            cmd = "ln -sf {} {}".format(slink, dlink)
            print (cmd)
            subprocess.run(cmd)
    
    setaccess.set_request_acls(reqID)

if __name__ == '__main__':
    main()
