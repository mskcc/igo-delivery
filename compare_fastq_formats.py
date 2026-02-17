#!/usr/bin/env python3
"""
Compare FASTQ naming formats across projects from ngs-stats.

Usage:
    python3 compare_fastq_formats.py 17123_D 17123_C 17123_B
    python3 compare_fastq_formats.py 17123_D  # single project analysis
"""

import subprocess
import json
import sys
from collections import defaultdict

NGS_STATS_ENDPOINT = "http://igodb.mskcc.org:8080/ngs-stats/permissions/getRequestPermissions/"

def get_fastqs(project_id):
    """Get FASTQ list from ngs-stats for a project using curl."""
    url = NGS_STATS_ENDPOINT + project_id
    try:
        result = subprocess.run(
            ["curl", "-s", url],
            capture_output=True,
            text=True
        )
        data = json.loads(result.stdout)
        return data.get("fastqs", [])
    except Exception as e:
        print(f"Error fetching {project_id}: {e}")
        return []

def extract_sample_folder(fastq_path):
    """Extract the sample folder name from a FASTQ path."""
    # Path format: /igo/delivery/FASTQ/<RUN>/Project_<PROJ>/Sample_<NAME>/file.fastq.gz
    parts = fastq_path.split("/")
    if len(parts) >= 7:
        return parts[6]  # Sample folder
    return None

def analyze_sample_format(sample_name):
    """Analyze the format of a sample folder name."""
    # Expected format: Sample_<SampleName>_IGO_<BaseId>
    # e.g., Sample_13-226-494E_beta_IGO_17123_D_97
    
    if not sample_name or not sample_name.startswith("Sample_"):
        return {"format": "unknown", "parts": {}}
    
    # Remove "Sample_" prefix
    remainder = sample_name[7:]
    
    # Try to find _IGO_ delimiter
    if "_IGO_" in remainder:
        parts = remainder.split("_IGO_")
        sample_part = parts[0]
        igo_part = parts[1] if len(parts) > 1 else ""
        
        # Count underscores in the IGO part to determine format
        igo_underscore_count = igo_part.count("_")
        
        return {
            "format": f"Sample_<name>_IGO_<base_id>",
            "sample_name": sample_part,
            "base_id": igo_part,
            "base_id_parts": igo_part.split("_"),
            "base_id_underscore_count": igo_underscore_count
        }
    else:
        return {"format": "no_IGO_delimiter", "raw": remainder}

def main():
    if len(sys.argv) < 2:
        print("Usage: python3 compare_fastq_formats.py <PROJECT_ID> [PROJECT_ID2] ...")
        print("Example: python3 compare_fastq_formats.py 17123_D 17123_C")
        sys.exit(1)
    
    projects = sys.argv[1:]
    all_formats = {}
    
    for project in projects:
        print(f"\n{'='*60}")
        print(f"Project: {project}")
        print('='*60)
        
        fastqs = get_fastqs(project)
        
        if not fastqs:
            print(f"  No FASTQs found for project {project}")
            continue
        
        # Extract unique sample folders
        sample_folders = set()
        for fq in fastqs:
            folder = extract_sample_folder(fq)
            if folder:
                sample_folders.add(folder)
        
        print(f"  Found {len(sample_folders)} unique sample folders")
        print()
        
        # Analyze formats
        format_counts = defaultdict(list)
        
        for folder in sorted(sample_folders):
            analysis = analyze_sample_format(folder)
            
            if "base_id_underscore_count" in analysis:
                format_key = f"base_id_parts={len(analysis['base_id_parts'])}"
                format_counts[format_key].append({
                    "folder": folder,
                    "base_id": analysis["base_id"],
                    "parts": analysis["base_id_parts"]
                })
            else:
                format_counts["other"].append({"folder": folder, "analysis": analysis})
        
        # Report findings
        print("  Format Analysis:")
        print("  " + "-"*50)
        
        for format_type, samples in sorted(format_counts.items()):
            print(f"\n  {format_type}: {len(samples)} samples")
            
            # Show examples
            for i, sample in enumerate(samples[:3]):  # Show first 3 examples
                print(f"    Example {i+1}: {sample['folder']}")
                if 'base_id' in sample:
                    print(f"              base_id: {sample['base_id']}")
                    print(f"              parts: {sample['parts']}")
            
            if len(samples) > 3:
                print(f"    ... and {len(samples) - 3} more")
        
        all_formats[project] = format_counts
    
    # Cross-project comparison
    if len(projects) > 1:
        print(f"\n{'='*60}")
        print("Cross-Project Format Comparison")
        print('='*60)
        
        for project, formats in all_formats.items():
            format_summary = ", ".join([f"{k}({len(v)})" for k, v in formats.items()])
            print(f"  {project}: {format_summary}")
        
        # Check if formats are consistent
        all_format_keys = [set(f.keys()) for f in all_formats.values()]
        if all(fk == all_format_keys[0] for fk in all_format_keys):
            print("\n  ✓ All projects have the same format types")
        else:
            print("\n  ✗ Projects have DIFFERENT format types!")
            for project, formats in all_formats.items():
                print(f"    {project}: {set(formats.keys())}")

if __name__ == "__main__":
    main()
