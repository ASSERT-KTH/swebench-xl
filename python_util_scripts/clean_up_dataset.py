#!/usr/bin/env python3
import os
import json
import shutil
import sys

def main():
	root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
	dataset = os.path.join(root, 'benchmark', 'dataset.jsonl')
	harbor = os.path.join(root, 'harbor_tasks')

	if not os.path.isdir(harbor):
		print('harbor_tasks directory not found at', harbor, file=sys.stderr)
		sys.exit(1)
	if not os.path.isfile(dataset):
		print('dataset.jsonl not found at', dataset, file=sys.stderr)
		sys.exit(1)

	dirs = {name for name in os.listdir(harbor) if os.path.isdir(os.path.join(harbor, name))}
	if not dirs:
		print('no directories found in harbor_tasks at', harbor, file=sys.stderr)

	backup = dataset + '.bak'
	tmp = dataset + '.tmp'

	kept = 0
	removed = 0
	malformed = 0

	with open(dataset, 'r', errors='replace') as inf, open(tmp, 'w') as out:
		for line in inf:
			if not line.strip():
				continue
			try:
				obj = json.loads(line)
			except Exception:
				# preserve malformed lines to avoid data loss
				out.write(line)
				malformed += 1
				kept += 1
				continue

			iid = obj.get('instance_id') or obj.get('instanceId') or obj.get('instance')
			if iid in dirs:
				out.write(line)
				kept += 1
			else:
				removed += 1

	shutil.copy2(dataset, backup)
	shutil.move(tmp, dataset)

	print(f'filtered dataset: kept={kept}, removed={removed}, malformed_preserved={malformed}')
	print('original backed up to', backup)

if __name__ == '__main__':
	main()
