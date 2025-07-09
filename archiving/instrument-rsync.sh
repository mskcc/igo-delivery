#!/bin/sh
# Adapted from ~pepper/bin scripts run from 2011-March 2019
# Copy runs from gclisi:/ifs/input/ to solarc:/ifs/archive/.
# A run should be copied when the ready file exists but no ARCHIVED file exists
# The last file written by each sequencer is not in Illumina documentation, they
# communicate that information verbally or by email

# either diana, jax, johnsawyers, kim, liz, michelle, momo, pitt, scott, toms, vic, ayyan
INSTRUMENT=$1
# READYFILE is either RTAComplete.txt, SequencingComplete.txt, RunCompletionStatus.xml, CopyComplete.txt
case "$1" in
  'diana' | 'michelle') # NovaSeq
    READYFILE="CopyComplete.txt"
    ;; 
  'jax' | 'pitt') # HiSeq 4000
    READYFILE='SequencingComplete.txt'
    ;;
  'johnsawyers' | 'toms' | 'vic' | 'ayyan') # MiSeq
    READYFILE='RTAComplete.txt'
    ;;
  'kim' | 'momo' | 'liz') # HiSeq 2500
    READYFILE='RTAComplete.txt'
    ;;
  'scott' ) # NextSeq
    READYFILE='RunCompletionStatus.xml'
    ;;
  *) echo "Sequencer Unknown" ; exit
esac

ARCHFILE=ARCHIVED
ARCHFILEDIR=/home/seqdataown/archived/$INSTRUMENT/
SOURCE=/igo/sequencers/$INSTRUMENT
DEST=/ifs/archive/GCL/hiseq/$INSTRUMENT
LOCK=/home/seqdataown/.locks/archiving-nonfastq-$INSTRUMENT.lock
RSYNC="rsync -a --exclude=*.cif --exclude=*.bcl --exclude=Intensities/BaseCalls/* --exclude=*.cbcl --exclude=*.filter --exclude=*.bcl.gz --exclude=nohup.out "

if [ -f $LOCK ]
 then
  echo "Per $LOCK, $0 is already running. `date`"
  exit 2
fi

touch $LOCK
echo
echo "Starting  $0. `date`"

cd $SOURCE
RUNS=`ls -d */` 
for RUN in $RUNS  # ~30s when no work to do
 do
  RUNNAME=$(basename $RUN)
  echo $ARCHFILEDIR$RUNNAME$ARCHFILE
  if [ -e $RUN$READYFILE -a ! -e $ARCHFILEDIR$RUNNAME ]
   then
    curl "http://delphi.mskcc.org:8080/ngs-stats/rundone/sequencerstartstop/$INSTRUMENT/$RUN/$READYFILE/igoStorage" &
    # This is the main copy, it may run for hours
    echo "Archiving $SOURCE/$RUN `date`"
    $RSYNC $SOURCE/$RUN $DEST/$RUN
    if [ $? != 0 ]
     then
      echo "$0: rsync #1 error on $RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN"
      echo "Failed command: $RSYNC $SOURCE/$RUN $DEST/$RUN" | mail -s "$0: rsync #1 error on $RUN" timalr@mskcc.org,naborsd@mskcc.org,luc@mskcc.org
    fi # [ $? != 0 ]

    touch $ARCHFILEDIR$RUNNAME
    echo "Archived $SOURCE/$RUN to $DEST/$RUN `date`"
  fi # [ -e $RUN$READYFILE -a ! -e $RUN$ARCHFILE ]
 done

rm $LOCK
echo "Completed $0. `date`"
