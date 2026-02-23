import json
import shutil
from pathlib import Path

def main():
    # Define paths relative to script location
    script_dir = Path(__file__).parent #/harbor directory

    jsonl_file = script_dir / ".." / "swe-bench++tools" / "final_consistent_instances.jsonl"
    source_base = script_dir / ".." / "benchmark" / "run_scripts"
    dest_base = script_dir / "run_scripts"
    parser_file = script_dir / ".." / "benchmark" / "parser.py"
    
    # Create destination base directory if it doesn't exist
    dest_base.mkdir(parents=True, exist_ok=True)
    
    # Read instances from jsonl file
    instances = []
    with open(jsonl_file, 'r') as f:
        for line in f:
            data = json.loads(line.strip())
            instances.append(data['instance_id'])
    
    print(f"Found {len(instances)} instances to copy")
    
    # Copy each instance directory
    copied = 0
    skipped = 0
    errors = 0
    
    for instance_id in instances:
        source_dir = source_base / instance_id
        dest_dir = dest_base / instance_id
        
        if not source_dir.exists():
            print(f"Warning: Source directory does not exist: {source_dir}")
            skipped += 1
            continue
        
        if dest_dir.exists():
            print(f"Destination already exists, removing: {dest_dir}")
            shutil.rmtree(dest_dir)
        
        try:
            shutil.copytree(source_dir, dest_dir)
            shutil.copy(parser_file, dest_dir / "parser.py")
            copied += 1
            print(f"Copied {instance_id}")
        except Exception as e:
            print(f"Error copying {instance_id}: {e}")
            errors += 1
    
    print(f"\nSummary:")
    print(f"  Copied: {copied}")
    print(f"  Skipped: {skipped}")
    print(f"  Errors: {errors}")
    print(f"  Total: {len(instances)}")

if __name__ == "__main__":
    main()

