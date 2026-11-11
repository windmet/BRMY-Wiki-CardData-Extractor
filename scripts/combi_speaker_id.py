#!/usr/bin/env python3
"""Guess who speaks each clip of multi-speaker card cues (e.g. 3rd-birthday department combi).

Method: MFCC frames from every character's own single-speaker card cues train one
full-covariance Gaussian per character; a clip goes to the department candidate with the
highest mean frame log-likelihood. See docs/COMBI_SPEAKER_ID.md.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from scipy.fft import dct
from scipy.signal import get_window

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from toolkit.core.cri_utf import extract_acb_cue_clips, read_memory_awb  # noqa: E402
from toolkit.core.session import MasterDataSession  # noqa: E402

SR = 16000
FRAME, HOP, N_FFT, N_MELS, N_MFCC = 400, 160, 512, 40, 19
WINDOW = get_window('hamming', FRAME)
CR_RARITY = 102  # two-character cards; their cues mix speakers


def mel_filters():
    mel = lambda f: 2595 * np.log10(1 + f / 700)
    inv = lambda m: 700 * (10 ** (m / 2595) - 1)
    bins = np.floor((N_FFT + 1) * inv(np.linspace(mel(60), mel(7600), N_MELS + 2)) / SR).astype(int)
    bank = np.zeros((N_MELS, N_FFT // 2 + 1))
    for i in range(1, N_MELS + 1):
        left, centre, right = bins[i - 1], bins[i], bins[i + 1]
        bank[i - 1, left:centre] = (np.arange(left, centre) - left) / max(centre - left, 1)
        bank[i - 1, centre:right] = (right - np.arange(centre, right)) / max(right - centre, 1)
    return bank


MEL = mel_filters()


def decode_hca(hca):
    """HCA bytes -> mono float32 at 16 kHz via ffmpeg's built-in HCA decoder."""
    run = subprocess.run(['ffmpeg', '-v', 'error', '-f', 'hca', '-i', 'pipe:0', '-ac', '1',
                          '-ar', str(SR), '-f', 's16le', 'pipe:1'], input=hca, capture_output=True)
    if run.returncode:
        raise RuntimeError(run.stderr.decode(errors='replace'))
    return np.frombuffer(run.stdout, dtype=np.int16).astype(np.float32) / 32768


def mfcc(signal):
    """19 MFCCs per 25 ms frame (10 ms hop), quiet frames dropped, per-clip mean removed."""
    signal = np.append(signal[:1], signal[1:] - 0.97 * signal[:-1])
    if len(signal) < FRAME:
        return np.zeros((0, N_MFCC))
    frames = np.lib.stride_tricks.sliding_window_view(signal, FRAME)[::HOP] * WINDOW
    power = np.abs(np.fft.rfft(frames, N_FFT)) ** 2 / N_FFT
    coeffs = dct(np.log(power @ MEL.T + 1e-10), type=2, axis=1, norm='ortho')[:, 1:N_MFCC + 1]
    energy = power.sum(axis=1)
    coeffs = coeffs[energy > np.percentile(energy, 35)]
    return coeffs - coeffs.mean(axis=0) if len(coeffs) else coeffs


class Gaussian:
    def __init__(self, frames):
        self.mean = frames.mean(axis=0)
        cov = np.cov(frames, rowvar=False) + np.eye(frames.shape[1]) * 1e-3
        self.inv = np.linalg.inv(cov)
        self.logdet = np.linalg.slogdet(cov)[1]

    def score(self, frames):
        diff = frames - self.mean
        return float(-0.5 * (np.einsum('ij,jk,ik->i', diff, self.inv, diff).mean() + self.logdet))


class Voices:
    """Decoded card cues, cached per card as .npz so reruns skip ffmpeg."""

    def __init__(self, acb_root, cache):
        self.paths = {p.name: p for p in Path(acb_root).rglob('voice_*.acb')}
        self.cache = Path(cache)
        self.cache.mkdir(parents=True, exist_ok=True)

    def cues(self, card_id):
        cached = self.cache / f'{card_id}.npz'
        if cached.exists():
            return np.load(cached, allow_pickle=True)['clips'].item()
        path = self.paths.get(f'voice_{card_id}.acb')
        if not path:
            return {}
        raw = path.read_bytes()
        awb = read_memory_awb(raw)
        clips = {}
        for cue in extract_acb_cue_clips(raw):
            waves = [decode_hca(awb[c['MemoryAwbId']]) for c in cue['Clips'] if c['MemoryAwbId'] in awb]
            if waves:
                clips[cue['CueName']] = waves
        np.savez(cached, clips=np.array(clips, dtype=object))
        return clips


def build_references(tables, voices):
    """character -> [(card_id, frames)] from single-clip, non-combi cues of the character's own cards."""
    names = {r['CharacterId'] for r in tables.rows('mst_character') if 1 <= r['CharacterId'] <= 21}
    reference = defaultdict(list)
    for card in sorted(tables.rows('mst_character_card'), key=lambda r: r['CharacterCardId']):
        if card['CharacterId'] not in names or card.get('CardRarityCode') == CR_RARITY:
            continue
        for cue, waves in voices.cues(card['CharacterCardId']).items():
            if 'combi' in cue or len(waves) != 1:
                continue
            frames = mfcc(waves[0])
            if len(frames) > 30:
                reference[card['CharacterId']].append((card['CharacterCardId'], frames))
    return reference


