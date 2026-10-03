"""Validated ledger with explicit assumptions and row lineage."""
import csv, hashlib, json, re, sqlite3, os
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

PLANS = {v: k for k, values in {'Starter':['starter','start','tier 1'], 'Pro':['pro','professional','tier 2'], 'Enterprise':['enterprise','ent','tier 3']}.items() for v in values}
STATUSES = {v:k for k,values in {'paid':['paid','complete','completed','success'],'pending':['pending','in_review','awaiting'],'failed':['failed','declined','error'],'refunded':['refunded','refund','charged_back'],'void':['void','cancelled','canceled']}.items() for v in values}
CYCLES = {'monthly':'monthly','annual':'annual','annually':'annual','yearly':'annual'}
PRIORITY = {'pending':0,'failed':1,'void':2,'paid':3,'refunded':4}

def cents(value):
    return int((Decimal(value)*100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

def date(value, flags):
    if re.fullmatch(r'\d{2}[/-]\d{2}[/-]\d{4}',value) and all(int(x)<=12 for x in re.split('[/-]',value)[:2]):
        flags.append('ambiguous_date:'+value)
    for fmt in ('%Y-%m-%d','%Y/%m/%d','%m/%d/%Y','%b %d %Y','%d-%m-%Y'):
        try: return datetime.strptime(value,fmt).date().isoformat()
        except ValueError: pass
    raise ValueError('invalid date: '+value)

def clean(raw, source_row):
    r={k:v.strip() for k,v in raw.items()}; flags=[]
    for k in ('invoice_id','account_id','account_name'):
        if not r[k]: raise ValueError('missing '+k)
    for k,m in [('plan',PLANS),('status',STATUSES),('billing_cycle',CYCLES)]: r[k]=m[r[k].lower()]
    r['currency']=r['currency'].upper(); r['region']=r['region'].upper()
    fx={'USD':Decimal('1'),'EUR':Decimal('1.08'),'GBP':Decimal('1.27')}[r['currency']]
    if r['region'] not in ('NA','EMEA','APAC','LATAM'): raise ValueError('invalid region')
    r['seats']=int(r['seats']); r['support_tickets']=int(r['support_tickets'])
    discount=Decimal(r['discount_pct'])
    if not discount.is_finite() or not 0<=discount<=100 or r['seats']<=0 or r['support_tickets']<0: raise ValueError('invalid seats/discount/tickets')
    r['csat_score']=int(r['csat_score']) if r['csat_score'] else None
    if r['csat_score'] is not None and not 1<=r['csat_score']<=5: raise ValueError('invalid csat')
    value=r.pop('amount').replace(',','')
    value=re.sub(r'^[$€£]','',value)
    value=re.sub(r'\s+'+r['currency']+r'$','',value)
    amount=Decimal(value)
    if not amount.is_finite() or (r['status']=='refunded' and amount>=0) or (r['status']!='refunded' and amount<0): raise ValueError('invalid amount sign/value')
    r['amount_local_cents']=cents(amount); r['amount_usd_cents']=cents(amount*fx)
    r['mrr_usd_cents']=cents(Decimal({'Starter':49,'Pro':99,'Enterprise':299}[r['plan']])*r['seats']*(1-discount/100))
    r['discount_pct']=float(discount)
    for k in ('signup_date','invoice_date'): r[k]=date(r[k],flags)
    bools={'true':1,'yes':1,'1':1,'y':1,'false':0,'no':0,'0':0,'n':0}
    r['churned']=bools[r['churned'].lower()]
    email=r['contact_email'].lower()
    if '_at_' in email: email=email.replace('_at_','@');flags.append('email_repaired')
    if email and not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',email): email='';flags.append('email_invalid')
    r['contact_email']=email or None; r['industry']=r['industry'] or None
    methods={'credit card':'credit_card','credit_card':'credit_card','ach':'ACH','wire transfer':'wire','wire':'wire','invoice':'invoice','':None}
    r['payment_method']=methods[r['payment_method'].lower()]
    r['source_row']=source_row; r['flags']=json.dumps(flags)
    return r

def build(csv_path, db_path):
    csv_path=Path(csv_path);db_path=Path(db_path);db_path.parent.mkdir(parents=True,exist_ok=True)
    winners={}; seen=set(); audit=[]; rejected=[]; total=0
    with csv_path.open(newline='',encoding='utf-8-sig') as f:
        for n,raw in enumerate(csv.DictReader(f),2):
            total+=1
            try: r=clean(raw,n)
            except (ValueError,KeyError,TypeError,ArithmeticError) as e:
                rejected.append({'source_row':n,'reason':str(e),'raw':raw});continue
            fingerprint=tuple(raw.items()); old=winners.get(r['invoice_id'])
            if fingerprint in seen:
                audit.append({'source_row':n,'invoice_id':r['invoice_id'],'reason':'full_duplicate'});continue
            seen.add(fingerprint)
            if old:
                winner,loser=(r,old) if PRIORITY[r['status']]>PRIORITY[old['status']] else (old,r)
                audit.append({'source_row':loser['source_row'],'invoice_id':r['invoice_id'],'reason':'conflicting_invoice_id'})
                winners[r['invoice_id']]=winner
            else: winners[r['invoice_id']]=r
    if not winners: raise ValueError('no valid invoice rows')
    for x in audit:x['winner_source_row']=winners[x['invoice_id']]['source_row']
    rows=list(winners.values()); cols=list(rows[0]); tmp=db_path.with_suffix('.tmp')
    if tmp.exists():tmp.unlink()
    con=sqlite3.connect(tmp)
    ints={'seats','support_tickets','csat_score','churned','source_row','amount_local_cents','amount_usd_cents','mrr_usd_cents'}
    con.execute('CREATE TABLE invoices ('+', '.join(k+' '+('INTEGER' if k in ints else 'REAL' if k=='discount_pct' else 'TEXT')+(' PRIMARY KEY' if k=='invoice_id' else '') for k in cols)+')')
    con.executemany('INSERT INTO invoices VALUES ('+','.join('?' for _ in cols)+')',[[r[k] for k in cols] for r in rows])
    con.executescript('''CREATE TABLE accounts AS SELECT * FROM (SELECT *, ROW_NUMBER() OVER(PARTITION BY account_id ORDER BY invoice_date DESC, invoice_id DESC) AS rn FROM invoices) WHERE rn=1;
    CREATE UNIQUE INDEX account_key ON accounts(account_id);
    CREATE INDEX invoice_account ON invoices(account_id);''')
    disagreements=con.execute("SELECT count(*) FROM (SELECT account_id FROM invoices GROUP BY account_id HAVING count(DISTINCT plan)>1 OR count(DISTINCT region)>1 OR count(DISTINCT churned)>1 OR count(DISTINCT seats)>1 OR count(DISTINCT discount_pct)>1)").fetchone()[0]
    report={'input_rows':total,'clean_invoices':len(rows),'accounts':con.execute('SELECT count(*) FROM accounts').fetchone()[0],'duplicates_removed':len(audit),'quarantined':len(rejected),'flagged_invoices':sum(r['flags']!='[]' for r in rows),'accounts_with_conflicting_attributes':disagreements,'source_sha256':hashlib.sha256(csv_path.read_bytes()).hexdigest()}
    con.execute('CREATE TABLE metadata (report TEXT)');con.execute('INSERT INTO metadata VALUES (?)',(json.dumps(report),));con.commit();con.close();os.replace(tmp,db_path)
    for name,data in [('quality_report',report),('dedup_audit',audit),('quarantine',rejected)]:
        (db_path.parent/(name+'.json')).write_text(json.dumps(data,indent=2))
    return report
