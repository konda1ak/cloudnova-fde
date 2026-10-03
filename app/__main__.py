import argparse, json, sys
from pathlib import Path
from .pipeline import build
from .query import QUESTIONS, ask

def main():
    p=argparse.ArgumentParser(description='CloudNova ledger demo')
    p.add_argument('--input',default='data/cloudnova_invoices.csv');p.add_argument('--output',default='output');p.add_argument('--ask');args=p.parse_args()
    try:
        db=Path(args.output)/'ledger.sqlite';report=build(args.input,db)
        print(json.dumps({'quality':report},indent=2))
        answers=[ask(db,q) for q in ([args.ask] if args.ask else QUESTIONS)]
        print(json.dumps(answers,indent=2));(db.parent/'answers.json').write_text(json.dumps(answers,indent=2))
    except (ValueError,OSError) as e:print('ERROR: '+str(e),file=sys.stderr);return 2
    return 0

if __name__=='__main__':sys.exit(main())
