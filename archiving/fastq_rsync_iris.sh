#!/bin/bash
# Adapted from ~pepper/bin scripts run from 2011-2019
# A run should be copied when the fastq.md5.input file exists but no ARCHIVED file exists

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPLUNK_LOG="$SCRIPT_DIR/splunk_log.py"
SCRIPT_NAME="fastq_rsync_iris"

log_info()  { python3 "$SPLUNK_LOG" "$SCRIPT_NAME" INFO "$1" 2>/dev/null || echo "[INFO] $1"; }
log_error() { python3 "$SPLUNK_LOG" "$SCRIPT_NAME" ERROR "$1" 2>/dev/null || echo "[ERROR] $1"; }

ARCHFILE=ARCHIVED_AT_IRIS
SOURCE=/igo/staging/FASTQ
DEST=/ifs/datadelivery/igo_core/FASTQ/
LOCK=~/.md5locks/storage-FASTQ.lock
READYFILE=fastq.md5.input
RSYNC="rsync -a --no-links --exclude=*.cif --exclude=*.bcl --exclude=*.bcl.gz --exclude=nohup.out --exclude=*Undetermined_*.fastq.gz "

if [ -f $LOCK ]
 then
  echo "Per $LOCK, $0 is already running. `date`"
  exit 2
fi

touch $LOCK
echo
echo "Starting  $0. `date`"
log_info "Starting fastq_rsync_iris"

function rsync_run {
    RUN=$1

    echo "Archiving $SOURCE/$RUN `date`"
    log_info "Starting rsync for IRIS run $RUN"
    $RSYNC --exclude=$ARCHFILE $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #1 error on $RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #1 error on $RUN" skigodata@mskcc.org
      log_error "rsync #1 failed for IRIS run $RUN"
    fi # [ $? != 0 ]

    /usr/bin/chmod +x $DEST/$RUN

    date >> $DEST$RUN$ARCHFILE
    
    $RSYNC -v  $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #2 error on $RUN"
      echo "Failed command: $RSYNC -v                                       $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC -v                                       $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #2 error on $RUN" skigodata@mskcc.org
      log_error "rsync #2 failed for IRIS run $RUN"
    fi # [ $? != 0 ]

    echo "Archived $SOURCE/$RUN to $DEST/$RUN `date`"
    log_info "Successfully archived IRIS run $RUN"
    
    chmod +x $DEST/$RUN
    if [ $? != 0 ]; then
        log_error "chmod failed for IRIS run $RUN"
    else
        log_info "Permissions set for IRIS run $RUN"
    fi
    
    echo "Archived $SOURCE/$RUN to $DEST/$RUN `date` on IRIS" | mail -s "Hashed and archived: $RUN" skigodata@mskcc.org
}

cd $SOURCE
RUNS=`ls -d */`
for RUN in $RUNS
 do
  if [ -e $RUN$READYFILE -a ! -e $DEST$RUN$ARCHFILE ]
   then
    rsync_run $RUN &
  fi # [ -e $RUN$READYFILE -a ! -e $DEST$RUN$ARCHFILE ]
 done

wait
rm $LOCK
echo "Completed $0. `date`"
log_info "Completed fastq_rsync_iris"
