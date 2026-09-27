"""Conservative presentation of existing receipt issues, without rewriting them."""
import json


def feedback_groups(result):
    groups = {'errors': list(result.get('errors', [])), 'review': [], 'information': []}
    for warning in result.get('warnings', []):
        informational = isinstance(warning, dict) and (
            warning.get('kind') == 'baseline_initialized' or
            (warning.get('domain') == 'resources' and
             warning.get('kind') in {'offline_snapshot', 'unused_manifest_categories'}))
        groups['information' if informational else 'review'].append(warning)
    return groups


def issue_text(issue):
    if not isinstance(issue, dict):
        return str(issue)
    if issue.get('kind') == 'baseline_initialized':
        return '首次使用此输出目录，已建立数据结构基线。后续更新会与此基线比较。'
    return str(issue.get('warning') or issue.get('error') or json.dumps(issue, ensure_ascii=False))


def artifact_needs_review(artifact, groups):
    # Unscoped legacy warnings apply to the run; never silently downgrade them.
    return any(not isinstance(issue, dict) or not issue.get('domain') or
               issue['domain'] in {'resources', artifact.get('domain')}
               for issue in groups['review'])
