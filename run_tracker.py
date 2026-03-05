#!/usr/bin/env python3
"""
Run Tracker - Monitors sequencing run pipeline status and reports to Splunk.

Tracks runs through the following stages:
0. Sample sheet created (upcoming run)
1. Sequencing in progress (run directory exists, no completion file)
2. Sequencing complete (CopyComplete.txt / RTAComplete.txt)
3. Demux complete (staging FASTQ directory exists)
4. MD5 hashed (fastq.md5.input exists)
5. Archived (ARCHIVED_AT_IGO exists)
6. Delivered (delivery FASTQ directory exists)

Usage:
    python3 run_tracker.py              # Run once
    python3 run_tracker.py --daemon     # Run continuously
"""

import os
import sys
import time
import json
import re
import socket
import subprocess
import requests
import urllib3
from datetime import datetime, timedelta
from pathlib import Path
from splunk_logging import setup_logging, flush_and_shutdown

# Suppress InsecureRequestWarning for self-signed certs
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = setup_logging("run_tracker")

# Configuration
SEQUENCER_BASE = "/igo/sequencers"
STAGING_FASTQ = "/igo/staging/FASTQ"
DELIVERY_FASTQ = "/igo/delivery/FASTQ"
SAMPLESHEET_DIR = "/rtssdc/mohibullahlab/LIMS/LIMS_SampleSheets"
PROJECT_SHARES = "/igo/delivery/share"
NGS_STATS_URL = os.environ.get("NGS_STATS_URL", "https://igolims.mskcc.org:8443/ngs-stats/permissions")

# Sequencer configurations: name -> (path_suffix, completion_file)
SEQUENCERS = {
    "diana": ("diana", "CopyComplete.txt"),
    "michelle": ("michelle", "CopyComplete.txt"),
    "ruth": ("ruth", "CopyComplete.txt"),
    "scott": ("scott", "RunCompletionStatus.xml"),
    "pepe": ("pepe/output", "CopyComplete.txt"),
    "amelie": ("amelie/output", "CopyComplete.txt"),
    "bono": ("bono", "CopyComplete.txt"),
    "fauci2": ("fauci2", "CopyComplete.txt"),
    "johnsawyers": ("johnsawyers", "RTAComplete.txt"),
    "ayyan": ("ayyan", "RTAComplete.txt"),
    "toms": ("toms", "RTAComplete.txt"),
    "vic": ("vic", "RTAComplete.txt"),
}

# How far back to look for runs (days)
LOOKBACK_DAYS = 7


class RunStatus:
    """Represents the status of a sequencing run through the pipeline."""
    
    def __init__(self, run_name, sequencer=None):
        self.run_name = run_name
        self.sequencer = sequencer
        self.flowcell = None  # Original flowcell ID (e.g., A23FNGVLT3)
        self.flowcell_normalized = None  # Normalized flowcell without A/B prefix (e.g., 23FNGVLT3)
        
        # Samplesheet tracking - support multiple (regular + DRAGEN)
        self.samplesheet_file = None  # Primary samplesheet filename
        self.samplesheet_time = None  # Primary samplesheet mtime
        self.samplesheet_date = None  # Scheduled date from filename
        self.samplesheets = []  # List of all samplesheets: [{'file': str, 'path': str, 'time': datetime, 'is_dragen': bool}]
        
        self.run_started = False
        self.run_started_time = None
        self.sequencing_complete = False
        self.sequencing_complete_time = None
        self.demux_complete = False
        self.demux_complete_time = None
        self.md5_hashed = False
        self.md5_hash_time = None
        self.archived = False
        self.archive_time = None
        self.delivered = False
        self.delivery_time = None
        self.stage = "unknown"
        
        # Integrity check fields
        self.projects = []  # List of project IDs found
        self.integrity_issues = []  # List of issues found
        self.acls_set = None  # True/False/None (not checked)
        self.md5_verified = None  # True/False/None
        self.ngs_stats_registered = None  # True/False/None
        self.symlinks_created = None  # True/False/None
        self.staging_file_count = 0
        self.delivery_file_count = 0
    
    def add_samplesheet(self, filename, mtime, is_dragen=False, date=None):
        """Add a samplesheet to this run. Handles both regular and DRAGEN sheets."""
        ss_entry = {
            'file': filename,
            'path': f"{SAMPLESHEET_DIR}/{filename}",
            'time': mtime,
            'is_dragen': is_dragen
        }
        
        # Check if this exact file is already added
        for existing in self.samplesheets:
            if existing['file'] == filename:
                # Update if newer
                if mtime and (existing['time'] is None or mtime > existing['time']):
                    existing['time'] = mtime
                return
        
        self.samplesheets.append(ss_entry)
        
        # Update primary samplesheet (prefer most recent)
        if self.samplesheet_time is None or (mtime and mtime > self.samplesheet_time):
            self.samplesheet_file = filename
            self.samplesheet_time = mtime
            if date:
                self.samplesheet_date = date
    
    def determine_stage(self):
        """Determine the current pipeline stage."""
        if self.delivered:
            self.stage = "delivered"
        elif self.archived:
            self.stage = "archived"
        elif self.md5_hashed:
            self.stage = "hashed"
        elif self.demux_complete:
            self.stage = "demuxed"
        elif self.sequencing_complete:
            self.stage = "sequencing_complete"
        elif self.run_started:
            self.stage = "sequencing"
        elif self.samplesheet_file:
            self.stage = "upcoming"
        else:
            self.stage = "unknown"
        return self.stage
    
    def to_dict(self):
        """Convert to dictionary for Splunk logging."""
        d = {
            "run_name": self.run_name,
            "sequencer": self.sequencer,
            "flowcell": self.flowcell,
            "stage": self.stage,
            "samplesheet_file": self.samplesheet_file,
            "samplesheet_time": str(self.samplesheet_time) if self.samplesheet_time else None,
            "samplesheet_date": self.samplesheet_date,
            "run_started": self.run_started,
            "run_started_time": str(self.run_started_time) if self.run_started_time else None,
            "sequencing_complete": self.sequencing_complete,
            "sequencing_complete_time": str(self.sequencing_complete_time) if self.sequencing_complete_time else None,
            "demux_complete": self.demux_complete,
            "demux_complete_time": str(self.demux_complete_time) if self.demux_complete_time else None,
            "md5_hashed": self.md5_hashed,
            "md5_hash_time": str(self.md5_hash_time) if self.md5_hash_time else None,
            "archived": self.archived,
            "archive_time": str(self.archive_time) if self.archive_time else None,
            "delivered": self.delivered,
            "delivery_time": str(self.delivery_time) if self.delivery_time else None,
        }
        
        # Include integrity fields if checks were performed
        if self.projects:
            d["projects"] = self.projects
        if self.integrity_issues:
            d["integrity_issues"] = self.integrity_issues
        if self.acls_set is not None:
            d["acls_set"] = self.acls_set
        if self.md5_verified is not None:
            d["md5_verified"] = self.md5_verified
        if self.ngs_stats_registered is not None:
            d["ngs_stats_registered"] = self.ngs_stats_registered
        if self.symlinks_created is not None:
            d["symlinks_created"] = self.symlinks_created
        if self.staging_file_count > 0 or self.delivery_file_count > 0:
            d["staging_file_count"] = self.staging_file_count
            d["delivery_file_count"] = self.delivery_file_count
        
        return d


