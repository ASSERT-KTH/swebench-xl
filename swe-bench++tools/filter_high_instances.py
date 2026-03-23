import argparse
import json


def _load_json(path):
	with open(path, "r", encoding="utf-8") as f:
		return json.load(f)


def _collect_high_quality_ids(results):
	return {
		item.get("instance_id")
		for item in results
		if str(item.get("quality", "")).strip().lower() == "high" and item.get("instance_id")
	}


def main():
	parser = argparse.ArgumentParser(
		description="Create a copy of validated_instances.json containing only instances rated High quality."
	)
	parser.add_argument(
		"--validated",
		default="../benchmark-pipeline/validated_instances.json",
		help="Path to validated_instances.json",
	)
	parser.add_argument(
		"--ratings",
		default="semantic_alignment_results_new.json",
		help="Path to semantic alignment ratings JSON",
	)
	parser.add_argument(
		"--output",
		default="../benchmark-pipeline/validated_instances_high_quality.json",
		help="Path for filtered output JSON",
	)
	args = parser.parse_args()

	validated_instances = _load_json(args.validated)
	ratings = _load_json(args.ratings)

	high_quality_ids = _collect_high_quality_ids(ratings)
	filtered = [
		instance
		for instance in validated_instances
		if instance.get("status") == "verified" and instance.get("instance_id") in high_quality_ids
	]

	with open(args.output, "w", encoding="utf-8") as f:
		json.dump(filtered, f, indent=2)

	print(f"Loaded {len(validated_instances)} instances from {args.validated}")
	print(f"Loaded {len(ratings)} ratings from {args.ratings}")
	print(f"Found {len(high_quality_ids)} unique High quality instance IDs")
	print(f"Saved {len(filtered)} instances to {args.output}")


if __name__ == "__main__":
	main()
