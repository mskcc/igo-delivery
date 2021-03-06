# igo-delivery
Delivery email, symlinks and permissions for IGO projects

## Three main functions:
1. EmailDelivered.py for sending out notification emails
2. LinkProjectToSamples.py for creating symlinks of fastq files based on NGS database data
3. setaccess.py for setting permissions for each project

## Usage:

1. EmailDelivered.py need two arguments: mode and time length. Mode has two options, TEST and PROD which test mode will only print out email content. The unit for time length is minutes. Default is test mode and 30 minutes.
  ```
  python3 EmailDelivered.py PROD 30
  ```
2. LinkProjectToSamples.py has two different type of usage, either link by request or link by time period. If by time period, the unit is minutes.
```
python3 LinkProjectToSamples.py REQUEST=12345
```
```
python3 LinkProjectToSamples.py TIME=30
```
3. setaccess.py has three different type of usage, by project, by lab head folder or by time period. If by time period, the unit is minutes.
```
python3 setaccess.py REQUEST=12345
```
```
python3 setaccess.py LABSHAREDIR=abc
```
```
python3 setaccess.py ARCHIVEDWITHINLAST=30
```
