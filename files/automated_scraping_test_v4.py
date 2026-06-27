"""
SEMSAI AUTOMATED SCRAPING TEST SUITE — v4
==========================================
v4 changes:
  FIX 6 — ppm sanity cap (>180k forces LOW_CONFIDENCE)
  FIX 7 — dynamic ppm ceiling (250k for ≥400sqm)
  FIX 8 — compound-inclusive fallback query
"""

import re, json, time, statistics, requests
import pandas as pd
from collections import Counter
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse, unquote

SERPER_API_KEY = "4ba18d89caf51b60770686037f7caff27e6bf1fd"

PPM_CEILING_STANDARD = 220_000
PPM_CEILING_LARGE    = 250_000
PPM_SANITY_FLAG      = 180_000
AREA_LARGE_THRESHOLD = 400

TEST_CASES = [
    {"id":"A1","label":"Apartment resale — Palm Hills (6th Oct)","area":150,"bedrooms":3,"bathrooms":2,"property_type":"Apartment","sale_type":"Resale","compound":"Palm Hills","location":"6th of October","developer":"Palm Hills Developments"},
    {"id":"A2","label":"Apartment resale — Zed East (New Cairo)","area":120,"bedrooms":2,"bathrooms":2,"property_type":"Apartment","sale_type":"Resale","compound":"Zed East","location":"New Cairo","developer":"ORA"},
    {"id":"A3","label":"Apartment resale — Madinaty (New Cairo)","area":130,"bedrooms":3,"bathrooms":2,"property_type":"Apartment","sale_type":"Resale","compound":"Madinaty","location":"New Cairo","developer":"Talaat Moustafa Group"},
    {"id":"A4","label":"Apartment resale — Hyde Park (luxury)","area":180,"bedrooms":3,"bathrooms":3,"property_type":"Apartment","sale_type":"Resale","compound":"Hyde Park","location":"New Cairo","developer":"Hyde Park Developments"},
    {"id":"A5","label":"Apartment resale — Mivida (luxury)","area":160,"bedrooms":3,"bathrooms":2,"property_type":"Apartment","sale_type":"Resale","compound":"Mivida","location":"New Cairo","developer":"Emaar Misr"},
    {"id":"A6","label":"Apartment dev sale — Sodic East","area":140,"bedrooms":2,"bathrooms":2,"property_type":"Apartment","sale_type":"Developer Sale","compound":"Sodic East","location":"New Cairo","developer":"Sodic"},
    {"id":"A7","label":"Apartment dev sale — IL Monte Galala","area":110,"bedrooms":2,"bathrooms":1,"property_type":"Apartment","sale_type":"Developer Sale","compound":"IL Monte Galala","location":"Ain Sokhna","developer":"Tatweer Misr"},
    {"id":"A8","label":"Apartment dev sale — Badya (budget)","area":80,"bedrooms":1,"bathrooms":1,"property_type":"Apartment","sale_type":"Developer Sale","compound":"Badya","location":"6th of October","developer":"Palm Hills Developments"},
    {"id":"V1","label":"Villa resale — Villette (New Cairo)","area":300,"bedrooms":4,"bathrooms":3,"property_type":"Villa","sale_type":"Resale","compound":"Villette","location":"New Cairo","developer":"Sodic"},
    {"id":"V2","label":"Villa resale — Palm Hills (6th Oct)","area":400,"bedrooms":5,"bathrooms":4,"property_type":"Villa","sale_type":"Resale","compound":"Palm Hills","location":"6th of October","developer":"Palm Hills Developments"},
    {"id":"V3","label":"Villa dev sale — Hyde Park (luxury)","area":350,"bedrooms":4,"bathrooms":4,"property_type":"Villa","sale_type":"Developer Sale","compound":"Hyde Park","location":"New Cairo","developer":"Hyde Park Developments"},
    {"id":"V4","label":"Villa dev sale — Sodic West","area":280,"bedrooms":4,"bathrooms":3,"property_type":"Villa","sale_type":"Developer Sale","compound":"Sodic West","location":"6th of October","developer":"Sodic"},
    {"id":"C1","label":"Chalet resale — Marassi (North Coast)","area":100,"bedrooms":2,"bathrooms":2,"property_type":"Chalet","sale_type":"Resale","compound":"Marassi","location":"North Coast","developer":"Emaar Misr"},
    {"id":"C2","label":"Chalet resale — IL Monte Galala (Sokhna)","area":90,"bedrooms":2,"bathrooms":1,"property_type":"Chalet","sale_type":"Resale","compound":"IL Monte Galala","location":"Ain Sokhna","developer":"Tatweer Misr"},
    {"id":"C3","label":"Chalet dev sale — Hacienda Bay","area":120,"bedrooms":3,"bathrooms":2,"property_type":"Chalet","sale_type":"Developer Sale","compound":"Hacienda Bay","location":"North Coast","developer":"Palm Hills Developments"},
    {"id":"C4","label":"Chalet dev sale — Fouka Bay (luxury)","area":150,"bedrooms":3,"bathrooms":2,"property_type":"Chalet","sale_type":"Developer Sale","compound":"Fouka Bay","location":"North Coast","developer":"Tatweer Misr"},
    {"id":"E1","label":"EDGE: Arabic-name compound (Sodic East)","area":135,"bedrooms":2,"bathrooms":2,"property_type":"Apartment","sale_type":"Resale","compound":"Sodic East","location":"New Cairo","developer":"Sodic"},
    {"id":"E2","label":"EDGE: Ultra-luxury villa (500+ sqm)","area":550,"bedrooms":6,"bathrooms":5,"property_type":"Villa","sale_type":"Resale","compound":"Katameya Heights","location":"New Cairo","developer":"Katameya Heights"},
    {"id":"E3","label":"EDGE: Budget small apartment (75sqm)","area":75,"bedrooms":1,"bathrooms":1,"property_type":"Apartment","sale_type":"Developer Sale","compound":"Badya","location":"6th of October","developer":"Palm Hills Developments"},
    {"id":"E4","label":"EDGE: Niche compound (Al Burouj)","area":160,"bedrooms":3,"bathrooms":2,"property_type":"Apartment","sale_type":"Resale","compound":"Al Burouj","location":"New Cairo","developer":"City Edge"},
]

