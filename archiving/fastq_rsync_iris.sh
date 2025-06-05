#!/bin/bash
# Adapted from ~pepper/bin scripts run from 2011-2019
# A run should be copied when the fastq.md5.input file exists but no ARCHIVED file exists

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

function rsync_run {
    RUN=$1

    echo "Archiving $SOURCE/$RUN `date`"
    $RSYNC --exclude=$ARCHFILE $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #1 error on $RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #1 error on $RUN" naborsd@mskcc.org,luc@mskcc.org
    fi # [ $? != 0 ]

    /usr/bin/chmod +x $DEST/$RUN

    date >> $DEST$RUN$ARCHFILE
    
    $RSYNC -v  $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #2 error on $RUN"
      echo "Failed command: $RSYNC -v                                       $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC -v                                       $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #2 error on $RUN" skigodata@mskcc.org
    fi # [ $? != 0 ]

    echo "Archived $SOURCE/$RUN to $DEST/$RUN `date`"
    #chgrp -R igo $DEST/$RUN
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
