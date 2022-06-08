addressMap = {
    "standard": ["zzPDL_ski_igo_delivery@mskcc.org"],  # will be added to every delivery, together with project LabHead and PI
    "impact": ["zzPDL_CMO_Pipeline_Support@mskcc.org"],
    "access": ["zzPDL_SKI_CMO_ACCESS@mskcc.org"],
    "wesWithCCS": ["zzPDL_CMO_TEMPO_Support@mskcc.org","skicmopm@mskcc.org"],
    "ccs": ["zzPDL_CMO_TEMPO_Support@mskcc.org","skicmopm@mskcc.org"],
    "pipelineDefault": ["bic-request@cbio.mskcc.org"],
    "ski": ["skiinnovation@mskcc.org"]
}

aliases = {
    "a-haimovitz-friedman@ski.mskcc.org": "haimovia",
    "a-zelenetz@mskcc.org": "zeleneta",
    "a-zelenetz@ski.mskcc.org": "zeleneta",
    "d-scheinberg@ski.mskcc.org": "scheinbd",
    "f-giancotti@ski.mskcc.org": "giancotf",
    "j-massague@ski.mskcc.org": "massaguej",
    "k-anderson@ski.mskcc.org": "kanderson",
    "m-baylies@ski.mskcc.org": "bayliesm",
    "m-jasin@ski.mskcc.org": "jasinm",
    "m-mcdevitt@ski.mskcc.org": "m-mcdevitt",
    "m-moore@ski.mskcc.org": "moorem",
    "m-ptashne@ski.mskcc.org": "ptashne",
    "m-sadelain@ski.mskcc.org": "sadelaim",
    "m-van-den-brink@ski.mskcc.org": "vandenbm",
    "p-tempst@ski.mskcc.org": "tempstp",
    "r-benezra@ski.mskcc.org": "benezrar",
    "r-kolesnick@ski.mskcc.org": "rkolesnick",
    "s-keeney@ski.mskcc.org": "keeneys",
    "s-shuman@ski.mskcc.org": "sshuman",
    "w-mark@ski.mskcc.org": "markw"
}

DEFAULT_ADDRESS = "zzPDL_SKI_IGO_DATA@mskcc.org"
SKI_SENDER_ADDRESS = "igoski@mskcc.org"
MSKCC_ADDRESS = "YOUR_MSKCC_ADDRESS"
NO_PM = "NO PM"

# TODO add share drive name and access instruction to email body for all?
genericSubject= "[IGO Data] %s Project %s "

genericContent = "Hello,<br><br>The FASTQ files for your %s Project %s have been posted to the %s shared drive. Detailed instructions available at: <a href='http://genomics.mskcc.org/accessing-your-data/'> genomics.mskcc.org/accessing-your-data </a>"

nonMSKContent = "Hello,<br><br>The FASTQ files for your %s Project %s are ready. We could not identify a shared drive for %s. Please reach out to zzPDL_SKI_IGO_DATA@mskcc.org to discuss how you can access your data."

fastQOnlyContent = "Hello,<br><br>The FASTQ files for your %s Project %s have been posted to the %s shared drive. Detailed instructions available at: <a href='http://genomics.mskcc.org/accessing-your-data/'> genomics.mskcc.org/accessing-your-data </a>"

impactContent = "Hello,<br><br>IGO processing is now complete. FASTQ files for your %s Project %s have been posted to the %s shared drive as well as transferred to the CMO Analysis Support (CAS) Team, for pipeline analysis. You will be contacted when this project is delivered to cBioPortal."

wesWithCCSContent = "Hello,<br><br>IGO processing is now complete.FASTQ files for your %s Project %s have been transferred to the CMO Computational Sciences (CCS) Team, for pipeline analysis. Please contact your Project Manager for updates."

accessContent = "Hello,<br><br>IGO processing is now complete. FASTQ files for your %s Project %s have been transferred to the ACCESS Analysis Team, for data quality control and standard data processing. Please contact your Project Manager for further updates."

genericAnalysisContent = "Hello,<br><br>IGO processing is now complete. FASTQ files for your %s Project %s are accessible to the Bioinformatics Core (BIC). Please go to <a href='https://bic.mskcc.org/bic/services/request/'>https://bic.mskcc.org/bic/services/request/</a> to initiate a request for analysis. "

crisprAddon = "<br>In addition, you will receive the results of the CRISPResso analysis, generated by the CRISPResso2 software. <br> For a detailed description of the output please consult https://crispresso.pinellolab.partners.org/help "

FOOTER = "<br><br>Thank you, <br><a href='http://genomics.mskcc.org/'>Integrated Genomics Operation</a><br><a href='https://www.mskcc.org'>Memorial Sloan Kettering Cancer Center</a><br>Follow us on <a href='https://www.instagram.com/genomics212/?hl=en'>Instagram</a> and <a href='https://twitter.com/genomics212?lang=en'>Twitter</a>!<br><br>Please rate your delivery experience <a href='https://genomics.mskcc.org/feedback/data-delivery'>here</a><br>"
