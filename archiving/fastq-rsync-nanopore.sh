#!/bin/bash
# Copy/Paste/Modify of the main fastq rsync script specific for Oxford Nanopore data
# A run should be copied when the READYFILE file exists but no ARCHFILE file exists

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPLUNK_LOG="$SCRIPT_DIR/splunk_log.py"
SCRIPT_NAME="fastq-rsync-nanopore"

log_info()  { python3 "$SPLUNK_LOG" "$SCRIPT_NAME" INFO "$1" 2>/dev/null || echo "[INFO] $1"; }
log_error() { python3 "$SPLUNK_LOG" "$SCRIPT_NAME" ERROR "$1" 2>/dev/null || echo "[ERROR] $1"; }

READYFILE=ARCHIVE
ARCHFILE=ARCHIVED_AT_IGO
SOURCE=/igo/staging/promethion/
DEST=/igo/delivery/nanopore
LOCK=/home/seqdataown/.md5locks/igo-storage-nanopore.lock
RSYNC="rsync -a --no-links  --exclude=nohup.out "

if [ -f $LOCK ]
 then
  echo "Per $LOCK, $0 is already running. `date`"
  exit 2
fi

touch $LOCK
echo
echo "Starting  $0. `date`"
log_info "Starting fastq-rsync-nanopore"

function rsync_run {
    RUN=$1
    chmod +x $SOURCE/$RUN

    echo "Archiving $SOURCE/$RUN `date`"
    log_info "Starting rsync for nanopore run $RUN"
    $RSYNC --exclude=$ARCHFILE $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #1 error on $RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #1 error on $RUN" skigodata@mskcc.org
      log_error "rsync #1 failed for nanopore run $RUN"
    fi # [ $? != 0 ]

    /usr/bin/chmod +x $DEST/$RUN

    date >> $RUN$ARCHFILE
    # Copy again, and this time include the new marker file
    $RSYNC -v  $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #2 error on $RUN"
      echo "Failed command: $RSYNC -v                                       $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC -v                                       $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #2 error on $RUN" skigodata@mskcc.org
      log_error "rsync #2 failed for nanopore run $RUN"
    fi # [ $? != 0 ]

    echo "Archived $SOURCE/$RUN to $DEST/$RUN `date`"
    log_info "Successfully archived nanopore run $RUN"
    
    log_info "Setting permissions for nanopore run $RUN"
    chgrp -R igo $DEST/$RUN
    if [ $? != 0 ]; then
        log_error "chgrp failed for nanopore run $RUN"
    fi
    
    nfs4_setfacl -R -S "/igo/delivery/FASTQ/acl_entries.txt" /nfs4/$DEST/$RUN
    if [ $? != 0 ]; then
        log_error "nfs4_setfacl failed for nanopore run $RUN"
    fi
    
    log_info "Permissions set successfully for nanopore run $RUN"
    
    # /usr/bin/chmod +x $DEST/$RUN
    echo "Hashed and archived: $RUN" | mail -s "Hashed and archived: $RUN" skigodata@mskcc.org
    curl "http://delphi.mskcc.org:8080/ngs-stats/rundone/fastq/$RUN" &
}

cd $SOURCE
RUNS=`ls -d */`
for RUN in $RUNS
 do
  if [ -e $RUN$READYFILE -a ! -e $RUN$ARCHFILE ]
   then
    rsync_run $RUN &
  fi # [ -e $RUN$READYFILE -a ! -e $RUN$ARCHFILE ]
 done

wait
rm $LOCK
echo "Completed $0. `date`"
log_info "Completed fastq-rsync-nanopore"
