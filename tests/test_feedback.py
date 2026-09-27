import copy
import unittest

from toolkit.core.feedback import feedback_groups, artifact_needs_review


class FeedbackTests(unittest.TestCase):
    def test_only_explicit_informational_kinds_are_downgraded(self):
        receipt = {'errors': ['failed download'], 'warnings': [
            {'domain': 'resources', 'kind': 'offline_snapshot', 'warning': 'offline'},
            {'domain': 'resources', 'kind': 'unused_manifest_categories', 'warning': 'unknown'},
            {'kind': 'baseline_initialized'},
            {'kind': 'new_unknown_kind'},
            '当前使用离线缓存，未检查线上更新',
            {'domain': 'home_voices', 'warning': '13 incomplete subjects'},
        ]}
        original = copy.deepcopy(receipt)
        groups = feedback_groups(receipt)
        self.assertEqual(3, len(groups['information']))
        self.assertEqual(3, len(groups['review']))
        self.assertEqual(['failed download'], groups['errors'])
        self.assertEqual(original, receipt)

    def test_content_warnings_apply_to_their_domain_and_unscoped_warnings_to_all(self):
        groups = feedback_groups({'warnings': [{'domain': 'ojt', 'warning': 'missing coordinates'}]})
        self.assertTrue(artifact_needs_review({'domain': 'ojt'}, groups))
        self.assertFalse(artifact_needs_review({'domain': 'birthday_archive'}, groups))
        groups['review'].append('legacy warning')
        self.assertTrue(artifact_needs_review({'domain': 'birthday_archive'}, groups))