def model(reference, cid, exclude_card=None):
    return Gaussian(np.vstack([f for card, f in reference[cid] if card != exclude_card]))


def departments(tables):
    groups = defaultdict(list)
    for row in tables.rows('mst_character'):
        if 1 <= row['CharacterId'] <= 21 and row.get('CharacterGroupCode') != 99:
            groups[row['CharacterGroupCode']].append(row['CharacterId'])
    return groups


def validate(reference, groups):
    """Leave-one-card-out: hide a card's clips, rebuild models, classify among department members."""
    confusion = Counter()
    for members in groups.values():
        held = defaultdict(list)
        for cid in members:
            for card, frames in reference[cid]:
                held[card].append((cid, frames))
        for card, items in held.items():
            models = {cid: model(reference, cid, exclude_card=card) for cid in members}
            for truth, frames in items:
                confusion[(truth, max(members, key=lambda c: models[c].score(frames)))] += 1
    per_character = {}
    for (truth, guess), count in confusion.items():
        stats = per_character.setdefault(truth, {'total': 0, 'correct': 0, 'confused_with': Counter()})
        stats['total'] += count
        if truth == guess:
            stats['correct'] += count
        else:
            stats['confused_with'][guess] += count
    return per_character


def identify(entries, reference, voices):
    models = {cid: model(reference, cid) for cid in reference}
    results = []
    for entry in entries:
        waves = voices.cues(entry['CharacterCardId']).get(entry['CueName'], [])
        order = sorted(range(len(entry['Clips'])), key=lambda i: entry['Clips'][i]['StartSeconds'])
        clips = []
        for position in order:
            frames = mfcc(waves[position]) if position < len(waves) else np.zeros((0, N_MFCC))
            scores = {c: models[c].score(frames) for c in entry['CandidateSpeakerIds']} if len(frames) else {}
            ranked = sorted(scores, key=scores.get, reverse=True)
            clips.append({'Clip': position + 1, 'StartSeconds': entry['Clips'][position]['StartSeconds'],
                          'Speaker': ranked[0] if ranked else None,
                          'Margin': round(scores[ranked[0]] - scores[ranked[1]], 2) if len(ranked) > 1 else None,
                          'Scores': {str(c): round(s, 2) for c, s in scores.items()}})
        speakers = [c['Speaker'] for c in clips]
        results.append({'CharacterCardId': entry['CharacterCardId'], 'CharacterCardName': entry['CharacterCardName'],
                        'CharacterId': entry['CharacterId'], 'CombiCharacterId': entry['CombiCharacterId'],
                        'CandidateSpeakerIds': entry['CandidateSpeakerIds'], 'Clips': clips,
                        'Order': speakers, 'IsPermutation': len(set(speakers)) == len(speakers)})
    return results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--masterdata', required=True, help='decoded master_data.json')
    parser.add_argument('--acb-root', required=True, help='directory searched recursively for voice_<card>.acb')
    parser.add_argument('--combi', required=True, help='audit_output/card_combi_voices.json')
    parser.add_argument('--output', required=True, help='directory for the decoded-audio cache and results')
    parser.add_argument('--kind', default='department_combi', help='card_combi_voices Kind to analyse')
    parser.add_argument('--skip-validation', action='store_true')
    args = parser.parse_args(argv)

    output = Path(args.output)
    tables = MasterDataSession.open(args.masterdata).tables
    voices = Voices(args.acb_root, output / 'decoded')
    reference = build_references(tables, voices)
    report = {'ReferenceClips': {str(c): len(v) for c, v in sorted(reference.items())}}
    if not args.skip_validation:
        stats = validate(reference, departments(tables))
        correct = sum(s['correct'] for s in stats.values())
        total = sum(s['total'] for s in stats.values())
        report['Validation'] = {'Accuracy': round(correct / total, 4), 'Correct': correct, 'Total': total,
                                'PerCharacter': {str(c): {'Accuracy': round(s['correct'] / s['total'], 3),
                                                          'ConfusedWith': {str(k): v for k, v in s['confused_with'].items()}}
                                                 for c, s in sorted(stats.items())}}
        print(f"validation: {correct}/{total} = {correct / total:.3f}")
        for cid, s in sorted(stats.items()):
            if s['correct'] / s['total'] < 0.9:
                print(f"  weak: character {cid} accuracy {s['correct'] / s['total']:.2f}, confused with {dict(s['confused_with'])}")
    entries = [e for e in json.loads(Path(args.combi).read_text(encoding='utf-8'))['Entries'] if e['Kind'] == args.kind]
    report['Results'] = identify(entries, reference, voices)
    (output / 'combi_speakers.json').write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding='utf-8')
    for r in report['Results']:
        print(r['CharacterCardId'], r['CharacterCardName'], 'combi', r['CombiCharacterId'], '->', r['Order'],
              'margins', [c['Margin'] for c in r['Clips']])


if __name__ == '__main__':
    main()
