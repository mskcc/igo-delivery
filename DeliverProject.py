"""
Deliver an IGO request: create the lab share folder, materialize symlinks
from the FASTQ source tree into it, and apply ACLs.

Three project flavors are handled, all in `deliver_request`:
  - DLP: link one folder per run (not per sample).
  - Nanopore: link the whole pre-staged project folder from /igo/delivery/nanopore.
  - Standard: link one (sample, deduped run) at a time, skipping QC-failed
    samples and splitting Chromium Multiome runs into _GEX / _ATAC siblings.

Two entry points:
  - deliver_request(reqID): deliver a single request.
  - deliver_recent(minutes):  deliver everything LIMS flagged in the last N minutes.
"""

import os.path
import re
import socket
import subprocess
import sys

import requests
from requests.exceptions import HTTPError

import setaccess
from splunk_logging import setup_logging, flush_and_shutdown

logger = setup_logging("DeliverProject")


# --- Endpoints + filesystem layout ----------------------------------------

NGS_STATS_ENDPOINT = "http://igodb.mskcc.org:8080/ngs-stats/permissions/getRequestPermissions/"
LIMS_ENDPOINT = "https://igolims.mskcc.org:8443/LimsRest"

# Default delivery layout (igo cluster). The SDC host overrides these below.
FASTQ_ROOT = "/igo/delivery/FASTQ/%s/Project_%s/%s"     # (runID, requestID, sample)
DELIVERY_ROOT = "/igo/delivery/share/%s/Project_%s/%s"  # (labName, requestID, trimmedRun)
DELIVERY = "/igo/delivery/"
NANOPORE_DELIVERY = "/igo/delivery/nanopore/"
SDC = False

# LIMS credentials live in a sibling file shared by every script in this repo.
with open('ConnectLimsRest.txt') as _f:
    username = _f.readline().strip()
    password = _f.readline().strip()

# SDC delivery host: same logical layout, different mount points.
if socket.gethostname().startswith("isvigoacl01"):
    logger.info("Setting default paths for SDC")
    SDC = True
    FASTQ_ROOT = "/ifs/datadelivery/igo_core/FASTQ/%s/Project_%s/%s"
    DELIVERY_ROOT = "/ifs/datadelivery/igo_core/share/%s/Project_%s/%s"
    DELIVERY = "/ifs/datadelivery/igo_core/"
    NANOPORE_DELIVERY = "/ifs/datadelivery/igo_core/nanopore/"


# --- Small shell helpers --------------------------------------------------

def _sh(cmd):
    """Log and run a shell command. Every link/mkdir/chmod in this module
    historically went through `subprocess.run(..., shell=True)`; centralizing
    keeps that behavior and removes the log+run boilerplate from each call site."""
    logger.info(cmd)
    subprocess.run(cmd, shell=True)


def _mkdir_if_missing(path, made):
    """mkdir <path> unless it already exists or we created it earlier in this
    request. `made` is a per-request scratchpad so we don't fire mkdir twice
    for the same dir within one delivery."""
    if os.path.exists(path) or path in made:
        return
    _sh("mkdir " + path)
    made.append(path)


# --- HTTP fetchers --------------------------------------------------------

def get_NGS_stats(reqID):
    """Fetch the request's fastq inventory + lab/recipe metadata from ngs-stats."""
    response = requests.get(NGS_STATS_ENDPOINT + reqID, verify=False)
    return response.json()


def get_qc_stats(reqID):
    """Fetch per-(run, sample) recipe + qcStatus from LimsRest. Returns
    {run: {sample_name: {"recipe": str, "qcstatus": str}}}, or {} on any
    parse/HTTP failure -- callers must tolerate missing keys."""
    qc_query_url = LIMS_ENDPOINT + "/getProjectQc?project=" + reqID
    try:
        response = requests.get(qc_query_url, auth=(username, password), verify=False)
        response.raise_for_status()
        resp_json = response.json()
        if not resp_json or "samples" not in resp_json[0]:
            logger.error("No sample data in QC response for request %s", reqID)
            return {}

        run_sample_qc_info = {}
        for entry in resp_json[0]["samples"]:
            qc = entry.get("qc", {})
            run = qc.get("run")
            sample_name_part = qc.get("sampleName")
            base_id = entry.get("baseId")
            if not run or not sample_name_part or not base_id:
                logger.warning("Skipping sample with missing qc/run/sampleName/baseId in request %s: %s", reqID, entry)
                continue
            # Match the sample directory name ngs-stats writes:
            # "Sample_<sampleName>_IGO_<baseId>".
            sample_name = "Sample_" + sample_name_part + "_IGO_" + base_id
            run_sample_qc_info.setdefault(run, {})[sample_name] = {
                "recipe": entry.get("recipe"),
                "qcstatus": qc.get("qcStatus"),
            }
        return run_sample_qc_info

    except HTTPError as http_err:
        logger.error("Request ID: %s", reqID)
        logger.error("HTTP error occurred: %s", http_err)
    except (KeyError, IndexError, TypeError) as err:
        logger.error("Error parsing QC data for request %s: %s", reqID, err)
    return {}


