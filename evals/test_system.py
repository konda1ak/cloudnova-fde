"""Hand-calculated golden fixture; does not derive expected answers from app SQL."""
import csv, json, sqlite3, tempfile, unittest
from pathlib import Path
from app.pipeline import build, clean
from app.query import ask, QUESTIONS, connect_readonly

BASE=dict(invoice_id='I1',account_id='A',account_name='Alpha',contact_email='billing_at_alpha.com',region='NA',industry='',plan='Tier 1',billing_cycle='annual',seats='10',currency='USD',amount='$4,900.00',discount_pct='0',status='Complete',payment_method='Credit Card',signup_date='Jan 5 2023',invoice_date='01/05/2024',churned='N',csat_score='2',support_tickets='0')

class LedgerEvaluation(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.db=self.root/'ledger.sqlite'
        rows=[BASE.copy(),BASE.copy(),dict(BASE,status='pending',amount='5000'),
              dict(BASE,invoice_id='I2',account_id='B',account_name='Beta',region='EMEA',plan='ENT',seats='2',currency='EUR',amount='1,000.00 EUR',churned='Yes',csat_score='5'),
              dict(BASE,invoice_id='I3',amount='-100',status='REFUND',invoice_date='2024-02-01'),
              dict(BASE,invoice_id='I4',account_id='C',account_name='Gamma',region='APAC',plan='Professional',seats='5',currency='GBP',amount='200',status='awaiting',csat_score='4'),
              dict(BASE,invoice_id='I5',account_id='C',account_name='Gamma',region='APAC',plan='Professional',seats='5',currency='GBP',amount='300',status='declined',csat_score='4',invoice_date='2024-03-01'),
              dict(BASE,invoice_id='BAD',seats='-1')]
        p=self.root/'fixture.csv'
        with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=BASE.keys());w.writeheader();w.writerows(rows)
        self.report=build(p,self.db)
    def tearDown(self):self.tmp.cleanup()
    def answer(self,q):return ask(self.db,q)['answer']
    def test_paid_revenue_2024(self):self.assertEqual(self.answer(QUESTIONS[0]),[{'revenue_usd':5980.0}])
    def test_net_revenue(self):self.assertEqual(self.answer('net revenue in 2024')[0]['revenue_usd'],5880.0)
    def test_active_regional_mrr_annual_not_divided(self):self.assertEqual(self.answer(QUESTIONS[1]),[{'region':'APAC','active_accounts':1,'average_mrr_usd':495.0}])
    def test_refunds(self):self.assertEqual(self.answer(QUESTIONS[2])[0]['refunds_usd'],100.0)
    def test_churn_account_grain(self):self.assertEqual(self.answer(QUESTIONS[3]),[{'plan':'Enterprise','accounts':1,'churned_accounts':1,'churn_pct':100.0},{'plan':'Starter','accounts':1,'churned_accounts':0,'churn_pct':0.0}])
    def test_top_accounts_low_csat(self):
        a=self.answer(QUESTIONS[4]);self.assertEqual(a[0]['account_id'],'A');self.assertEqual(a[0]['net_revenue_usd'],4800.0);self.assertEqual(a[0]['low_csat'],1)
    def test_exposure_fx(self):self.assertEqual(self.answer(QUESTIONS[5]),[{'invoices':2,'exposure_usd':635.0}])
    def test_dedup_quarantine_lineage(self):
        self.assertEqual((self.report['clean_invoices'],self.report['duplicates_removed'],self.report['quarantined']),(5,2,1))
        a=ask(self.db,QUESTIONS[0]);self.assertEqual(a['provenance']['contributing_records'],2)
        self.assertEqual(sorted(a['provenance']['sample_csv_rows']),[2,5])
        audit=json.loads((self.root/'dedup_audit.json').read_text());self.assertTrue(all(x['winner_source_row']==2 for x in audit))
    def test_dates_discounts_signs(self):
        r=clean(dict(BASE,invoice_date='05-01-2024',discount_pct='20'),2)
        self.assertEqual(r['invoice_date'],'2024-01-05');self.assertEqual(r['mrr_usd_cents'],39200);self.assertIn('ambiguous_date',r['flags']);self.assertEqual(r['contact_email'],'billing@alpha.com')
        with self.assertRaises(ValueError):clean(dict(BASE,status='REFUND',amount='100'),2)
    def test_refund_duplicate_priority(self):
        p=self.root/'dupe.csv'
        with p.open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=BASE.keys());w.writeheader();w.writerows([BASE,dict(BASE,status='REFUND',amount='-20')])
        build(p,self.db);self.assertEqual(self.answer('refunds')[0]['refunds_usd'],20)
    def test_no_ignored_filters(self):
        for q in ['refunds in 2024','top 5 accounts by revenue with 20 seats','paid revenue in 2024; DROP TABLE invoices','which region has the highest average MRR per account with low CSAT?']:
            with self.assertRaises(ValueError):ask(self.db,q)
    def test_read_only(self):
        with connect_readonly(self.db) as con:
            with self.assertRaises(sqlite3.DatabaseError):con.execute('DELETE FROM invoices')
    @unittest.expectedFailure
    def test_expected_failure_predictive_churn(self):
        # Ground truth unavailable: no future labels/history; intentionally abstains.
        self.assertIsNotNone(ask(self.db,'Predict which accounts will churn next month'))

if __name__=='__main__':unittest.main(verbosity=2)
