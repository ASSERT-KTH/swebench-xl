import json
import shutil
from pathlib import Path

def main():
    # Define paths relative to script location
    script_dir = Path(__file__).parent #/harbor directory

    jsonl_file = script_dir / ".." / "benchmark" / "filtered_dataset.jsonl"
    base_dockerfile = script_dir / ".." / "benchmark" / "dockerfiles" / "base"
    instance_dockerfile = script_dir / ".." / "benchmark" / "dockerfiles" / "instances"
    dest_base = script_dir / "dockerfiles" / "base_dockerfile"
    dest_instance = script_dir / "dockerfiles" / "instance_dockerfile"
    
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
        source_dir = instance_dockerfile / instance_id
        dest_dir_instance = dest_instance / instance_id
        dest_dir_base = dest_base / instance_id
        
        if not source_dir.exists():
            print(f"Warning: Source directory does not exist: {source_dir}")
            skipped += 1
            continue
        
        if dest_dir_instance.exists():
            print(f"Destination already exists, removing: {dest_dir_instance}")
            shutil.rmtree(dest_dir_instance)
        
        try:
            shutil.copytree(source_dir, dest_dir_instance)
            shutil.copytree(base_dockerfile, dest_dir_base)
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

