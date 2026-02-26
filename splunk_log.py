#!/usr/bin/env python3
"""
CLI wrapper for splunk_logging - allows shell scripts to send logs to Splunk.

Usage:
    splunk_log.py <script_name> <level> <message>
    
Examples:
    splunk_log.py "fastq-rsync-igo" INFO "Starting rsync for run DIANA_0500"
    splunk_log.py "rsync_promethion" ERROR "rsync failed for Project_12345"
    
Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
"""
import sys
import logging
from splunk_logging import setup_logging, flush_and_shutdown


def main():
    if len(sys.argv) < 4:
        print("Usage: splunk_log.py <script_name> <level> <message>", file=sys.stderr)
        print("Levels: DEBUG, INFO, WARNING, ERROR, CRITICAL", file=sys.stderr)
        sys.exit(1)
    
    script_name = sys.argv[1]
    level_str = sys.argv[2].upper()
    message = " ".join(sys.argv[3:])
    
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }
    
    level = level_map.get(level_str, logging.INFO)
    
    logger = setup_logging(script_name)
    logger.log(level, message)
    flush_and_shutdown()


if __name__ == "__main__":
    main()
