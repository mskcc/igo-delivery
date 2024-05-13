# email group need to be added to ccList based on recipe and analysis type
addressMap = {
    "standard": ["zzPDL_ski_igo_delivery@mskcc.org"],  # will be added to every delivery, together with project LabHead and PI
    "impact": ["bicargos@mskcc.org"],
    "access": ["zzPDL_SKI_CMO_ACCESS@mskcc.org"],
    "wesWithCCS": ["zzPDL_CMO_TEMPO_Support@mskcc.org","skicmopm@mskcc.org"],
    "ccs": ["zzPDL_CMO_TEMPO_Support@mskcc.org","skicmopm@mskcc.org"],
    "pipelineDefault": ["bicrequest@mskcc.org"],
    "ski": ["skiinnovation@mskcc.org"],
    "CMO-CH": ["zzPDL_SKI_CMO_ACCESS@mskcc.org"],
    "TCRSeq": ["elhanaty@mskcc.org","greenbab@mskcc.org","lih7@mskcc.org","havasove@mskcc.org"],
    "DLP": ["HavasovE@mskcc.org", "mcphera1@mskcc.org"]
}

# when people use their ski address in submission, need to convert name based on their mskcc address
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

# recipe to delivery language
recipe_dict = {
    'ATAC': 'ATAC Sequencing',
    'HC_ACCESS': 'MSK-ACCESS',
    'HC_CMOCH': 'CMO-CH',
    'HC_Custom': 'Custom Capture',
    'HC_IMPACT': 'IMPACT',
    'HC_IMPACT-Heme': 'IMPACT-Heme',
    'HC_IMPACT-Mouse': 'Mouse IMPACT',
    'ddPCR': 'ddPCR',
    'DNA_Amplicon': 'Amplicon Sequencing',
    'DNA_ChIP': 'ChIP Sequencing',
    'DNA_CRISPR': 'CRISPR Sequencing',
    'DNA_CUT&RUN': 'CUT&RUN Sequencing',
    'DNA_SingleCellCNV': 'Single Cell CNV Sequencing',
    'Extraction_cfDNA': 'cfDNA Extraction',
    'Extraction_Dual': 'Dual DNA/RNA Extraction',
    'Extraction_DNA': 'DNA or RNA Extraction',
    'Extraction_RNA': 'DNA or RNA Extraction',
    'FA_CLA': 'Cell Line Authentication',
    'FA_Custom': 'Custom Fragment Analysis',
    'FA_Fingerprint': 'Tumor/Normal Fingerprinting',
    'Methyl_Capture': 'Methylation Capture Sequencing',
    'Methyl_WGS': 'Whole Genome Methylation Sequencing',
    'Nanopore_cDNA': 'Nanopore cDNA Sequencing',
    'Nanopore_Chromium': 'Nanopore 10X cDNA Sequencing',
    'Nanopore_Long-DNA': 'Nanopore Long Read DNA Sequencing',
    'Nanopore_RNA': 'Nanopore Direct RNA Sequencing',
    'Nanopore_Short-DNA': 'Nanopore Short Read DNA Sequencing',
    'PEDPEG': 'PED-PEG',
    'QC_DNA': 'DNA QC',
    'QC_Library': 'Library QC',
    'QC_RNA': 'RNA QC',
    'RNA_Capture': 'RNA Capture',
    'RNA_PolyA': 'RNA Seq - PolyA',
    'RNA_Ribodeplete': 'RNA Seq - Ribodepletion',
    'RNA_SMARTer-Cells': 'SMARTer from Cells',
    'RNA_SMARTer-RNA': 'RNA Seq - SMARTer',
    'SC_Chromium-ATAC': '10X scATAC Sequencing',
    'SC_Chromium-BCR': '10X scVDJ (BCR) Sequencing',
    'SC_Chromium-FB-3': '10X Feature Barcode/Hashtag Sequencing',
    'SC_Chromium-FB-5': '10X Feature Barcode/Hashtag Sequencing',
    'SC_Chromium-GEX-3': '10X scRNA-Seq',
    'SC_Chromium-GEX-5': '10X scRNA-Seq',
    'SC_Chromium-Multiome': '10X Multiome',
    'SC_Chromium-TCR': '10X scVDJ (TCR) Sequencing',
    'SC_DLP': 'DLP+',
    'SC_SmartSeq': 'SmartSeq (384-well)',
    'ST_CosMx': 'CosMx',
    'ST_GeoMx': 'GeoMx',
    'ST_Visium': 'Visium',
    'ST_Xenium': 'Xenium',
    'TCR_IGO': 'TCR Sequencing',
    'User_Amplicon': 'Amplicon Sequencing',
    'User_ATAC': 'ATAC Sequencing',
    'User_ChIP': 'ChIP Sequencing',
    'User_Chromium': '10X scRNA-Seq',
    'User_Chromium-ATAC': '10X scATAC Sequencing',
    'User_Methyl': 'Methylation Sequencing',
    'User_MissionBio': 'MissionBio',
    'User_RNA': 'RNA Sequencing',
    'User_shRNA': 'shRNA Sequencing',
    'User_SingleCellCNV': 'Single Cell CNV Sequencing',
    'User_WGBS': 'Whole Genome Bisulfite Sequencing',
    'User_WGS': 'Whole Genome Sequencing',
    'WES_Human': 'Whole Exome Sequencing',
    'WES_Mouse': 'Mouse Whole Exome Sequencing',
    'WGS_Deep': 'Whole Genome Sequencing (deep or PCR-free)',
    'WGS_Metagenomic': 'Metagenomic Sequencing',
    'WGS_Shallow': 'Shallow Whole Genome Sequencing'
}

