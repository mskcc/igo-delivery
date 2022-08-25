import sys
import shutil
import os
from pathlib import Path
import requests
import glob

special_group_accounts = ["cmoigo", "bicigo", "isabl"]

DLP_REQUIRED_ACCESS_LIST = ["havasove", "shahbot", "mcphera1", "grewald"]
TCRSEQ_REQUIRED_ACCESS_LIST = ["elhanaty","greenbab","lih7","havasove"]
LAB_SHARE_PATH = "/igo/delivery/share/"
ACL_TEMP_DIR = "/tmp/acls/"
NGS_STATS_ENDPOINT = "http://delphi.mskcc.org:8080/ngs-stats/permissions/getRequestPermissions/"
NGS_STATS_ENDPOINT_LAB = "http://delphi.mskcc.org:8080/ngs-stats/permissions/getLabPermissions/"
NGS_STATS_ENDPOINT_RECENT = "http://delphi.mskcc.org:8080/ngs-stats/rundone/getRecentlyArchivedRequests/"

# lab_name is optional
def set_request_acls(request, lab_name):
    print("Setting ACLs for request {} ".format(request))
    request_perms = get_request_metadata(request, "none")
    if request_perms is None:
        # Maybe the request is older than the LIMS, just give access to all lab members based on the folder such as 'pamere'
        if lab_name == "":
            print("Unknown request ID {}, quitting.".format(request))
            return
        else:
            print("No known LIMS data, granting permissions based on the lab folder: " + lab_name)
            #request_perms = get_lab_metadata(lab_name, request)
            request_perms = get_request_metadata(request, lab_name)
            temp_acl_file = request_perms.write_acl_temp_file()
            request_perms.grant_share_acls(temp_acl_file, True)
            request_perms.grant_fastq_acls(temp_acl_file)
            print("---")
            return
    temp_acl_file = request_perms.write_acl_temp_file()
    request_perms.grant_fastq_acls(temp_acl_file)
    request_perms.grant_share_acls(temp_acl_file, False)
    print("---")


def get_request_metadata(request, lab_name):
    url = NGS_STATS_ENDPOINT + request + "/" + lab_name
    print("Sending request {}".format(url))
    r = requests.get(url).json()
    # 'status': 500, 'error': 'Internal Server Error',
    if 'status' in r.keys() and r['status'] == 500:
        return None
    return RequestPermissions(r['labName'], r['labMembers'], r['request'], r['requestName'], r['requestReadAccess'], r['requestGroups'], r['dataAccessEmails'], r['fastqs'])


def get_lab_metadata(lab_name, request):
    url = NGS_STATS_ENDPOINT_LAB + lab_name
    print("Sending request {}".format(url))
    r = requests.get(url).json()
    # 'status': 500, 'error': 'Internal Server Error',
    if 'status' in r.keys() and r['status'] == 500:
        return None
    return RequestPermissions(r['labName'], r['labMembers'], request, '', '', '', '', '')


