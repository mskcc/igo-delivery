#!/bin/sh

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

for RUN in $RUNS
 do
  cd $RUN
   if [ -e $READYFILE -a ! -e fastq.md5.$MODE ]
    then
     echo "Generating $RUN fastq.md5.$MODE. `date`"
     find . -name \*\.fastq.gz ! -name '*Undetermined_*' -print0 | xargs -0 -n1 -P20 md5sum --tag | sort > fastq.md5.$MODE.partial
     mv fastq.md5.$MODE.partial fastq.md5.$MODE
     echo "Generated  $RUN fastq.md5.$MODE. `date`"
   fi # [ -e $READYFILE -a ! -e $TYPE.md5.$MODE ]
 done

rm $LOCK
echo "Completed FASTQ. `date`"
