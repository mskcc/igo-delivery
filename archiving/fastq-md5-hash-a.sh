#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPLUNK_LOG="$SCRIPT_DIR/splunk_log.py"
SCRIPT_NAME="fastq-md5-hash-a"

log_info()  { python3 "$SPLUNK_LOG" "$SCRIPT_NAME" INFO "$1" 2>/dev/null || echo "[INFO] $1"; }
log_error() { python3 "$SPLUNK_LOG" "$SCRIPT_NAME" ERROR "$1" 2>/dev/null || echo "[ERROR] $1"; }

MODE=input
RUNS=/igo/staging/FASTQ/*/
LOCK=/home/seqdataown/.md5locks/FASTQ_HASHING_INPUT
READYFILE=RTAComplete.txt

if [ -f $LOCK ]
 then
  echo "Per $LOCK, FASTQ hashing is already running. `date`"
  exit 2
fi

touch $LOCK
echo
echo "Starting  $0. `date`"
log_info "Starting FASTQ input hashing"

for RUN in $RUNS
 do
  cd $RUN
   if [ -e $READYFILE -a ! -e fastq.md5.$MODE ]
    then
     echo "Generating $RUN fastq.md5.$MODE. `date`"
     log_info "Generating MD5 hash for $RUN"
     find . -name \*\.fastq.gz ! -name '*Undetermined_*' -print0 | xargs -0 -n1 -P20 md5sum --tag | sort > fastq.md5.$MODE.partial
     mv fastq.md5.$MODE.partial fastq.md5.$MODE
     echo "Generated  $RUN fastq.md5.$MODE. `date`"
     log_info "Completed MD5 hash for $RUN"
   fi # [ -e $READYFILE -a ! -e $TYPE.md5.$MODE ]
 done

rm $LOCK
echo "Completed FASTQ. `date`"
log_info "Completed FASTQ input hashing"