# fields from LIMS and fastq databases used to determine all ACLs
class RequestPermissions:
    def __init__(self, lab, members, request, requestName, request_members, groups, dataAccessEmails, fastqs):
        self.lab = lab
        self.members = members  # members of the lab
        self.request = request  # request ID such as 08822_X
        self.request_name = requestName
        self.request_members = request_members  # individuals/groups granted read access to the request
        self.groups = groups  # groups that need access per request
        self.data_access_emails = list(dataAccessEmails)
        self.fastqs = fastqs  # list of fastqs per request
        self.request_share_path = LAB_SHARE_PATH + self.lab + "/Project_" + self.request

        if self.request_name == "DLP":
            print("DLP requests must give access to {} ".format(DLP_REQUIRED_ACCESS_LIST))
            self.data_access_emails.extend(DLP_REQUIRED_ACCESS_LIST)
        if "TCRSeq" in self.request_name:
            print("TCRSeq requests must give access to {} ".format(TCRSEQ_REQUIRED_ACCESS_LIST))
            self.data_access_emails.extend(TCRSEQ_REQUIRED_ACCESS_LIST)

    # Grants ACLs to all fastq.gz files in a project, parent folders for the fastqs and SampleSheet.csv
    # For DLP runs ending in 'DLP' DIANA_0294_AHTGLJDSXY_DLP, grants read access to the 'Reports' and 'Stats' folders
    def grant_fastq_acls(self, temp_file_path):
        print("Setting ACLS for all {} fastqs in the request.".format(len(self.fastqs)))
        # nfs4_setfacl -S "/igo/delivery/FASTQ/acl_entries.txt" /igo/delivery/share/bergerm1/Project_06302_AM
        command_prefix = "nfs4_setfacl -S \"{}\"".format(temp_file_path)
        sample_folders = set()
        for fastq in self.fastqs:
            fastq_path = Path(fastq)
            if not fastq_path.exists():
                print("{} fastq.gz does not exist. Moving on.".format(fastq))
                continue

            # /igo/delivery/share/labname/Project_12345/MICHELLE_0682/Sample_mysample
            sample_folders.add(fastq_path.parent)

            set_acl_command = "{} {}".format(command_prefix, fastq)
            print(set_acl_command)
            result = os.system(set_acl_command)
            if result != 0:
                print("ERROR SETTING ACL - ".format(set_acl_command))
        project_folders = set()
        for sample_folder in sample_folders:
            set_acl_command = "{} {}".format(command_prefix, sample_folder)
            parent_path = Path(sample_folder).parent
            project_folders.add(parent_path)
            print(set_acl_command)
            result = os.system(set_acl_command)
            if result != 0:
                print("ERROR SETTING ACL at sample level - ".format(set_acl_command))
            sample_sheet = sample_folder.joinpath(Path("SampleSheet.csv"))
            if sample_sheet.exists():  # if SampleSheet.csv exists make it readable too
                set_acl_command = "{} {}".format(command_prefix, sample_sheet)
                os.system(set_acl_command)
            # check if *.yaml file exists for DLP projects and grant same access to it
            if glob.glob("{}/*.yaml".format(sample_folder)): # if os.system("test -f {}/*.yaml".format(sample_folder)) == 0:
                set_acl_command_yaml = "{} {}/*.yaml".format(command_prefix, sample_folder)
                print(set_acl_command_yaml)
                os.system(set_acl_command_yaml)
            run_folder = str(sample_folder.parent)
            if run_folder.endswith("DLP"):
                reports_folder = run_folder + "/Reports"
                reports_status = os.stat(reports_folder)
                # mask 4 means readable by all
                if str(oct(reports_status.st_mode)[-1:]) == "4":
                    print("Reports folder {} is already readable by all".format(reports_folder))
                else:
                    set_acl_reports = "nfs4_setfacl -R -S \"{}\" {}".format(temp_file_path, reports_folder)
                    print(set_acl_reports)
                    result = os.system(set_acl_reports)
        # /igo/delivery/FASTQ/MICHELLE_0284_BHVKK3DMXX/Project_09641_AS
        for project_folder in project_folders:
            set_acl_command = "{} {}".format(command_prefix, project_folder)
            print(set_acl_command)
            result = os.system(set_acl_command)
            if result != 0:
                print("ERROR SETTING ACL at project level - ".format(set_acl_command))

    def grant_share_acls(self, temp_file_path, recursively):
        if self.request_share_exists():
            print("Setting ACLS for all request share folders below " + self.request_share_path)
            # nfs4_setfacl -R(recursive)
            # nfs4_setfacl -R -S "/igo/archive/FASTQ/acl_entries.txt" /igo/delivery/share/lab/request
            set_acl_command = "nfs4_setfacl -R -S \"{}\" {}".format(temp_file_path, self.request_share_path)
            if recursively:
                set_acl_command = "nfs4_setfacl -R -L -S \"{}\" {}".format(temp_file_path, self.request_share_path)
            print(set_acl_command)
            result = os.system(set_acl_command)
            if result != 0:
                print("ERROR SETTING ACL - ".format(set_acl_command))
            #verify lab directory is readable by all since it has no ACLs set
            parent = os.path.dirname(self.request_share_path)
            mask = str(oct(os.stat(parent).st_mode)[-3:])
            if mask != "775":
                command = "chmod +rx {}".format(parent)
                print(command)
                os.system(command)
        else:
            print("{} share does not exist ".format(self.request_share_path))

    # Write the file with the ACLs to a temp location
    def write_acl_temp_file(self):  # just leave the temp files around for possible reference later
        temp_file_path = ACL_TEMP_DIR + self.lab + "_" + self.request + ".txt"
        temp_file = open(temp_file_path, "w")  # open to overwrite any existing content
        temp_file.write(self.get_acls())
        temp_file.close()
        # also write ACL file to the share dir if it exists for reference
        if self.request_share_exists():
            acl_file_copy_path = self.request_share_path + "/acl_permissions.txt"
            print("Copying ACL permissions file to {}".format(acl_file_copy_path))
            shutil.copy(temp_file_path, acl_file_copy_path)

        return temp_file_path

    # create the ACL list with all lab members and groups
    def get_acls(self):
        # make a set of users and set of groups from the labMembers table, request access table & dataAccessEmails
        # groups must be separate set because the ACL format is different ie "A:g:isabl@hpc.private:rxtncy"
        users_set = set()
        groups_set = set()

        # Already filtered via ngs_stats code -
        # email.endsWith("mskcc.org") & & !email.contains("zzPDL")) then dataAccessIDs.add(email.split("@")[0])
        print("Adding data access emails {}".format(self.data_access_emails))
        for email_id in self.data_access_emails:
            email_id = str(email_id).strip()
            if email_id != "skicmopm":
                users_set.add(email_id.lower())

        for group_name in self.groups:
            groups_set.add(group_name)
        for lab_member in self.members:
            if lab_member["group"]:
                groups_set.add(lab_member["member"])
            else:
                users_set.add(lab_member["member"])
        for r_member in self.request_members:
            if r_member["group"]:
                groups_set.add(r_member["member"])
            else:
                users_set.add(r_member["member"])

        acls = ""
        # Let's put groups on the top then individuals
        for group_name in groups_set:
            # TODO check if group name is valid?
            acls += "A:g:" + group_name + "@hpc.private:rxtncy\n"

        print("Checking if each account exists for all user IDs before trying to add the ACL with the id command")
        for user in users_set:
            user_exists_command = "id -u %s" % (user)
            user_exists_result = os.system(user_exists_command)
            if user_exists_result != 0:  # try again, for some reason the command occasionally fails when the id is valid
                user_exists_result = os.system(user_exists_command)
            if user_exists_result == 0:
                acls += "A::" + user + "@hpc.private:rxtncy\n"
            else:
                print("User {} does not exist, they should be removed from the DB.".format(user))

        owner_group_everyone = "A::OWNER@:rwaDxtTnNcCoy\nA::GROUP@:rxtncCy\nA::EVERYONE@:tncy\n"
        return acls + owner_group_everyone

    def request_share_exists(self):
        return os.path.isdir(self.request_share_path)


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 setaccess.py REQUEST=<request> | LABSHAREDIR=<directory> | ARCHIVEDWITHINLAST=<minutes>")
        return

    args = sys.argv[1]

    if args.startswith("REQUEST="):
        request = args[8:]
        set_request_acls(request, '')

    if args.startswith("LABSHAREDIR="):
        lab_folder = args[12:]
        print("Granting access permissions for {}".format(lab_folder))
        lab_name = os.path.basename(lab_folder)
        project_folders_list = [f.path for f in os.scandir(lab_folder) if f.is_dir()]
        for project_folder in project_folders_list:
            folder_name = os.path.basename(project_folder)
            # ./weigeltb/Project_05851_I_p1,Project_04495_si, ./rosenbj1/Project_06179_s1, ./rudinc/Project_06437_F_p1_Zp
            # ./bergerm1/Project_05500_AF_Im
            if folder_name.count("_") >= 3 or folder_name.find("_s") > 0:
                continue
            if folder_name.startswith("Project_"):  # ignore non Project_ folders
                request = folder_name.replace("Project_", "")
                set_request_acls(request, lab_name)
    if args.startswith("ARCHIVEDWITHINLAST="):
        minutes = args[19:]
        if int(minutes) > 70000:
            print("This request would take too long, exiting.")
            return
        getArchivedProjectsURL = NGS_STATS_ENDPOINT_RECENT + minutes
        print("Sending request {}".format(getArchivedProjectsURL))
        archivedProjects = requests.get(getArchivedProjectsURL).json()
        for project in archivedProjects:
            set_request_acls(project, '')


if __name__ == '__main__':
    main()
