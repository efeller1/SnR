import openpyxl, pandas as pd
F='/root/.claude/uploads/ba536949-1b86-5e29-81a6-20c0ae4afb5b/c202c99c-Model_Backtest_20260304214422.xlsx'
def load():
    rows=list(openpyxl.load_workbook(F,data_only=True).active.iter_rows(values_only=True))
    i=next(k for k,r in enumerate(rows) if r[0]=='Monthly Returns')
    out=[]
    for r in rows[i+3:]:
        if not isinstance(r[0],(int,float)) or not isinstance(r[1],(int,float)): break
        out.append((int(r[0]),int(r[1]),r[2],r[4]))
    d=pd.DataFrame(out,columns=['year','month','model','spx'])
    return d.sort_values(['year','month']).reset_index(drop=True)
