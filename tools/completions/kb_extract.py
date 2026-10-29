"""Pull KB elevations from the Form 3 OCR text (field 17 'ELEVATIONS (DF, RKB, RT, GL)'): the form lists a GL and a KB number near that label.
A (GL, KB) pair is accepted only when GL is within 3 ft of the state's ground elevation (data/headers.json) and KB is 8 to 60 ft above it."""
import glob,re,json,collections,sys,os
def numbers(s):
    m=re.search(r'(?i)elevations?\s*\(|\(\s*DF\s*,\s*R?KB',s)
    if not m: return []
    seg=s[m.end():m.end()+360]
    seg=re.sub(r'\d{1,2}/\d{1,2}/\d{2,4}',' ',seg)
    seg=re.sub(r'(?<=\d),(?=\d{3}\b)','',seg)               # 5,088 -> 5088
    out=[]
    for t in re.finditer(r'(?<![\d.])(\d{4}(?:\.\d{1,2})?)(?![\d/])',seg):
        v=float(t.group(1))
        if 3500<=v<=8000: out.append(v)
    return out
def pair(vals,state):
    best=[]
    for a in vals:
        for b in vals:
            if 8<=b-a<=60 and (state is None or abs(a-state)<=3): best.append((a,b))
    if best: return best[0]
    if state is not None:                                   # some forms list only the KB: one number 8 to 60 ft above the state ground elevation
        k=[b for b in vals if 8<=b-state<=60]
        if len(set(k))==1: return (state,k[0])
    return None
if __name__=='__main__':
    R=sys.argv[1]; H=json.load(open(sys.argv[3])); st={}
    for v in H.values():
        try: st[v['API Number']]=float(v['Elevation'])
        except: pass
    res={}; nostate=0
    for d in sorted(glob.glob(R+'/wells/49-*')):
        api=os.path.basename(d); votes=collections.Counter()
        for f in glob.glob(d+'/f3_*.json'):
            p=pair(numbers(open(f,errors='ignore').read()),st.get(api))
            if p: votes[p]+=1
        if votes:
            gl,kb=votes.most_common(1)[0][0]; res[api]=kb
    json.dump(res,open(sys.argv[2],'w'),sort_keys=True,indent=0)
    print(len(res),'wells with a KB')