def _qc_field(qc_map, run, sample, field):
    """Look up a field in the nested {run: {sample: {field: ...}}} qc map.
    The QC payload's run key is the first three underscore-separated segments
    of the fastq run ID, so we truncate before lookup."""
    run_key = "_".join(run.split("_")[:3])
    return qc_map.get(run_key, {}).get(sample, {}).get(field)


# --- NGS_Stats parsing ----------------------------------------------------

class NGS_Stats:
    """Parsed view of the ngs-stats response for one request."""

    def __init__(self, stats_json):
        self.labName = stats_json.get("labName", "")
        self.fastq_list = stats_json.get("fastqs", [])
        self.samples = self.get_sample_run_dict()
        self.requestName = stats_json.get("requestName", "")
        self.isDLP = stats_json.get("isDLP", False)
        self.request = stats_json.get("request", "")
        if not self.labName:
            logger.warning("NGS_Stats missing labName: %s", stats_json)
        if not self.fastq_list:
            logger.warning("NGS_Stats missing fastqs: %s", stats_json)

    def get_sample_run_dict(self):
        """Group fastq paths into {sample_dir: [run_dirs...]}.
        Path layout is /igo/delivery/FASTQ/<run>/Project_<id>/<sample>/<file>,
        so split index 4 is the run and index 6 is the sample."""
        samples = {}
        for fastq in self.fastq_list:
            parts = fastq.split("/")
            run, sample = parts[4], parts[6]
            samples.setdefault(sample, [])
            if run not in samples[sample]:
                samples[sample].append(run)
        return samples


def trimRunID(runID):
    """Reduce e.g. 'RUTH_0089_AHHLYJDSX3' -> 'RUTH_0089'. Used as the per-run
    folder name in the lab share so reruns of the same flowcell collapse together."""
    trimmedRun = re.match("([A-Za-z0-9]+_[0-9]+).*", runID).groups()[0]
    logger.info("Trimmed Run: %s", trimmedRun)
    return trimmedRun


def updateRun(runs, reqID, sample):
    """Dedupe runs that share a trimmed prefix, keeping the one whose fastq
    folder was modified most recently. Handles the case where a flowcell was
    re-demuxed: same trimmed ID, different full IDs, only the newest should
    deliver."""
    by_trim = {}
    for run in runs:
        by_trim.setdefault(trimRunID(run), []).append(run)

    chosen = []
    for full_ids in by_trim.values():
        if len(full_ids) == 1:
            chosen.append(full_ids[0])
            continue
        # Multiple full run IDs share the trimmed prefix: pick the one whose
        # FASTQ dir has the newest mtime on disk.
        winner = full_ids[0]
        for candidate in full_ids:
            winner_path = DELIVERY + "FASTQ/{}/Project_{}/{}".format(winner, reqID, sample)
            cand_path = DELIVERY + "FASTQ/{}/Project_{}/{}".format(candidate, reqID, sample)
            # Older requests sometimes have stale entries that don't exist on
            # disk anymore (eg 08822); just skip those candidates.
            if os.path.exists(winner_path) and os.path.exists(cand_path):
                if os.path.getmtime(cand_path) > os.path.getmtime(winner_path):
                    winner = candidate
        chosen.append(winner)
    return chosen


def link_special_project_to_samples(reqID):
    subprocess.run(["python3", "LinkSpecialProjectToSamples.py", reqID])


# --- Per-flavor linking ---------------------------------------------------

def _ensure_lab_and_project_dirs(labName, reqID):
    """Create <DELIVERY>/share/<lab>/ (world-readable so PIs can browse) and
    the project subdir (group-only via 0o007 umask). Returns the project dir."""
    labDir = DELIVERY + "share/%s" % labName
    projDir = DELIVERY + "share/%s/Project_%s" % (labName, reqID)

    if not os.path.exists(labDir):
        _sh("mkdir " + labDir)
        _sh("chmod +rx " + labDir)

    # Switch the umask BEFORE creating the project dir so it inherits 0o770.
    previous_umask = os.umask(0o007)
    logger.info("Current umask: %s", 0o007)
    logger.info("Previous umask: %s", previous_umask)

    if not os.path.exists(projDir):
        _sh("mkdir " + projDir)

    return projDir


