import csv
import sys
from pathlib import Path
from datetime import datetime, timezone

def cycle(root, model):
    files=list(Path(root).rglob("datos_vigilancia_"+model.lower()+".csv"))
    if len(files)!=1:
        raise ValueError("No hay un CSV de vigilancia inequívoco")
    with files[0].open(encoding="utf-8-sig",newline="") as f:
        runs={datetime.fromisoformat(row["run_time"].replace("Z","+00:00")).astimezone(timezone.utc) for row in csv.DictReader(f,delimiter=";")}
    if len(runs)!=1:
        raise ValueError("Corrida ausente o ambigua")
    run=runs.pop()
    print(f'{model}: corrida CSV UTC {run.isoformat()}', file=sys.stderr)
    allowed = (0,6,12,18) if model == 'GFS' else (0,12)
    if run.hour not in allowed or run.minute or run.second or run.microsecond:
        raise ValueError(f'Corrida no admitida para {model}: {run.isoformat()}')
    return run.strftime("%Y%m%d%H")

if __name__=="__main__":
    print(cycle(sys.argv[1],sys.argv[2]))
