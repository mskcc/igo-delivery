import requests
from requests.exceptions import HTTPError
import os
import smtplib
from email.mime.text import MIMEText
import socket

LIMS_ENDPOINT = "https://igolims.mskcc.org:8443/LimsRest"
file1 = open('ConnectLimsRest.txt', 'r')
allLines = file1.readlines()
username = allLines[0].strip()
password = allLines[1].strip()
id_to_exclude = ["svc_shah3_bot", "shahbot", "skicmopm", "zzpdl_ski_isabl"]

# get user id list from lims
def get_user_list_weekly():
    limsurl = LIMS_ENDPOINT + "/getDataAccessEmails"
    try:
        response = requests.get(limsurl, auth=(username, password), verify=False)
        response.raise_for_status()
        user_list = response.json()

    except HTTPError as http_err:
        print(f'HTTP error occurred: {http_err}')

    return user_list

# remove @mskcc.org and remove non-msk email
def parse_user_list(user_list):
    id = []
    for user in user_list:
        item = user.split("@")
        if len(item) == 2 and item[1] == "mskcc.org":
            id.append(item[0])
    return id

# check if the user is in the database
def check_id(id):
    id_to_add = []
    for user in id:
        user_exists_command = "id -u %s" % (user)
        user_exists_result = os.system(user_exists_command)
        if user_exists_result != 0:  # try again, for some reason the command occasionally fails when the id is valid
            user_exists_result = os.system(user_exists_command)
        if user_exists_result == 0:
            continue
        else:
            if user not in id_to_exclude:
                id_to_add.append(user)
    return id_to_add

# send email    
def notify(email):
        msg = MIMEText(email["content"], "html")
        msg['Subject'] = email["subject"]
        msg['From'] = "igoski@mskcc.org"
        msg['To'] = "zzPDL_SKI_IGO_DATA@mskcc.org"
        s = smtplib.SMTP('localhost')
        s.sendmail("igoski@mskcc.org", "zzPDL_SKI_IGO_DATA@mskcc.org", msg.as_string())
        s.close()

if __name__ == '__main__':
    cluster = "Lilac/Juno"
    if socket.gethostname().startswith("isvigoacl01"):
        cluster = "IRIS"
    user_list = get_user_list_weekly()
    id = parse_user_list(user_list)
    id_to_add = check_id(id)
    print(id_to_add)
    email = {}
    email["content"] = ", ".join(id_to_add)
    email["subject"] = "id to add for cluster {}".format(cluster)
    notify(email)
    