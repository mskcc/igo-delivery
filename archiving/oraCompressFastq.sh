#!/bin/bash
# a program to compress a fastq.gz into .ora and store the .fastq md5sum
# Must be run as user seqdataown on id01

echo "Processing: $1";

FASTQ=$1
# remove .gz from fastq.gz filename
FASTQONLY=`echo $FASTQ | cut -d "." -f1,2`
FASTQ_TIMESTAMP=`stat -c '%y' $FASTQ`
FASTQ_DIRECTORY=`dirname $FASTQ`

echo "gunzip -c $FASTQ > $FASTQONLY"
gunzip -c $FASTQ > $FASTQONLY

echo "md5sum $FASTQONLY > $FASTQONLY'.md5'"
md5sum $FASTQONLY > $FASTQONLY'.md5'

echo "dragen ora compression started for $FASTQONLY"
dragen  --enable-map-align false --ora-input $FASTQONLY --enable-ora true --ora-reference /igo/work/igo/DRAGEN-compression/lenadata-1 --output-directory $FASTQ_DIRECTORY

echo "Setting .ora last modified timestamp to $FASTQ_TIMESTAMP"
touch -m -d "$FASTQ_TIMESTAMP" $FASTQONLY".ora"

chgrp igo $FASTQONLY".ora"
chgrp igo $FASTQONLY'.md5'
rm $FASTQONLY

cd /igo/work/mcmanamd/orad_2_5_5/

/igo/work/mcmanamd/orad_2_5_5/orad $FASTQONLY".ora" --check

#cleanup DRAGEN files
cd $FASTQ_DIRECTORY
rm dragen-replay.json dragen.time_metrics.csv streaming_log_seqdataown.csv 2210019CK07T*_usage.txt
