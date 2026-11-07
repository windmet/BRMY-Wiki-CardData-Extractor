# Canonical Music and optional Jukebox enrichment

`generate music jukebox --masterdata <file> --output <directory>` and
`sync music jukebox --cache <cache> --output <directory>` produce independent
`Music_Source.json` and `Jukebox_Source.json` in `audit_output`. The Music legacy
database/XLSX and duplicate/orphan resource audit remain available. Canonical
identities never merge on title; usage references retain table, field and row IDs.
These sync plans download only masterdata. Media failures cannot block the source.

Optional media command (install UnityPy and Pillow for jackets):

```text
python -m toolkit.media_enrichment --source <Jukebox_Source.json> --cache <cache> --vgmstream <vgmstream-cli> --output <receipt.json> --jacket-output <image-directory>
```

`--offline` forbids network access. The receipt can be reused at the same output
path: the provider verifies raw bytes and catalog fingerprints; measurements are
reused only for identical resource identity/content, resolver and engine binary.
Changed resources are downloaded and measured again. Failure replaces old measured
duration with `stale` and null seconds, or leaves new records `pending`.

All 191 entries in the locally verified snapshot have exact
`Jukebox/<AudioFileName>.mp3` catalog members. The command probes those original
files with official vgmstream `-m -I -i`; seconds are samples/sampleRate. It records
resource key, size, fingerprint, SHA256, catalog SHA256, engine binary SHA256,
engine version and stream metadata. It never downloads a guessed URL, strips
`_N`, substitutes a profile preview, or selects the longest ACB subsong.

This distinction is observable: HH_03_N's Jukebox file is 122.208 seconds;
the HH_03 AWB stream is approximately 120.652 seconds; ACB preload fragments are
under 0.1 second. Missing exact Jukebox resources therefore remain pending.
ACB/AWB full-stream resolution is deliberately not fabricated as a fallback.

Jackets use catalogued native keys and exact Texture2D names; output is transparent
lossless WebP, capped at 256 pixels. Audio stays only in the provider cache. A
receipt is candidate evidence, not publication authority or real-device playback
acceptance. The Calculator validates the matching source snapshot and file keys
before consuming duration/jacket evidence.
