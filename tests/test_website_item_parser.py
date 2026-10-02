"""Native exchange slot regression, independent of the generated snapshot."""
import sys
import unittest
from pathlib import Path
from toolkit.website.item_catalog import extract

class Tables:
    def rows(self, table):
        return {
            'mst_item':[{'ItemId':1},{'ItemId':2},{'ItemId':3}],
            'mst_exchange':[{'ExchangeId':7,'CostItemId1':1,'CostItemId2':2}],
            'mst_exchange_product':[{'ExchangeId':7,'ExchangeProductNo':1,'CostItemIdNumber':2,'CostItemCount':10,'DirectRewardGroupId':8}],
            'mst_direct_reward':[{'DirectRewardGroupId':8,'RewardTypeCode':2,'RewardTargetId':3,'RewardCount':1}],
        }.get(table,[])
    def by_id(self,table,key): return {r[key]:r for r in self.rows(table)}
    def group_by(self,table,key):
        out={}
        for r in self.rows(table): out.setdefault(r[key],[]).append(r)
        return out

class ExchangeSlotTest(unittest.TestCase):
    def test_only_selected_cost_slot_is_used(self):
        result=extract(Tables())
        self.assertNotIn('1',result['Uses'])
        self.assertEqual(result['Uses']['2'][0]['CostItemIdNumber'],2)
        self.assertEqual(result['Acquisitions']['3'][0]['CostItemId'],2)

if __name__=='__main__': unittest.main()
