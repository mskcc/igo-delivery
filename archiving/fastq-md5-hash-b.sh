#!/bin/sh

MODE=archive
RUNS=/igo/delivery/FASTQ/*/
LOCK=/home/seqdataown/.md5locks/FASTQ_HASHING_ARCHIVE
READYFILE=ARCHIVED

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
   if [ -e $READYFILE -a ! -e fastq.md5.$MODE ]
    then
     echo "Generating $RUN fastq.md5.$MODE. `date`"
     find . -name \*\.fastq.gz -print0 | xargs -0 -n1 -P20 md5sum --tag | sort > fastq.md5.$MODE.partial
     mv fastq.md5.$MODE.partial fastq.md5.$MODE
     echo "Generated  $RUN fastq.md5.$MODE. `date`"

     if [ $MODE = archive ]
      then
      RUNNAME=$(basename $RUN)
       curl "http://delphi.mskcc.org:8080/ngs-stats/rundone/fastq/$RUNNAME" &
       (diff -qs fastq.md5.input fastq.md5.archive; wc -l fastq.md5.*) | mail -s "Hashed and archived: $RUN" mcmanamd@mskcc.org,naborsd@mskcc.org
     fi # [ $MODE = archive ]
   fi # [ -e $READYFILE -a ! -e $TYPE.md5.$MODE ]
 done

rm $LOCK
echo "Completed FASTQ Final Hash. `date`"
