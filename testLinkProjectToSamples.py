import LinkProjectToSamples

test_json_info = LinkProjectToSamples.get_NGS_stats("11116_S")
test_sample = LinkProjectToSamples.NGS_Stats(test_json_info)
def test_create_NGS_Stats():
    assert (test_sample.labName == "landgrec")
    assert (test_sample.samples["Sample_PROTEIN_SAM1_IGO_11116_S_1"] == ['RUTH_0084_AHWWTHDSX2_mb', 'RUTH_0084_AHWWTHDSX2'])

def test_trimRunID():
    runID = "AYYAN_0118_000000000-GB4RY"
    trimmedRunID = LinkProjectToSamples.trimRunID(runID)
    assert (trimmedRunID == "AYYAN_0118")
