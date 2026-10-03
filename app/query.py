"""Constrained NL → reviewed parameterized SQL. No generated SQL execution."""
import json, re, sqlite3
from pathlib import Path

QUESTIONS=[
 'What was our total recognized revenue in USD for paid invoices in 2024?',
 'Which region has the highest average MRR per account?',
 'How much have we given back in refunds?',
 "What's the churn rate among Enterprise accounts vs Starter?",
 'List the top 5 accounts by revenue, and flag any with CSAT ≤ 2.',
 "How many invoices are stuck in pending/failed and what's the exposed $?"
]

def plan(question):
    q=question.lower().strip(); params=[]
    normalized=re.sub(r"[^a-z0-9]+", " ", q).strip()
    patterns=[
        r"what was our total recognized revenue in usd for paid invoices in (?:19|20)\d{2}",
        r"(?:what is |what was )?(?:total )?(?:paid|net recognized|net) revenue(?: in usd)?(?: for| in) (?:19|20)\d{2}",
        r"which region has the highest average mrr per account",
        r"how much have we given back in refunds", r"(?:what is |total )?refunds",
        r"what s the churn rate among enterprise accounts vs starter",
        r"churn rate (?:among |for )?enterprise (?:accounts )?vs starter",
        r"list the top 5 accounts by revenue and flag any with csat 2",
        r"top 5 accounts by revenue",
        r"how many invoices are stuck in pending failed and what s the exposed",
        r"pending failed exposure",
    ]
    if not any(re.fullmatch(pattern, normalized) for pattern in patterns):
        raise ValueError('Unsupported question wording or filter. Use a documented question or alias; no unrecognized predicates are ignored.')
    # Restrict vocabulary to known question families: unsupported filters are unsafe.
    forbidden=r'\b(month|quarter|predict|forecast|next|last|only|excluding|between|before|after|europe|emea|apac|latam|na|canada)\b'
    if re.search(forbidden,q):raise ValueError('Unsupported filter or prediction; use a documented question.')
    if 'churn' in q and 'enterprise' in q and 'starter' in q:
        intent='churn';sql="SELECT plan, count(*) AS accounts, sum(churned) AS churned_accounts, round(100.0*sum(churned)/count(*),2) AS churn_pct FROM accounts WHERE plan IN ('Enterprise','Starter') GROUP BY plan ORDER BY plan"; lineage="SELECT source_row FROM accounts WHERE plan IN ('Enterprise','Starter')"
    elif 'mrr' in q and 'region' in q:
        intent='regional_mrr';sql='SELECT region, count(*) AS active_accounts, round(avg(mrr_usd_cents)/100.0,2) AS average_mrr_usd FROM accounts WHERE churned=0 GROUP BY region ORDER BY average_mrr_usd DESC, region LIMIT 1';lineage='SELECT source_row FROM accounts WHERE churned=0 AND region=(SELECT region FROM accounts WHERE churned=0 GROUP BY region ORDER BY avg(mrr_usd_cents) DESC, region LIMIT 1)'
    elif 'refund' in q and not 'revenue' in q:
        intent='refunds';sql="SELECT round(-coalesce(sum(amount_usd_cents),0)/100.0,2) AS refunds_usd FROM invoices WHERE status='refunded'";lineage="SELECT source_row FROM invoices WHERE status='refunded'"
    elif 'pending' in q and 'failed' in q:
        intent='exposure';sql="SELECT count(*) AS invoices, round(coalesce(sum(amount_usd_cents),0)/100.0,2) AS exposure_usd FROM invoices WHERE status IN ('pending','failed')";lineage="SELECT source_row FROM invoices WHERE status IN ('pending','failed')"
    elif re.search(r'top\s+5',q) and 'revenue' in q:
        intent='top_accounts';sql="""SELECT i.account_id, a.account_name, round(sum(i.amount_usd_cents)/100.0,2) AS net_revenue_usd, a.csat_score, CASE WHEN a.csat_score IS NULL THEN NULL ELSE a.csat_score<=2 END AS low_csat FROM invoices i JOIN accounts a USING(account_id) WHERE i.status IN ('paid','refunded') GROUP BY i.account_id ORDER BY sum(i.amount_usd_cents) DESC, i.account_id LIMIT 5""";lineage="SELECT source_row FROM invoices WHERE status IN ('paid','refunded') AND account_id IN (SELECT account_id FROM invoices WHERE status IN ('paid','refunded') GROUP BY account_id ORDER BY sum(amount_usd_cents) DESC, account_id LIMIT 5)"
    elif 'revenue' in q:
        years=re.findall(r'\b(?:19|20)\d{2}\b',q)
        if len(years)!=1:raise ValueError('Revenue question requires exactly one explicit year.')
        y=int(years[0]);params=[f'{y}-01-01',f'{y+1}-01-01']
        net='net' in q
        intent='net_revenue' if net else 'paid_revenue'
        filt="status IN ('paid','refunded')" if net else "status='paid'"
        sql=f'SELECT round(coalesce(sum(amount_usd_cents),0)/100.0,2) AS revenue_usd FROM invoices WHERE {filt} AND invoice_date>=? AND invoice_date<?'
        lineage=f'SELECT source_row FROM invoices WHERE {filt} AND invoice_date>=? AND invoice_date<?'
    else: raise ValueError('Unsupported question; supported intents: paid/net yearly revenue, regional MRR, refunds, Enterprise/Starter churn, top 5 accounts, pending/failed exposure.')
    # Reject additional predicates and multiple question intents rather than ignore them.
    if re.search(r'\b(pro|starter|enterprise|monthly|annual|202[0-9]|201[0-9])\b',q) and intent in ('regional_mrr','refunds','exposure','top_accounts'):
        raise ValueError('This intent does not support plan, cycle or year filters.')
    if intent in ('paid_revenue','net_revenue') and re.search(r'\b(starter|enterprise|pro|monthly|annual|top|mrr|churn|pending|failed)\b',q):raise ValueError('Unsupported additional revenue filter.')
    return intent,sql,params,lineage

def connect_readonly(db):
    con=sqlite3.connect(Path(db).resolve().as_uri()+'?mode=ro',uri=True);con.row_factory=sqlite3.Row
    allowed={sqlite3.SQLITE_SELECT,sqlite3.SQLITE_READ,sqlite3.SQLITE_FUNCTION,sqlite3.SQLITE_RECURSIVE}
    con.set_authorizer(lambda action,*args:sqlite3.SQLITE_OK if action in allowed else sqlite3.SQLITE_DENY)
    return con

def ask(db, question):
    if not isinstance(question,str) or not 1<=len(question)<=1000:raise ValueError('Question must be 1–1000 characters.')
    intent,sql,params,lineage=plan(question)
    with connect_readonly(db) as con:
        result=[dict(r) for r in con.execute(sql,params).fetchmany(100)]
        ids=[r[0] for r in con.execute(lineage,params)]
        report=json.loads(con.execute('SELECT report FROM metadata').fetchone()[0])
    return {'question':question,'intent':intent,'sql':sql,'parameters':params,'answer':result,'provenance':{'source_sha256':report['source_sha256'],'contributing_records':len(ids),'sample_csv_rows':ids[:10],'note':'Samples are not exhaustive; run the lineage SQL for every contributing CSV row.'},'lineage_sql':lineage,'assumptions':'Fixed FX; deterministic dedup; latest-invoice account snapshot. See specs/model.md.'}
