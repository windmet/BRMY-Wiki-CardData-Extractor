# GROOVE drop source contract

The GROOVE exporter extends the existing team source, not a second domain.

## Source collections

- BoostItems: `mst_groove_constant.GrooveBoostItemId* -> mst_item.ItemId`.
- StaminaRecoveryItems: `mst_item_groove_stamina_recover.ItemId -> mst_item.ItemId`.
- WishListItems: `mst_groove_wish_list_item.ItemId -> mst_item.ItemId`; retains raw LotteryRate and availability dates.
- WishListRateLevels: threshold IDs, BorderLotteryRate, Text, without assigning levels to items.
- ChanceBoxColorRates: ChanceBoxItemRarity, ChanceBoxColor, LotteryRate, without mapping item rarity.
- PlayQualityRewardRates: ID and Rainbow/Gold/Silver/Copper, without binding drinks to profiles.
- DropConstants: denominators, caps, recovery crystal cost and MaxScore as separate raw facts.
- UnresolvedAssociations: explicit business gaps, independent from broken-data Issues.

Required tables are checked before extraction. Missing item references and duplicate drop identities produce Issues; raw rows and joined raw item/constant records remain in the source JSON for auditing. Consumers must not publish broken joins as valid data.

No exact drop probabilities, expected values, drink multipliers, wishlist stacking/cap order or box-color names are inferred. Similar numbers or names do not establish foreign keys. External quality/rarity field references trigger `needs_review`; they never enable a formula automatically. The threshold application rule remains unresolved.

The existing Tracks, BonusRunners, BonusMatrix, RunnerPositions, BonusLevels, Relations, Stages, Characters and Constants remain semantically unchanged. On the local 266-table 2026-09-21 snapshot, old/new collections compare equal; new counts are drinks 4, recovery items 2, wishlist 142, levels 6, colors 7, profiles 2, constants 1, unresolved associations 3, Issues 0. These counts are observations, not fixed schema requirements.

The Calculator owns a separate allowlisted projection and its version. Do not replace its newer normalizer with the old sample TypeScript from the supplied patch bundle.

Validation: `python -m unittest tests.test_groove tests.test_groove_drop -q`, then `./scripts/verify.ps1`. Live extraction uses `python -m toolkit generate groove --masterdata <existing snapshot> --output <output root>`; no remote access is needed to reproduce a snapshot comparison.