def _link_dlp(stats, projDir):
    """DLP delivers at run granularity, not per sample: one symlink from the
    project dir to each unique fastq directory we saw for this request."""
    logger.info("Linking DLP run")
    fastq_directories = {os.path.dirname(f) for f in stats.fastq_list}
    for fastq_dir in fastq_directories:
        # Use the run folder name (parent of the Project_ dir under FASTQ) as
        # the link name inside the lab share.
        dlink = projDir + "/" + fastq_dir.split('/')[-2]
        # -n: replace an existing symlink-to-directory in place instead of
        # dereferencing it and writing a new link inside the source.
        _sh("ln -sfn {} {}".format(fastq_dir, dlink))


def _link_nanopore(reqID, projDir):
    """Nanopore data is staged ahead of time under NANOPORE_DELIVERY/Project_<id>;
    we just link the whole folder into the lab share -- no per-sample walk."""
    project_folder = "Project_" + reqID
    if project_folder in os.listdir(NANOPORE_DELIVERY):
        _sh("ln -sf {} {}".format(NANOPORE_DELIVERY + project_folder, projDir))


def _link_standard(reqID, labName, stats):
    """Standard projects: one symlink per (sample, deduped run). Skips samples
    QC marked Failed; for Chromium Multiome recipes appends _GEX/_ATAC to the
    run folder so the two halves land in sibling dirs."""
    qc_map = get_qc_stats(reqID)
    made = []
    for sample, runs in stats.samples.items():
        for run in updateRun(runs, reqID, sample):
            dlink = DELIVERY_ROOT % (labName, reqID, trimRunID(run))
            slink = FASTQ_ROOT % (run, reqID, sample)

            qcstatus = _qc_field(qc_map, run, sample, "qcstatus")
            if qcstatus is None or qcstatus == "Failed":
                logger.warning("%s from run %s failed, don't deliver", sample, run)
                continue
            # Older requests sometimes have stale fastq entries that don't
            # exist on disk anymore (eg 08822); skip with a warning.
            if not os.path.exists(slink):
                logger.warning("%s does not exist", slink)
                continue

            # Multiome libraries are split into GEX + ATAC halves; deliver
            # them into sibling run folders so downstream tools find each side.
            recipe = _qc_field(qc_map, run, sample, "recipe")
            if recipe == "SC_Chromium-Multiome-GEX":
                dlink += "_GEX"
            elif recipe == "SC_Chromium-Multiome-ATAC":
                dlink += "_ATAC"

            _mkdir_if_missing(dlink, made)
            _sh("ln -sf {} {}".format(slink, dlink))


# --- Top-level entry points -----------------------------------------------

def deliver_request(reqID):
    """Deliver one request: prepare the lab/project dirs, dispatch to the
    right linking strategy, then apply ACLs."""
    stats = NGS_Stats(get_NGS_stats(reqID))
    print(vars(stats))
    logger.info("RequestName: %s", stats.requestName)

    projDir = _ensure_lab_and_project_dirs(stats.labName, reqID)

    if SDC:
        # ngs-stats hands back /igo paths; rewrite them to the /ifs mount the
        # SDC host actually sees.
        logger.info("Replacing all paths for SDC")
        stats.fastq_list = [s.replace("/igo/delivery/FASTQ", "/ifs/datadelivery/igo_core/FASTQ")
                            for s in stats.fastq_list]

    if stats.isDLP:
        _link_dlp(stats, projDir)
    elif stats.requestName == "Nanopore":
        _link_nanopore(reqID, projDir)
    else:
        _link_standard(reqID, stats.labName, stats)

    setaccess.set_request_acls(reqID, "")


def get_recent_delivery(time):
    """Pull deliveries flagged in LIMS within the last <time> minutes."""
    url = "{}/getRecentDeliveries?time={}&units=m".format(LIMS_ENDPOINT, time)
    try:
        response = requests.get(url, auth=(username, password), verify=False)
        response.raise_for_status()
        return response.json()
    except HTTPError as http_err:
        logger.error("HTTP error occurred: %s", http_err)


def deliver_recent(time):
    """Deliver every request flagged in LIMS within the last <time> minutes.
    Entries without a `samples` list (DLP placeholders, etc.) are skipped."""
    deliveries = get_recent_delivery(time)
    if deliveries is None:
        logger.error("No delivery data returned -- check input")
        return

    to_deliver = []
    for entry in deliveries:
        if "samples" not in entry:
            continue
        req_id = entry.get('requestId')
        if not req_id:
            logger.warning("Delivery entry missing requestId: %s", entry)
            continue
        to_deliver.append(req_id)

    if not to_deliver:
        logger.info("No projects need to deliver during last %s mins", time)
        return

    for req in to_deliver:
        deliver_request(req)
    logger.info("%d projects are delivered", len(to_deliver))


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python3 DeliverProject.py REQUEST=<request> | TIME=<minutes>")
    else:
        arg = sys.argv[1]
        if arg.startswith("REQUEST="):
            deliver_request(arg[8:])
        elif arg.startswith("TIME="):
            deliver_recent(arg[5:])
    flush_and_shutdown()
