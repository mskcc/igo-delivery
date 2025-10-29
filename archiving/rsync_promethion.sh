#!/bin/bash
# Copy runs off the Oxford Nanopore Promethion, only allow one rsync to run on the machine at a time

ARCHFILE=COPIED
SOURCE=/data
DEST=igo@igo-ln01:/igo/staging/promethion
LOCK=/home/igo/.md5locks/rsync.lock
RSYNC="rsync -a --no-links --exclude=nohup.out "

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
    #chmod +x $SOURCE/$RUN

    echo "Archiving $SOURCE/$RUN `date` from $SOURCE/$RUN to $DEST/$RUN"
    $RSYNC --exclude=$ARCHFILE $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #1 error on $RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #1 error on $RUN" skigodata@mskcc.org
    fi # [ $? != 0 ]

    date >> $RUN$ARCHFILE
    # Copy again, and this time include the new marker file
    $RSYNC -v  $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #2 error on $RUN"
      echo "Failed command: $RSYNC -v                                       $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC -v                                       $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #2 error on $RUN" skigodata@mskcc.org
    fi # [ $? != 0 ]

    echo "Archived $SOURCE/$RUN to $DEST/$RUN `date`"
}

cd $SOURCE
RUNS=`ls -d Project_*/`
for RUN in $RUNS
 do
  if [ ! -e $RUN$ARCHFILE ]
   then
    rsync_run $RUN &
  fi 
 done

wait
rm $LOCK
echo "Completed $0. `date`"
