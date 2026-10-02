"""Extract period metadata only. Stage projections come from canonical Puzzle."""
from .common import window

def extract(md):
    periods = []
    for row in md.rows('mst_marvelous_challenge'):
        periods.append({**{k:row[k] for k in ('MarvelousChallengeId','MarvelousChallengeType','Lap','MarvelousChallengeMusicCueIds','LogoFileName')},'Availability':window(row.get('StartTime'),row.get('EndTime'))})
    return {'Meta':{'Domain':'marvelous_periods'},'Periods':sorted(periods,key=lambda p:p['MarvelousChallengeId']),'Audit':{'PeriodCount':len(periods)}}