def get_file_mtime(filepath):
    """Get file modification time as datetime, or None if file doesn't exist."""
    try:
        return datetime.fromtimestamp(os.path.getmtime(filepath))
    except (OSError, FileNotFoundError):
        return None


def parse_samplesheet_filename(filename):
    """
    Parse sample sheet filename to extract run information.
    
    Patterns:
    - SampleSheet_YYMMDD_SEQUENCER_NNNN_FLOWCELL.csv
    - SampleSheetDRAGEN_YYMMDD_SEQUENCER_NNNN_FLOWCELL.csv
    - SampleSheetDRAGEN_FLOWCELL.csv (short form)
    - SampleSheetDRAGEN_TEMP_MMDDYY_SEQUENCER_NNNN_FLOWCELL.csv
    
    Returns dict with: sequencer, run_number, flowcell, date, run_name, is_dragen
    Returns None if filename doesn't match expected patterns or is OLD/ORIGINAL.
    """
    # Skip OLD, ORIGINAL, or other prefixed files
    if filename.startswith(('OLD_', 'OLD-', 'ORIGINAL_', 'ccc_', 'original_', 'Original_', 'replaced')):
        return None
    
    # Skip directories and non-csv files
    if not filename.endswith('.csv'):
        return None
    
    # Remove .csv extension
    name = filename[:-4]
    
    # Known sequencer names (uppercase)
    sequencers = {'DIANA', 'MICHELLE', 'RUTH', 'SCOTT', 'PEPE', 'AMELIE', 'BONO', 
                  'FAUCI', 'FAUCI2', 'JOHNSAWYERS', 'AYYAN', 'TOMS', 'VIC'}
    
    # Pattern 1: SampleSheet_YYMMDD_SEQUENCER_NNNN_FLOWCELL or SampleSheetDRAGEN_YYMMDD_...
    # Pattern 2: SampleSheetDRAGEN_TEMP_MMDDYY_...
    patterns = [
        # Standard: SampleSheet_YYMMDD_SEQUENCER_NNNN_FLOWCELL
        r'^SampleSheet_(\d{6})_([A-Z0-9]+)_(\d{4})_([A-Z0-9]+)$',
        # DRAGEN with date: SampleSheetDRAGEN_YYMMDD_SEQUENCER_NNNN_FLOWCELL
        r'^SampleSheetDRAGEN_(\d{6})_([A-Z0-9]+)_(\d{4})_([A-Z0-9]+)$',
        # DRAGEN TEMP: SampleSheetDRAGEN_TEMP_MMDDYY_SEQUENCER_NNNN_FLOWCELL
        r'^SampleSheetDRAGEN_TEMP_(\d{6})_([A-Z0-9]+)_(\d{4})_([A-Z0-9]+)$',
        # DRAGEN short form (flowcell only): SampleSheetDRAGEN_FLOWCELL
        r'^SampleSheetDRAGEN_([A-Z0-9]+)$',
        # SampleSheet short form (flowcell only): SampleSheet_FLOWCELL
        r'^SampleSheet_([A-Z0-9]+)$',
    ]
    
    for i, pattern in enumerate(patterns):
        match = re.match(pattern, name, re.IGNORECASE)
        if match:
            groups = match.groups()
            
            if i <= 2:  # Full format with date
                date_str, sequencer, run_num, flowcell = groups
                # Validate sequencer name
                seq_upper = sequencer.upper()
                if seq_upper not in sequencers:
                    continue
                
                # Parse date (YYMMDD or for TEMP it's MMDDYY)
                try:
                    if i == 2:  # TEMP format uses MMDDYY
                        samplesheet_date = datetime.strptime(date_str, '%m%d%y').strftime('%Y-%m-%d')
                    else:
                        samplesheet_date = datetime.strptime(date_str, '%y%m%d').strftime('%Y-%m-%d')
                except ValueError:
                    samplesheet_date = None
                
                # Build run name: SEQUENCER_NNNN_FLOWCELL (matches directory naming)
                run_name = f"{seq_upper}_{run_num}_{flowcell.upper()}"
                
                return {
                    'sequencer': seq_upper.lower(),
                    'run_number': run_num,
                    'flowcell': flowcell.upper(),
                    'date': samplesheet_date,
                    'run_name': run_name,
                    'is_dragen': 'DRAGEN' in name.upper(),
                    'filename': filename,
                }
            else:  # Short form (flowcell only)
                flowcell = groups[0].upper()
                return {
                    'sequencer': None,
                    'run_number': None,
                    'flowcell': flowcell,
                    'date': None,
                    'run_name': flowcell,  # Use flowcell as run name
                    'is_dragen': 'DRAGEN' in name.upper(),
                    'filename': filename,
                }
    
    return None


