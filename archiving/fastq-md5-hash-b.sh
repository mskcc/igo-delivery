#!/bin/bash
# Generate md5 hash for all fastq.gz files on a run

RUNS=/igo/delivery/FASTQ/*/
LOCK=/home/seqdataown/.md5locks/FASTQ_HASHING_ARCHIVE
READYFILE=ARCHIVED_AT_IGO

if [ -f $LOCK ]
 then
  echo "Per $LOCK, FASTQ hashing is already running. `date`"
  exit 2
fi

touch $LOCK
echo
echo "Starting  $0. `date`"

for RUN in $RUNS
 do
  cd $RUN
   if [ -e $READYFILE -a ! -e fastq.md5.archive ]
    then
     echo "Generating $RUN fastq.md5.archive. `date`"
     find . -name \*\.fastq.gz -print0 | xargs -0 -n1 -P20 md5sum --tag | sort > fastq.md5.archive.partial
     mv fastq.md5.archive.partial fastq.md5.archive
     echo "Generated  $RUN fastq.md5.archive. `date`"
     
     RUNNAME=$(basename $RUN)
     curl "http://igodb.mskcc.org:8080/ngs-stats/rundone/fastq/$RUNNAME" &
     (diff -qs fastq.md5.input fastq.md5.archive; wc -l fastq.md5.*) | mail -s "Hashed and archived: $RUN" timalr@mskcc.org,luc@mskcc.org,naborsd@mskcc.org
   fi # [ -e $READYFILE -a ! -e $TYPE.md5.archive ]
 done

rm $LOCK
echo "Completed FASTQ Final Hash. `date`"
