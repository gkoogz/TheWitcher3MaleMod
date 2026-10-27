"""Check actual sealed campaign lifecycle evidence, separate from visual review."""
import math


def text(vector):
    length=int(vector[0]);letters=[]
    for value in vector[1:]:
        word=int(value)
        for _ in range(3):letters.append(chr(word%128));word//=128
    return ''.join(letters)[:min(length,9)]


def analyze(rows,checkpoints):
    records={}
    for row in rows:
        v=row.get('vectors',[])
        if row.get('iterationReadback')and len(v)==8 and[v[i][3]for i in range(3)]==[-291,-292,-293]:
            records[int(v[4][0])]=dict(seconds=row['seconds'],paused=row['paused'],position=v[3][:3],
                saveLocked=bool(v[4][1]),ownPause=bool(v[4][2]),armor=text(v[5]),armorLength=int(v[5][0]),
                pants=text(v[6]),pantsLength=int(v[6][0]),restored=bool(v[7][2]),sdkTick=int(v[7][3]))
    events=[row for row in rows if row.get('iterationReadback')and len(row.get('vectors',[]))==8
        and[row['vectors'][i][3]for i in range(3)]==[-231,-232,-233]]
    restored=any(row['vectors'][4][0]==16 for row in events)
    required={301,302,303,304,305,306,307,309,310,311,312,313};missing=sorted(required-records.keys())
    start,end=records.get(301),records.get(302)
    distance=math.dist(start['position'][:2],end['position'][:2])if start and end else 0
    dressed,undressed=records.get(304,{}),records.get(305,{})
    clothes=(dressed.get('armor','').casefold().startswith('starting ')and dressed.get('pants','').casefold().startswith('pants 02')
        and undressed.get('armorLength')==0 and not undressed.get('pants','').casefold().startswith('pants 02'))
    before,paused,after=records.get(305,{}),records.get(306,{}),records.get(312,{})
    pause_ticks=paused.get('sdkTick',0)-before.get('sdkTick',0)
    paused_state=paused.get('paused')and paused.get('ownPause')and not after.get('paused',True)and not after.get('ownPause',True)and pause_ticks>=30
    cps={row['stage']:row for row in checkpoints}
    frozen=305 in cps and 306 in cps and cps[305]['sequence']==cps[306]['sequence']
    resumed=307 in cps and 309 in cps and cps[309]['sequence']>cps[307]['sequence']
    after_load=records.get(309,{})
    result=dict(observedCampaignStages=sorted(records),missingCampaignStages=missing,walkDistanceMeters=distance,walkObserved=distance>=1,
        clothingChangeObserved=bool(clothes),pauseObserved=bool(paused_state),pauseSDKTicks=pause_ticks,pausedPhysicsSequenceFrozen=frozen,
        saveUnlockedObserved=310 in records and not records[310]['saveLocked'],saveCompletedObserved=313 in records,loadRequestedObserved=311 in records,
        restoredGameStartedObserved=restored,afterLoadObserved=bool(after_load.get('restored'))and resumed,campaignLifecycle=records)
    result['campaignActionsObserved']=not missing and all(result[key]for key in ('walkObserved','clothingChangeObserved','pauseObserved',
        'pausedPhysicsSequenceFrozen','saveUnlockedObserved','saveCompletedObserved','loadRequestedObserved','restoredGameStartedObserved','afterLoadObserved'))
    return result
