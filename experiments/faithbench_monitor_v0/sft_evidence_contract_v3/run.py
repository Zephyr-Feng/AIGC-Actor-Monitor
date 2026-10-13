"""Reuse frozen twenty-step training path with the new parser in this process only."""
import argparse,sys
from pathlib import Path
BASE=Path(__file__).resolve().parent
sys.path.insert(0,str(BASE));import contract
sys.path.insert(0,str(BASE.parent/'sft_smoke_v1'));import train_smoke as legacy
legacy.single=contract
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--inputs',type=Path,required=True);p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--preflight-only',action='store_true');a=p.parse_args()
 if a.preflight_only:legacy.cpu_preflight(a.inputs,a.base,a.output)
 else:legacy.run(a.inputs,a.base,a.output)