PRICE_KEYS = {"price","totalprice","unitprice","startingprice","minprice","maxprice","listprice","saleprice","offerprice","askingprice","priceegp","priceinegp","amount","value","min_price","max_price","starting_price","total_price","unit_price","sellingprice","selling_price"}
DANGER_KEYWORDS = ["مقدم","قسط","installment","downpayment","monthly","per month"]
SLUG_TYPE_CONFLICTS = {
    "apartment":["penthouse","townhouse","twinhouse","twin-house","serviced-apartment","studio-for-sale"],
    "villa":    ["apartment-for-sale","penthouse-for-sale","studio-for-sale","duplex-for-sale"],
    "chalet":   ["apartment-for-sale","studio-for-sale"],
}
NAWY_UNIT_PRICE_PATHS = [
    ["props","pageProps","propertyDetails","price"],["props","pageProps","propertyDetails","totalPrice"],
    ["props","pageProps","propertyDetails","unitPrice"],["props","pageProps","unit","price"],
    ["props","pageProps","unit","totalPrice"],["props","pageProps","property","price"],
    ["props","pageProps","property","totalPrice"],["props","pageProps","listing","price"],
    ["props","pageProps","listing","totalPrice"],["props","pageProps","data","price"],
    ["props","pageProps","data","totalPrice"],["props","pageProps","data","unit","price"],
]
_SLUG_NOISE = {"the","el","al","il","new","park","view","east","west","north","south","city","gardens"}

def get_price_bounds(area):
    """FIX 7: dynamic ceiling."""
    ceiling = PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD
    return area * 18_000, area * ceiling

def nawy_url_type(url):
    path = unquote(urlparse(url).path.lower())
    if any(p in path for p in ["/blog/","/news/","/articles/","/insights/","/guide/"]): return "blog"
    if "/search/" in path: return "search"
    if "/compound/undefined/" in path: return "rejected"
    if "/compound/" in path and "/property/" in path: return "property"
    return "rejected"

def extract_compound_id(url):
    path = unquote(urlparse(url).path.lower())
    if "/compound/" in path:
        seg = path.split("/compound/",1)[1].split("/")[0]
        parts = seg.split("-",1)
        if parts[0].isdigit(): return int(parts[0])
    return None