def scan_samplesheets(lookback_days=LOOKBACK_DAYS):
    """
    Scan sample sheet directory for recent sample sheets.
    Returns dict of run_name -> RunStatus for runs found in sample sheets.
    """
    runs = {}
    samplesheet_path = Path(SAMPLESHEET_DIR)
    
    if not samplesheet_path.exists():
        logger.warning("Sample sheet directory not found: %s", SAMPLESHEET_DIR)
        return runs
    
    cutoff = datetime.now() - timedelta(days=lookback_days)
    
    try:
        for f in samplesheet_path.iterdir():
            if not f.is_file():
                continue
            
            # Skip old files
            try:
                mtime = datetime.fromtimestamp(f.stat().st_mtime)
                if mtime < cutoff:
                    continue
            except OSError:
                continue
            
            parsed = parse_samplesheet_filename(f.name)
            if not parsed:
                continue
            
            # Ensure uppercase for consistent matching
            run_name = parsed['run_name'].upper()
            flowcell = parsed['flowcell'].upper() if parsed['flowcell'] else None
            flowcell_norm = normalize_flowcell(flowcell)
            
            # Create or update status
            if run_name not in runs:
                status = RunStatus(run_name, parsed['sequencer'])
                status.flowcell = flowcell
                status.flowcell_normalized = flowcell_norm
                runs[run_name] = status
            
            # Add this samplesheet (handles both regular and DRAGEN)
            status = runs[run_name]
            status.add_samplesheet(
                filename=parsed['filename'],
                mtime=mtime,
                is_dragen=parsed.get('is_dragen', False),
                date=parsed['date']
            )
            
            # Update sequencer/flowcell if not set
            if parsed['sequencer'] and not status.sequencer:
                status.sequencer = parsed['sequencer']
            if flowcell and not status.flowcell:
                status.flowcell = flowcell
                status.flowcell_normalized = flowcell_norm
    
    except PermissionError:
        logger.warning("Permission denied scanning %s", samplesheet_path)
    
    return runs


def normalize_flowcell(flowcell):
    """
    Normalize flowcell ID by stripping the A/B side prefix if present.
    Example: A23FNGVLT3 -> 23FNGVLT3, BHJWFFDRX5 -> HJWFFDRX5
    """
    if not flowcell:
        return None
    fc = flowcell.upper()
    # Strip A/B prefix if flowcell starts with A or B followed by alphanumeric
    if len(fc) > 1 and fc[0] in ('A', 'B') and fc[1].isalnum():
        return fc[1:]
    return fc


def extract_run_name_from_dir(dir_name):
    """
    Extract standardized run name from directory name.
    Removes YYMMDD_ prefix if present.
    Returns (run_name, flowcell, flowcell_normalized, sequencer) tuple.
    
    Example: 250219_DIANA_0401_AHJWFFDRX5 -> (DIANA_0401_AHJWFFDRX5, AHJWFFDRX5, HJWFFDRX5, diana)
    """
    name = dir_name
    # Remove date prefix: YYMMDD_SEQUENCER_NNNN_FLOWCELL -> SEQUENCER_NNNN_FLOWCELL
    if len(name) > 7 and name[6] == '_':
        name = name[7:]
    
    parts = name.split('_')
    
    # Known sequencer names
    known_sequencers = {'DIANA', 'MICHELLE', 'RUTH', 'SCOTT', 'PEPE', 'AMELIE', 
                       'BONO', 'FAUCI', 'FAUCI2', 'JOHNSAWYERS', 'AYYAN', 'TOMS', 'VIC'}
    
    flowcell = None
    sequencer = None
    
    if len(parts) >= 3:
        # Standard format: SEQUENCER_NNNN_FLOWCELL or SEQUENCER_NNNN_FLOWCELL_SUFFIX
        flowcell = parts[2]  # Third part is flowcell (not last, in case of _DLP suffix)
        seq_name = parts[0].upper()
        if seq_name in known_sequencers:
            sequencer = seq_name.lower()
    elif len(parts) == 2:
        # Missing sequencer: NNNN_FLOWCELL - try to extract flowcell
        # Check if first part looks like a run number (digits)
        if parts[0].isdigit():
            flowcell = parts[1]
        else:
            # Could be SEQUENCER_FLOWCELL (unusual)
            seq_name = parts[0].upper()
            if seq_name in known_sequencers:
                sequencer = seq_name.lower()
                flowcell = parts[1]
    
    flowcell_normalized = normalize_flowcell(flowcell)
    
    return name, flowcell, flowcell_normalized, sequencer