# email template
genericSubject= "[IGO Data] %s Project %s "

genericContent = "Hello,<br><br>The FASTQ files for your %s Project %s have been posted to the <b>%s</b> shared drive. Detailed instructions available at: <a href='http://genomics.mskcc.org/accessing-your-data/'> genomics.mskcc.org/accessing-your-data </a>"

nonMSKContent = "Hello,<br><br>The FASTQ files for your %s Project %s are ready. We could not identify a shared drive for %s. Please reach out to skigodata@mskcc.org to discuss how you can access your data."

fastQOnlyContent = "Hello,<br><br>The FASTQ files for your %s Project %s have been posted to the %s shared drive. Detailed instructions available at: <a href='http://genomics.mskcc.org/accessing-your-data/'> genomics.mskcc.org/accessing-your-data </a>"

impactContent = "Hello,<br><br>IGO processing is now complete. FASTQ files for your %s Project %s have been posted to the <b>%s</b> shared drive and transferred to the Bioinformatics Core for pipeline analysis. You will be contacted when results are ready."

wesWithCCSContent = "Hello,<br><br>IGO processing is now complete. FASTQ files for your %s Project %s have been posted to the <b>%s</b> shared drive and transferred to the CMO Computational Sciences (CCS) Team for pipeline analysis. Please contact your Project Manager for updates."

accessContent = "Hello,<br><br>IGO processing is now complete. FASTQ files for your %s Project %s have been posted to the <b>%s</b> shared drive and transferred to the ACCESS Analysis Team for data quality control and standard data processing. Please contact your Project Manager for further updates."

genericAnalysisContent = "Hello,<br><br>IGO processing is now complete. FASTQ files for your %s Project %s have been posted to the <b>%s</b> shared drive and are accessible to the Bioinformatics Core (BIC). Please go to <a href='https://bic.mskcc.org/bic/services/request/'>https://bic.mskcc.org/bic/services/request/</a> to initiate a request for analysis. For information about accessing your fastq files, please go to <a href='http://genomics.mskcc.org/accessing-your-data/'> genomics.mskcc.org/accessing-your-data </a>"

crisprAddon = "<br>In addition, you will receive the results of the CRISPResso analysis, generated by the CRISPResso2 software. <br> For a detailed description of the output please consult https://crispresso.pinellolab.partners.org/help "

RNASeqAddon = "<br>In addition, IGO also delivers BAM files for your project. A detailed description of the BAM generation command can be found <a href='https://genomics.mskcc.org/accessing-your-data#deliverables'> Data & Delivery </a>"

SamplePickUpAddon = "<br><br><b>IGO's Sample Discard/Return Policy:</b> <br><br>Leftover biomaterial (tissue, DNA, RNA, etc.) submitted to IGO for processing will be discarded 24 months after submission of the project. You will have to proactively request your leftover material. Please click <a style='text-decoration: underline' href='mailto:igosampleprojmgmt@mskcc.org?subject=%5BIGO%20Sample%20Pickup%5D&amp;body=The%20following%20plates%20are%20requested%20for%20pickup%3A%20%0A'>here</a> to email IGO to schedule a pick up."

UserSamplePickUpAddon = "<br><br><b>IGO's Sample Discard/Return Policy:</b> <br><br>Any samples not picked up within 1 week of FASTQ delivery will be discarded. Please click <a style='text-decoration: underline' href='mailto:igosampleprojmgmt@mskcc.org?subject=%5BIGO%20Sample%20Pickup%5D&amp;body=The%20following%20plates%20are%20requested%20for%20pickup%3A%20%0A'>here</a> to email IGO to schedule a pick up."

DataStoragePolicyAddon = "<br><br><b>IGO's Data Storage Policy:</b><ul><li>FASTQ files will be linked to the project folder for 3 years</li><li>BAM files will be available for 6 months</li><li>Pipeline files (such as Cell Ranger) will be available for 3 months</li><li>POD5 files will be available for 30 days</li></ul>Deleted FASTQ, BAM, and pipeline files can be regenerated using an iLab request for a fee. <b>Deleted POD5 files cannot be recovered</b>."

FOOTER = "<br><br>Thank you, <br><a href='http://genomics.mskcc.org/'>Integrated Genomics Operation</a><br><a href='https://www.mskcc.org'>Memorial Sloan Kettering Cancer Center</a><br>Follow us on <a href='https://www.instagram.com/genomics212/?hl=en'>Instagram</a> and <a href='https://twitter.com/genomics212?lang=en'>Twitter</a>!<br><br>Please rate your delivery experience <a href='https://genomics.mskcc.org/feedback/data-delivery'>here</a><br>"