def resolve_compound_ids(compound_name, search_fn):
    query = f'site:nawy.com/compound "{compound_name}" property'
    data  = search_fn(query, max_results=5)
    tokens = set(re.split(r'[\s\-_]+', compound_name.lower())) - _SLUG_NOISE
    if not tokens: tokens = set(re.split(r'[\s\-_]+', compound_name.lower()))
    ids = set()
    for item in data.get("organic",[]):
        url = item.get("link",""); cid = extract_compound_id(url)
        if cid is None: continue
        path = unquote(urlparse(url).path.lower())
        if "/compound/" in path:
            slug = path.split("/compound/",1)[1].split("/")[0]
            if any(t in slug for t in tokens): ids.add(cid)
    print(f"      [IDs] '{compound_name}' → {sorted(ids) if ids else 'none'}")
    return ids

def url_has_type_conflict(url, target_type):
    path = unquote(urlparse(url).path.lower())
    for slug in SLUG_TYPE_CONFLICTS.get(target_type.lower(),[]):
        if slug in path: return True, slug
    return False, ""

def compound_variants(name):
    n = name.lower().strip()
    variants = {n, n.replace(" ",""), n.replace(" ","-"), n.replace(" ","_")}
    arabic_map = {"il ":"ايل ","al ":"ال","el ":"ال","new ":"نيو ","capital":"كابيتال","mondo":"موندو","palm":"بالم","lake":"ليك","garden":"جاردن","park":"بارك","view":"فيو"}
    ar = n
    for en, av in arabic_map.items(): ar = ar.replace(en, av)
    if ar != n: variants.add(ar)
    return list(variants)

def validate_nawy_listing(clean_text, url, target_features, debug=False):
    def reject(r):
        if debug: print(f"        [REJECT] {r}")
        return False
    if nawy_url_type(url) != "property": return reject(f"url={nawy_url_type(url)}")
    path = unquote(urlparse(url).path.lower())
    target_type = target_features.get("property_type","apartment")
    conflict, slug = url_has_type_conflict(url, target_type)
    if conflict: return reject(f"slug '{slug}'")
    allowed_ids = target_features.get("compound_ids", set())
    if allowed_ids:
        uid = extract_compound_id(url)
        if uid is not None and uid not in allowed_ids: return reject(f"ID {uid} not in {sorted(allowed_ids)}")
    for s in ["Top Searches","Popular locations","Related Compounds","Explore similar"]:
        clean_text = clean_text.split(s)[0]
    text_lower = clean_text.lower()
    target_compound = target_features.get("compound","").lower().strip()
    if target_compound and not allowed_ids:
        cvariants = compound_variants(target_compound)
        compound_slug = ""
        if "/compound/" in path:
            after = path.split("/compound/",1)[1].split("/")[0]
            if after == "undefined": return reject("compound/undefined")
            parts = after.split("-",1)
            compound_slug = parts[1] if len(parts)>1 and parts[0].isdigit() else after
        slug_tokens = set(re.split(r'[-_\s]+', compound_slug))
        target_tokens = set(re.split(r'[-_\s]+', target_compound))
        if not target_tokens.issubset(slug_tokens) and not any(v.replace(" ","-") in text_lower.replace(" ","-") or v in text_lower for v in cvariants if len(v)>=6):
            return reject(f"compound not matched")
    TYPE_KW = {
        "apartment":{"positive":["apartment","flat","studio","duplex","penthouse","شقة","شقه"],"negative":["villa","فيلا","chalet","شاليه"]},
        "villa":    {"positive":["villa","standalone","twin house","townhouse","ivilla","فيلا"],"negative":["apartment","شقة"]},
        "chalet":   {"positive":["chalet","cabin","beach unit","sahel unit","شاليه","كابينة"],"negative":["apartment","شقة"]},
    }
    entry = TYPE_KW.get(target_type.lower(),{"positive":[target_type],"negative":[]})
    text_ns = re.sub(r'\s+','',text_lower)
    if not any((w in text_lower or w.replace(" ","") in text_ns) for w in entry["positive"]): return reject(f"no '{target_type}'")
    body = text_lower[1000:-1000] if len(text_lower)>3000 else text_lower
    for neg in entry["negative"]:
        cnt = body.count(neg); thr = 8 if neg in {"apartment","شقة"} else 2
        if cnt > thr: return reject(f"rival '{neg}' ×{cnt}")
    if debug: print(f"        [PASS]")
    return True