def scan_sequencers(lookback_days=LOOKBACK_DAYS):
    """Scan sequencer directories for recent runs."""
    runs = {}
    cutoff = datetime.now() - timedelta(days=lookback_days)
    
    for seq_name, (path_suffix, completion_file) in SEQUENCERS.items():
        seq_path = Path(SEQUENCER_BASE) / path_suffix
        if not seq_path.exists():
            continue
        
        try:
            for run_dir in seq_path.iterdir():
                if not run_dir.is_dir():
                    continue
                
                # Skip if too old
                try:
                    mtime = datetime.fromtimestamp(run_dir.stat().st_mtime)
                    ctime = datetime.fromtimestamp(run_dir.stat().st_ctime)
                    if mtime < cutoff:
                        continue
                except OSError:
                    continue
                
                normalized_name, flowcell, flowcell_norm, _ = extract_run_name_from_dir(run_dir.name)
                run_name = normalized_name.upper()  # Uppercase for consistent matching
                
                status = RunStatus(run_name, seq_name)  # Use seq_name from directory iteration
                status.flowcell = flowcell.upper() if flowcell else None
                status.flowcell_normalized = flowcell_norm.upper() if flowcell_norm else None
                status.run_started = True
                status.run_started_time = ctime
                
                # Check for completion file
                completion_path = run_dir / completion_file
                if completion_path.exists():
                    status.sequencing_complete = True
                    status.sequencing_complete_time = get_file_mtime(str(completion_path))
                
                runs[run_name] = status
        except PermissionError:
            logger.warning("Permission denied scanning %s", seq_path)
    
    return runs


def check_staging_status(runs, lookback_days=LOOKBACK_DAYS):
    """Check staging FASTQ directory for demux and hash status."""
    staging_path = Path(STAGING_FASTQ)
    if not staging_path.exists():
        return
    
    cutoff = datetime.now() - timedelta(days=lookback_days)
    
    try:
        for run_dir in staging_path.iterdir():
            if not run_dir.is_dir():
                continue
            
            # Normalize run name (strip date prefix, uppercase for consistency)
            raw_name = run_dir.name
            normalized_name, flowcell, flowcell_norm, sequencer = extract_run_name_from_dir(raw_name)
            run_name = normalized_name.upper()  # Uppercase for consistent matching
            
            try:
                mtime = datetime.fromtimestamp(run_dir.stat().st_mtime)
                if mtime < cutoff and run_name not in runs:
                    continue
            except OSError:
                continue
            
            # Create status if not from sequencer scan
            if run_name not in runs:
                status = RunStatus(run_name, sequencer)
                status.flowcell = flowcell.upper() if flowcell else None
                status.flowcell_normalized = flowcell_norm.upper() if flowcell_norm else None
                runs[run_name] = status
            
            status = runs[run_name]
            status.demux_complete = True
            status.demux_complete_time = get_file_mtime(str(run_dir))
            
            # Check for MD5 hash
            md5_file = run_dir / "fastq.md5.input"
            if md5_file.exists():
                status.md5_hashed = True
                status.md5_hash_time = get_file_mtime(str(md5_file))
            
            # Check for archive marker
            archive_file = run_dir / "ARCHIVED_AT_IGO"
            if archive_file.exists():
                status.archived = True
                status.archive_time = get_file_mtime(str(archive_file))
    except PermissionError:
        logger.warning("Permission denied scanning %s", staging_path)


def check_delivery_status(runs, lookback_days=LOOKBACK_DAYS):
    """Check delivery FASTQ directory for delivered runs."""
    delivery_path = Path(DELIVERY_FASTQ)
    if not delivery_path.exists():
        return
    
    cutoff = datetime.now() - timedelta(days=lookback_days)
    
    try:
        for run_dir in delivery_path.iterdir():
            if not run_dir.is_dir():
                continue
            
            # Normalize run name (strip date prefix, uppercase for consistency)
            raw_name = run_dir.name
            normalized_name, flowcell, flowcell_norm, sequencer = extract_run_name_from_dir(raw_name)
            run_name = normalized_name.upper()  # Uppercase for consistent matching
            
            try:
                mtime = datetime.fromtimestamp(run_dir.stat().st_mtime)
                if mtime < cutoff and run_name not in runs:
                    continue
            except OSError:
                continue
            
            # Create status if not seen before
            if run_name not in runs:
                status = RunStatus(run_name, sequencer)
                status.flowcell = flowcell.upper() if flowcell else None
                status.flowcell_normalized = flowcell_norm.upper() if flowcell_norm else None
                runs[run_name] = status
            
            status = runs[run_name]
            status.delivered = True
            status.delivery_time = get_file_mtime(str(run_dir))
            
            # Find projects in this run
            try:
                for item in run_dir.iterdir():
                    if item.is_dir() and item.name.startswith("Project_"):
                        project_id = item.name.replace("Project_", "")
                        status.projects.append(project_id)
            except PermissionError:
                pass
    except PermissionError:
        logger.warning("Permission denied scanning %s", delivery_path)


