#!/usr/bin/env python3
import os
import re

def check_file_for_issues(filepath):
    issues = []
    with open(filepath, 'r') as f:
        content = f.read()
        if 'state.get(' in content and 'isinstance(state, dict)' not in content and 'graph_runner' not in filepath and 'main' not in filepath and 'session' not in filepath and 'graph.py' not in filepath:
            issues.append(f"Uses state.get() without dict check")
        if re.search(r'state\["[^"]+"\]', content) and 'graph_runner' not in filepath and 'main' not in filepath and 'session' not in filepath and 'graph.py' not in filepath:
            issues.append(f"Uses state['field'] instead of state.context.field")
        if 'def ' in content and 'agent' in filepath.lower():
            if 'sync_to_legacy()' not in content:
                issues.append(f"Agent missing sync_to_legacy() call")
    return issues

for root, dirs, files in os.walk('./agents-api'):
    for file in files:
        if file.endswith('.py') and not file.startswith('fix_'):
            filepath = os.path.join(root, file)
            issues = check_file_for_issues(filepath)
            if issues:
                print(f"\n{filepath}:")
                for issue in issues:
                    print(f"  ⚠️  {issue}")

print("\n✅ Scan complete!")