def _get_nested(obj, path):
    cur = obj
    for k in path:
        if not isinstance(cur,dict) or k not in cur: return None
        cur = cur[k]
    return cur

def _extract_prices_from_json(obj, pkeys, depth=0):
    hits = []
    if depth>20: return hits
    if isinstance(obj,dict):
        for k,v in obj.items():
            if k.lower() in pkeys and isinstance(v,(int,float)) and v>0: hits.append(int(v))
            else: hits.extend(_extract_prices_from_json(v,pkeys,depth+1))
    elif isinstance(obj,list):
        for item in obj: hits.extend(_extract_prices_from_json(item,pkeys,depth+1))
    return hits

def _extract_next_data_price(nd_json, floor, ceil):
    for path in NAWY_UNIT_PRICE_PATHS:
        val = _get_nested(nd_json, path)
        if isinstance(val,(int,float)) and floor<=val<=ceil:
            print(f"        [ND:targeted] {'.'.join(path[-2:])}={int(val):,.0f}"); return [int(val)]
    def find_unit(obj,d=0):
        res=[]
        if d>8: return res
        if isinstance(obj,dict):
            kl={k.lower() for k in obj}
            if any(p in kl for p in ["price","totalprice","unitprice"]) and any(a in kl for a in ["area","space","size","sqm"]):
                for k,v in obj.items():
                    if k.lower() in {"price","totalprice","unitprice"} and isinstance(v,(int,float)) and v>0: res.append(int(v))
            for v in obj.values(): res.extend(find_unit(v,d+1))
        elif isinstance(obj,list):
            for item in obj: res.extend(find_unit(item,d+1))
        return res
    up=[p for p in find_unit(nd_json) if floor<=p<=ceil]
    if up: print(f"        [ND:unit_obj] {up[:3]}"); return up
    all_k=_extract_prices_from_json(nd_json,PRICE_KEYS)
    ir=[p for p in all_k if floor<=p<=ceil]
    if ir: print(f"        [ND:full_scan] {ir[:5]}")
    return ir

def deduplicate_shared_prices(prices):
    if len(prices)<3: return prices
    counts=Counter(prices); n=len(prices)
    f=[p for p in prices if counts[p]/n<=0.50]
    if not f: return prices
    removed=list({p for p in prices if counts[p]/n>0.50})
    if removed: print(f"        [DEDUP] {[f'{p:,.0f}' for p in removed[:3]]}")
    return f