def count_fastq_files(directory):
    """Count .fastq.gz files in a directory tree."""
    count = 0
    try:
        for root, dirs, files in os.walk(directory):
            for f in files:
                if f.endswith('.fastq.gz'):
                    count += 1
    except (PermissionError, OSError):
        pass
    return count


def check_acls(run_path):
    """
    Check if NFSv4 ACLs are set on a run directory.
    Returns True if ACLs appear to be set, False otherwise.
    """
    try:
        result = subprocess.run(
            ['nfs4_getfacl', str(run_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True,
            timeout=10
        )
        if result.returncode == 0:
            acl_output = result.stdout
            # Check for user-specific ACLs (not just OWNER@/GROUP@/EVERYONE@)
            # A properly configured ACL will have entries like A::username@domain:permissions
            has_user_acls = bool(re.search(r'A:.*@hpc\.private:', acl_output))
            has_group_acls = bool(re.search(r'A:g:.*@hpc\.private:', acl_output))
            return has_user_acls or has_group_acls
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None  # Could not check


def verify_md5_hashes(run_name):
    """
    Compare fastq.md5.input (staging) with fastq.md5.archive (delivery).
    Returns True if they match, False if mismatch, None if can't compare.
    """
    staging_md5 = Path(STAGING_FASTQ) / run_name / "fastq.md5.input"
    delivery_md5 = Path(STAGING_FASTQ) / run_name / "fastq.md5.archive"
    
    if not staging_md5.exists() or not delivery_md5.exists():
        return None
    
    try:
        with open(staging_md5, 'r') as f:
            staging_content = set(f.read().strip().split('\n'))
        with open(delivery_md5, 'r') as f:
            delivery_content = set(f.read().strip().split('\n'))
        
        return staging_content == delivery_content
    except (IOError, OSError):
        return None


def check_ngs_stats_registration(run_name):
    """
    Check if FASTQs for this run are registered in ngs-stats.
    Returns True if registered, False if not, None if can't check.
    """
    try:
        url = f"{NGS_STATS_URL.replace('/permissions', '')}/fastq/{run_name}"
        response = requests.get(url, timeout=10, verify=False)
        if response.status_code == 200:
            data = response.json()
            # Check if any FASTQs are registered
            if isinstance(data, list) and len(data) > 0:
                return True
            elif isinstance(data, dict) and data.get('fastqs'):
                return True
            return False
        return False
    except (requests.RequestException, ValueError):
        return None


def check_project_symlinks(projects):
    """
    Check if symlinks exist for the given projects in the share directory.
    Returns (True, []) if all OK, (False, [missing_projects]) if issues.
    """
    shares_path = Path(PROJECT_SHARES)
    if not shares_path.exists():
        return None, []
    
    missing = []
    for project_id in projects:
        # Project shares are typically named by project ID
        project_share = shares_path / project_id
        if not project_share.exists():
            # Also check with Project_ prefix
            project_share_alt = shares_path / f"Project_{project_id}"
            if not project_share_alt.exists():
                missing.append(project_id)
    
    if not projects:
        return None, []
    
    return len(missing) == 0, missing


def run_integrity_checks(runs, check_delivered_only=True):
    """
    Run integrity checks on runs.
    
    Checks:
    - ACLs are set on delivery directories
    - MD5 hashes match between staging and archive
    - FASTQs are registered in ngs-stats
    - Project symlinks exist
    - File counts match between staging and delivery
    """
    # Count runs to check
    runs_to_check = [r for r, s in runs.items() if not check_delivered_only or s.delivered]
    total_runs = len(runs_to_check)
    
    if total_runs == 0:
        logger.info("No delivered runs to check for integrity")
        return
    
    logger.info("Starting integrity checks for %d delivered runs...", total_runs)
    logger.info("Delivered runs to check: %s", runs_to_check)
    
    checked = 0
    for run_name, status in runs.items():
        # Only check delivered runs by default
        if check_delivered_only and not status.delivered:
            continue
        
        checked += 1
        delivery_path = Path(DELIVERY_FASTQ) / run_name
        staging_path = Path(STAGING_FASTQ) / run_name
        
        if not delivery_path.exists():
            logger.debug("Skipping %s - delivery path not found", run_name)
            continue
        
        # Progress logging every 10 runs or for last run
        if checked % 10 == 0 or checked == total_runs:
            logger.info("Integrity check progress: %d/%d runs (%d%%)", 
                       checked, total_runs, int(checked * 100 / total_runs))
        
        logger.debug("Checking integrity: %s", run_name)
        
        # Check ACLs
        logger.debug("  [%s] Checking ACLs...", run_name)
        status.acls_set = check_acls(delivery_path)
        if status.acls_set is False:
            status.integrity_issues.append("ACLs not set")
            logger.warning("  [%s] ACLs not set!", run_name)
        
        # Check MD5 hashes
        logger.debug("  [%s] Checking MD5 hashes...", run_name)
        status.md5_verified = verify_md5_hashes(run_name)
        if status.md5_verified is False:
            status.integrity_issues.append("MD5 hash mismatch")
            logger.warning("  [%s] MD5 hash mismatch!", run_name)
        
        # Check ngs-stats registration
        logger.debug("  [%s] Checking ngs-stats registration...", run_name)
        status.ngs_stats_registered = check_ngs_stats_registration(run_name)
        if status.ngs_stats_registered is False:
            status.integrity_issues.append("Not registered in ngs-stats")
            logger.warning("  [%s] Not registered in ngs-stats!", run_name)
        
        # Check project symlinks
        if status.projects:
            logger.debug("  [%s] Checking symlinks for %d projects...", run_name, len(status.projects))
            symlinks_ok, missing = check_project_symlinks(status.projects)
            status.symlinks_created = symlinks_ok
            if symlinks_ok is False:
                status.integrity_issues.append(f"Missing symlinks: {missing}")
                logger.warning("  [%s] Missing symlinks: %s", run_name, missing)
        
        # Count files
        logger.debug("  [%s] Counting FASTQ files...", run_name)
        if staging_path.exists():
            status.staging_file_count = count_fastq_files(staging_path)
        status.delivery_file_count = count_fastq_files(delivery_path)
        
        if status.staging_file_count > 0 and status.delivery_file_count > 0:
            if status.staging_file_count != status.delivery_file_count:
                status.integrity_issues.append(
                    f"File count mismatch: staging={status.staging_file_count}, delivery={status.delivery_file_count}"
                )
                logger.warning("  [%s] File count mismatch: staging=%d, delivery=%d", 
                             run_name, status.staging_file_count, status.delivery_file_count)
        
        # Log completion for this run
        if status.integrity_issues:
            logger.info("  [%s] Completed with %d issues", run_name, len(status.integrity_issues))
        else:
            logger.debug("  [%s] Completed - OK", run_name)
    
    logger.info("Integrity checks complete: %d runs checked", checked)


def get_pipeline_summary(runs):
    """Get summary counts by stage."""
    summary = {
        "upcoming": 0,
        "sequencing": 0,
        "sequencing_complete": 0,
        "demuxed": 0,
        "hashed": 0,
        "archived": 0,
        "delivered": 0,
        "total": len(runs),
    }
    
    for status in runs.values():
        stage = status.determine_stage()
        if stage in summary:
            summary[stage] += 1
    
    return summary


def log_run_statuses(runs, log_individual=True, run_integrity=False):
    """Log run statuses to Splunk with structured events for table visualization."""
    summary = get_pipeline_summary(runs)
    
    # Log summary event (for dashboard KPIs)
    summary_event = {
        "event_type": "pipeline_summary",
        **summary,
        "scan_time": datetime.now().isoformat()
    }
    logger.info(json.dumps(summary_event))
    
    # Log each run as a structured table row
    for status in runs.values():
        status.determine_stage()
        
        # Create a flat, table-friendly record
        row = {
            "event_type": "run_status",
            "run": status.run_name,
            "sequencer": status.sequencer or "unknown",
            "flowcell": status.flowcell or "",
            "stage": status.stage,
            "stage_order": _stage_order(status.stage),  # For sorting
            "scheduled_date": status.samplesheet_date or "",
            "samplesheet_file": status.samplesheet_file or "",
            "samplesheet_path": f"{SAMPLESHEET_DIR}/{status.samplesheet_file}" if status.samplesheet_file else "",
            "samplesheet_count": len(status.samplesheets),
            "samplesheet_paths": "; ".join([ss['path'] for ss in status.samplesheets]) if status.samplesheets else "",
            "samplesheet_regular": next((ss['path'] for ss in status.samplesheets if not ss['is_dragen']), ""),
            "samplesheet_dragen": next((ss['path'] for ss in status.samplesheets if ss['is_dragen']), ""),
            "has_samplesheet": "Yes" if status.samplesheet_file else "No",
            "has_dragen_samplesheet": "Yes" if any(ss['is_dragen'] for ss in status.samplesheets) else "No",
            "run_started": "Yes" if status.run_started else "No",
            "seq_complete": "Yes" if status.sequencing_complete else "No",
            "demuxed": "Yes" if status.demux_complete else "No",
            "hashed": "Yes" if status.md5_hashed else "No",
            "archived": "Yes" if status.archived else "No",
            "delivered": "Yes" if status.delivered else "No",
        }
        
        # Add integrity fields if checked
        if run_integrity and status.delivered:
            row["acls_ok"] = _bool_to_status(status.acls_set)
            row["md5_ok"] = _bool_to_status(status.md5_verified)
            row["ngs_stats_ok"] = _bool_to_status(status.ngs_stats_registered)
            row["symlinks_ok"] = _bool_to_status(status.symlinks_created)
            row["file_count_staging"] = status.staging_file_count
            row["file_count_delivery"] = status.delivery_file_count
            row["issues"] = "; ".join(status.integrity_issues) if status.integrity_issues else ""
            row["has_issues"] = "Yes" if status.integrity_issues else "No"
        
        # Add timing info
        if status.samplesheet_time:
            row["samplesheet_time"] = status.samplesheet_time.isoformat()
        if status.sequencing_complete_time:
            row["seq_complete_time"] = status.sequencing_complete_time.isoformat()
        if status.delivery_time:
            row["delivery_time"] = status.delivery_time.isoformat()
        
        # Log level based on stage/issues
        if status.integrity_issues:
            logger.warning(json.dumps(row))
        elif status.stage in ("upcoming", "sequencing", "sequencing_complete", "demuxed"):
            logger.info(json.dumps(row))
        else:
            logger.info(json.dumps(row))
    
    # Log integrity summary if checks were performed
    if run_integrity:
        delivered = [s for s in runs.values() if s.delivered]
        if delivered:
            integrity_event = {
                "event_type": "integrity_summary",
                "delivered_runs": len(delivered),
                "acls_verified": sum(1 for s in delivered if s.acls_set is True),
                "md5_verified": sum(1 for s in delivered if s.md5_verified is True),
                "ngs_stats_registered": sum(1 for s in delivered if s.ngs_stats_registered is True),
                "symlinks_ok": sum(1 for s in delivered if s.symlinks_created is True),
                "runs_with_issues": sum(1 for s in delivered if s.integrity_issues),
                "scan_time": datetime.now().isoformat()
            }
            logger.info(json.dumps(integrity_event))


def _stage_order(stage):
    """Return numeric order for stage (for sorting in Splunk)."""
    order = {
        "upcoming": 1,
        "sequencing": 2,
        "sequencing_complete": 3,
        "demuxed": 4,
        "hashed": 5,
        "archived": 6,
        "delivered": 7,
        "unknown": 0
    }
    return order.get(stage, 0)


def _bool_to_status(value):
    """Convert boolean/None to display string."""
    if value is True:
        return "OK"
    elif value is False:
        return "FAIL"
    else:
        return "N/A"


def merge_samplesheet_info(runs, samplesheet_runs):
    """
    Merge sample sheet information into existing runs.
    Also adds new runs that only exist as sample sheets (upcoming).
    Uses case-insensitive matching for run names and flowcells.
    Also tries matching by normalized flowcell (without A/B prefix).
    """
    for ss_run_name, ss_status in samplesheet_runs.items():
        # Normalize run name to uppercase for matching
        run_name_upper = ss_run_name.upper()
        ss_flowcell_upper = ss_status.flowcell.upper() if ss_status.flowcell else None
        ss_flowcell_norm = ss_status.flowcell_normalized.upper() if ss_status.flowcell_normalized else normalize_flowcell(ss_flowcell_upper)
        
        # Try exact match first (case-insensitive)
        if run_name_upper in runs:
            existing = runs[run_name_upper]
            # Copy all samplesheets from ss_status to existing
            for ss in ss_status.samplesheets:
                existing.add_samplesheet(
                    filename=ss['file'],
                    mtime=ss['time'],
                    is_dragen=ss['is_dragen'],
                    date=ss_status.samplesheet_date
                )
            if not existing.flowcell and ss_flowcell_upper:
                existing.flowcell = ss_flowcell_upper
                existing.flowcell_normalized = ss_flowcell_norm
            if not existing.sequencer and ss_status.sequencer:
                existing.sequencer = ss_status.sequencer
        else:
            # Check if we can match by flowcell (try exact first, then normalized)
            matched = False
            for existing in runs.values():
                existing_flowcell_upper = existing.flowcell.upper() if existing.flowcell else None
                existing_flowcell_norm = existing.flowcell_normalized.upper() if existing.flowcell_normalized else normalize_flowcell(existing_flowcell_upper)
                
                # Try exact flowcell match first
                flowcell_match = False
                if existing_flowcell_upper and ss_flowcell_upper:
                    if existing_flowcell_upper == ss_flowcell_upper:
                        flowcell_match = True
                
                # Try normalized flowcell match (strips A/B prefix)
                if not flowcell_match and existing_flowcell_norm and ss_flowcell_norm:
                    if existing_flowcell_norm == ss_flowcell_norm:
                        flowcell_match = True
                
                if flowcell_match:
                    # Copy all samplesheets from ss_status to existing
                    for ss in ss_status.samplesheets:
                        existing.add_samplesheet(
                            filename=ss['file'],
                            mtime=ss['time'],
                            is_dragen=ss['is_dragen'],
                            date=ss_status.samplesheet_date
                        )
                    # Update sequencer if missing
                    if not existing.sequencer and ss_status.sequencer:
                        existing.sequencer = ss_status.sequencer
                    matched = True
                    break
            
            if not matched:
                # New upcoming run (sample sheet exists but run not started)
                # Store with uppercase run name for consistency
                ss_status.run_name = run_name_upper
                if ss_status.flowcell:
                    ss_status.flowcell = ss_flowcell_upper
                    ss_status.flowcell_normalized = ss_flowcell_norm
                runs[run_name_upper] = ss_status


def run_once(run_integrity=True):
    """Run the tracker once."""
    logger.info("Starting run tracker scan")
    
    # Scan sample sheets first (for upcoming runs)
    logger.info("Scanning sample sheets...")
    samplesheet_runs = scan_samplesheets()
    logger.info("Found %d sample sheets: %s", len(samplesheet_runs), list(samplesheet_runs.keys()))
    
    # Scan sequencer directories
    logger.info("Scanning sequencer directories...")
    runs = scan_sequencers()
    logger.info("Found %d runs on sequencers: %s", len(runs), list(runs.keys()))
    
    # Check staging and delivery status BEFORE merging samplesheets
    # This ensures runs found only in staging/delivery can be matched with samplesheets
    logger.info("Checking staging status...")
    check_staging_status(runs)
    demuxed_runs = [r for r, s in runs.items() if s.demux_complete]
    logger.info("Found %d demuxed runs in staging: %s", len(demuxed_runs), demuxed_runs)
    
    logger.info("Checking delivery status...")
    check_delivery_status(runs)
    delivered_runs = [r for r, s in runs.items() if s.delivered]
    logger.info("Found %d delivered runs: %s", len(delivered_runs), delivered_runs)
    
    # NOW merge sample sheet info (after all runs are discovered)
    logger.info("Merging sample sheet info...")
    merge_samplesheet_info(runs, samplesheet_runs)
    runs_with_samplesheets = [r for r, s in runs.items() if s.samplesheet_file]
    logger.info("Matched %d runs with sample sheets", len(runs_with_samplesheets))
    
    # Run integrity checks on delivered runs
    if run_integrity:
        logger.info("Running integrity checks on delivered runs...")
        run_integrity_checks(runs, check_delivered_only=True)
    
    # Log results
    log_run_statuses(runs, run_integrity=run_integrity)
    
    logger.info("Run tracker scan complete. Found %d runs.", len(runs))
    return runs


def run_daemon(interval_seconds=300, run_integrity=True):
    """Run the tracker continuously."""
    logger.info("Starting run tracker daemon (interval: %ds)", interval_seconds)
    
    while True:
        try:
            run_once(run_integrity=run_integrity)
        except Exception as e:
            logger.error("Error in run tracker: %s", e)
        
        flush_and_shutdown()
        time.sleep(interval_seconds)


def print_usage():
    print("""
Run Tracker - Monitor sequencing run pipeline status

Usage:
    python3 run_tracker.py                      # Run once with integrity checks
    python3 run_tracker.py --no-integrity       # Run once without integrity checks
    python3 run_tracker.py --daemon [interval]  # Run continuously (default: 300s)
    python3 run_tracker.py --check-run <name>   # Check specific run integrity
    python3 run_tracker.py --help               # Show this help

Environment Variables:
    NGS_STATS_URL   - ngs-stats API URL (default: https://igolims.mskcc.org:8443/ngs-stats)
    LOOKBACK_DAYS   - How many days back to scan (default: 7)
""")


def check_single_run(run_name):
    """Check integrity of a single run."""
    logger.info("Checking integrity of run: %s", run_name)
    
    status = RunStatus(run_name)
    
    delivery_path = Path(DELIVERY_FASTQ) / run_name
    staging_path = Path(STAGING_FASTQ) / run_name
    
    if not delivery_path.exists():
        logger.error("Run not found in delivery: %s", delivery_path)
        return
    
    status.delivered = True
    status.delivery_time = get_file_mtime(str(delivery_path))
    
    # Find projects
    try:
        for item in delivery_path.iterdir():
            if item.is_dir() and item.name.startswith("Project_"):
                project_id = item.name.replace("Project_", "")
                status.projects.append(project_id)
    except PermissionError:
        pass
    
    # Run all checks
    runs = {run_name: status}
    run_integrity_checks(runs, check_delivered_only=False)
    
    # Print results
    print(f"\nRun: {run_name}")
    print(f"  Delivery path: {delivery_path}")
    print(f"  Projects: {status.projects}")
    print(f"  ACLs set: {status.acls_set}")
    print(f"  MD5 verified: {status.md5_verified}")
    print(f"  ngs-stats registered: {status.ngs_stats_registered}")
    print(f"  Symlinks created: {status.symlinks_created}")
    print(f"  Staging files: {status.staging_file_count}")
    print(f"  Delivery files: {status.delivery_file_count}")
    
    if status.integrity_issues:
        print(f"\n  ISSUES:")
        for issue in status.integrity_issues:
            print(f"    - {issue}")
    else:
        print(f"\n  No integrity issues found")
    
    logger.info("Run check complete: %s", json.dumps(status.to_dict()))


def main():
    run_integrity = True
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--help":
            print_usage()
            return
        elif sys.argv[1] == "--no-integrity":
            run_integrity = False
        elif sys.argv[1] == "--daemon":
            interval = int(sys.argv[2]) if len(sys.argv) > 2 else 300
            run_daemon(interval, run_integrity=run_integrity)
            return
        elif sys.argv[1] == "--check-run":
            if len(sys.argv) < 3:
                print("Error: --check-run requires a run name")
                print_usage()
                return
            check_single_run(sys.argv[2])
            flush_and_shutdown()
            return
    
    run_once(run_integrity=run_integrity)
    flush_and_shutdown()


if __name__ == "__main__":
    main()