def extract_nawy_price(raw_html, clean_text, area, floor, ceil):
    found=[]
    nd=re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',raw_html,re.DOTALL)
    if nd:
        try: found+=_extract_next_data_price(json.loads(nd.group(1)),floor,ceil)
        except Exception as e: print(f"        [ND err] {e}")
    for sc in BeautifulSoup(raw_html,"html.parser").find_all("script",type="application/ld+json"):
        try:
            ld=json.loads(sc.string or "")
            found+=[p for p in _extract_prices_from_json(ld,PRICE_KEYS) if floor<=p<=ceil]
        except: pass
    for m in re.findall(r'(\d{1,3}(?:,\d{3}){2,})|(\d{7,10})',clean_text):
        try: found.append(int((m[0] or m[1]).replace(",","")))
        except: pass
    for m in re.findall(r'(?:egp|جنيه)\s*(\d[\d,]+)',clean_text.lower()):
        try: found.append(int(m.replace(",","")))
        except: pass
    for m in re.findall(r'(\d+\.?\d*)\s*(?:million|m)\s*(?:egp|le|pounds?)?',clean_text.lower()):
        try: found.append(int(float(m)*1_000_000))
        except: pass
    ir=sorted(set(p for p in found if floor<=p<=ceil),reverse=True)
    tnc=clean_text.replace(",",""); safe=[]
    for price in ir:
        pos=tnc.find(str(price)); ctx=tnc[max(0,pos-60):pos+60].lower()
        if not any(w in ctx for w in DANGER_KEYWORDS): safe.append(price)
        else: print(f"        [SKIP danger] {price:,.0f}")
    if not safe: return None
    safe=deduplicate_shared_prices(safe)
    best=sorted(safe)[len(safe)//2]
    ppm=best/area
    ceiling_ppm = PPM_CEILING_LARGE if area >= AREA_LARGE_THRESHOLD else PPM_CEILING_STANDARD
    if not (15_000<=ppm<=ceiling_ppm): print(f"        [SKIP ppm={ppm:,.0f}]"); return None
    return best

def remove_outliers(prices, area, fallback=False):
    """FIX 5+6: Z-score with ppm sanity cap."""
    if len(prices)<3: return prices, len(prices)<2
    thr=1.8 if fallback else 2.5
    s=pd.Series(prices); med=s.median(); mad=(s-med).abs().median()
    clean=s[((0.6745*(s-med))/mad).abs()<=thr].tolist() if mad>0 else prices
    if fallback and len(clean)>=4:
        q1=statistics.quantiles(clean,n=4)[0]; q3=statistics.quantiles(clean,n=4)[2]; iqr=q3-q1
        ic=[p for p in clean if (q1-1.5*iqr)<=p<=(q3+1.5*iqr)]
        if ic: clean=ic
    clean=clean if clean else prices
    lc = len(clean)<3 or len(set(prices))==1
    # FIX 6: ppm sanity cap
    if clean:
        avg_ppm = (sum(clean)/len(clean)) / area
        if avg_ppm > PPM_SANITY_FLAG:
            print(f"        [PPM SANITY] {avg_ppm:,.0f}/sqm > {PPM_SANITY_FLAG:,} → LOW_CONFIDENCE")
            lc = True
    return clean, lc

def _fetch_page(url):
    headers={"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36","Accept-Language":"en-US,en;q=0.9"}
    for attempt in range(2):
        try:
            r=requests.get(url,headers=headers,timeout=20)
            if r.status_code==200: return r.text
            if r.status_code==500 and attempt==0: time.sleep(5); continue
            return None
        except:
            if attempt==0: time.sleep(3); continue
            return None
    return None

def _run_search(query, max_results=10):
    for attempt in range(2):
        try:
            resp=requests.post("https://google.serper.dev/search",headers={"X-API-KEY":SERPER_API_KEY,"Content-Type":"application/json"},json={"q":query,"num":max_results,"gl":"eg","hl":"en"},timeout=20+attempt*15)
            resp.raise_for_status(); return resp.json()
        except requests.exceptions.Timeout:
            if attempt==0: time.sleep(3); continue
            return {}
        except Exception as e:
            print(f"      [SEARCH ERR] {e}"); return {}
    return {}

def run_single_test(f):
    result={"id":f["id"],"label":f["label"],"area":f["area"],"property_type":f["property_type"],"sale_type":f["sale_type"],"compound":f["compound"],"location":f["location"],"status":"fail","compound_match":False,"fallback_used":False,"low_confidence":False,"compound_ids_resolved":[],"listings_fetched":0,"listings_passed_validator":0,"raw_prices":[],"clean_prices":[],"web_avg":0,"web_ppm":0,"error":None}
    try:
        sale_hint="resale" if "resale" in f["sale_type"].lower() else "for sale"
        query=f'site:nawy.com/compound "{f["compound"]}" {f["property_type"]} {sale_hint}'
        print(f"\n{'='*60}\n  [{f['id']}] {f['label']}\n{'='*60}")

        compound_ids=resolve_compound_ids(f["compound"],_run_search)
        result["compound_ids_resolved"]=sorted(compound_ids)

        data=_run_search(query,max_results=12)
        fetched=[]; fallback_used=False

        for item in data.get("organic",[]):
            url=item.get("link","")
            if nawy_url_type(url)!="property": continue
            conflict,slug=url_has_type_conflict(url,f["property_type"])
            if conflict: continue
            html=_fetch_page(url)
            if html: fetched.append({"url":url,"html":html})

        if not fetched:
            # FIX 8: compound-inclusive fallback
            fq=f'site:nawy.com "{f["compound"]}" {f["property_type"]} {sale_hint}'
            print(f"  ⚠️  Fallback: {fq}")
            d2=_run_search(fq,max_results=12)
            for item in d2.get("organic",[]):
                url=item.get("link","")
                if nawy_url_type(url)!="property": continue
                conflict,slug=url_has_type_conflict(url,f["property_type"])
                if conflict: continue
                html=_fetch_page(url)
                if html: fetched.append({"url":url,"html":html})
            fallback_used=bool(fetched)

        result["fallback_used"]=fallback_used
        result["listings_fetched"]=len(fetched)
        result["compound_match"]=not fallback_used

        val_features={"compound":"" if fallback_used else f["compound"],"compound_ids":compound_ids if not fallback_used else set(),"property_type":f["property_type"]}

        # FIX 7: dynamic bounds
        floor,ceil=get_price_bounds(f["area"])
        raw_prices=[]; seen=set()

        for item in fetched[:8]:
            url=item["url"]
            if url in seen: continue
            seen.add(url)
            soup=BeautifulSoup(item["html"],"html.parser")
            clean_text=soup.get_text(separator=" ")
            print(f"    → {url[-65:]}")
            if not validate_nawy_listing(clean_text,url,val_features,debug=True): continue
            result["listings_passed_validator"]+=1
            price=extract_nawy_price(item["html"],clean_text,f["area"],floor,ceil)
            if price:
                raw_prices.append(price)
                print(f"        ✅ {price:,.0f} EGP ({price/f['area']:,.0f}/sqm)")
            else:
                print(f"        ❌ no price")
            time.sleep(0.3)

        result["raw_prices"]=raw_prices
        # FIX 5+6
        clean,lc=remove_outliers(raw_prices,f["area"],fallback=fallback_used)
        result["clean_prices"]=clean; result["low_confidence"]=lc

        if clean:
            avg=sum(clean)/len(clean)
            result["web_avg"]=round(avg); result["web_ppm"]=round(avg/f["area"])
            result["status"]="success"
            cf=" [LC]" if lc else ""; fb=" FB" if fallback_used else ""
            print(f"\n  {'⚠️ FALLBACK' if fallback_used else '✅ COMPOUND'}{cf}{fb}  avg={avg:,.0f} ({avg/f['area']:,.0f}/sqm) n={len(clean)}")
        else:
            result["status"]="no_price"; print(f"\n  ❌ No prices")
    except Exception as e:
        import traceback; result["error"]=traceback.format_exc(); result["status"]="error"; print(f"  💥 {e}")
    return result

def print_report(results):
    total=len(results); success=sum(1 for r in results if r["status"]=="success")
    no_price=sum(1 for r in results if r["status"]=="no_price")
    lc=sum(1 for r in results if r["low_confidence"])
    fallbacks=sum(1 for r in results if r["fallback_used"])

    print("\n\n"+"★"*60+"\n  SEMSAI TEST SUITE v4 — FINAL REPORT\n"+"★"*60)
    print(f"\n  Hit rate      : {success}/{total} ({100*success//total}%)")
    print(f"  Fallbacks     : {fallbacks}/{total}")
    print(f"  Low confidence: {lc}/{total}")
    print(f"  No price      : {no_price}/{total}")

    sanity_ok=True
    print(f"\n  {'─'*56}")
    print(f"  {'ID':3}  {'Compound':20}  {'Type':9}  {'ppm':>10}  n   Status")
    print(f"  {'─'*56}")
    for r in results:
        icon="✅" if r["status"]=="success" else "❌"
        lc_f=" [LC]" if r["low_confidence"] else ""
        fb_f=" FB" if r["fallback_used"] else ""
        if r["web_ppm"]>180000 and not r["low_confidence"]: sanity_ok=False
        print(f"  {icon} {r['id']:3}  {r['compound']:20}  {r['property_type']:9}  {r['web_ppm']:>10,}  {len(r['clean_prices']):<3} {r['status']}{lc_f}{fb_f}")

    grade="A" if success==total and sanity_ok else "B" if success>=total*0.9 else "C"
    print(f"\n  Grade: {grade}")
    print("★"*60)

def run_all_tests():
    print("★"*60+f"\n  SEMSAI v4 TEST SUITE\n  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"+"★"*60)
    results=[]
    for tc in TEST_CASES:
        r=run_single_test(tc); results.append(r); time.sleep(1.5)
    print_report(results)
    report={"run_at":datetime.now().isoformat(),"version":"v4","summary":{"total":len(results),"success":sum(1 for r in results if r["status"]=="success"),"no_price":sum(1 for r in results if r["status"]=="no_price"),"fallbacks":sum(1 for r in results if r["fallback_used"]),"low_conf":sum(1 for r in results if r["low_confidence"])},"results":results}
    with open("scraping_report_v4.json","w",encoding="utf-8") as f: json.dump(report,f,ensure_ascii=False,indent=2)
    print("\n  📄 Saved → scraping_report_v4.json")
    return report

if __name__ == "__main__":
    run_all_tests()
