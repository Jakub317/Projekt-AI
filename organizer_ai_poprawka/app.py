from pathlib import Path
import csv, os, re, subprocess, sys, threading, uuid
from flask import Flask, jsonify, render_template, request, send_from_directory, abort
from werkzeug.utils import secure_filename

ROOT=Path(__file__).resolve().parent
UPLOADS=ROOT/'uploads'; MODELS=ROOT/'model'; RESULTS=ROOT/'results'
SCRIPT=ROOT/'scripts'/'analizuj_wideo_przegrodki.py'
ALLOWED={'mp4','avi','mov','mkv','m4v'}
app=Flask(__name__)
app.config['MAX_CONTENT_LENGTH']=1024*1024*1024
lock=threading.Lock()
task={'id':None,'status':'idle','progress':0,'message':'Wybierz nagranie, aby rozpocząć.','video_name':None,'error':None}

def model_file():
    for p in (MODELS/'best.pt',ROOT/'best.pt'):
        if p.is_file(): return p
    return None

def snapshot():
    with lock: return dict(task)

def update(**kw):
    with lock: task.update(kw)

def worker(video, tid, model):
    out=RESULTS/tid; out.mkdir(parents=True,exist_ok=True)
    cmd=[sys.executable,str(SCRIPT),'--video',str(video),'--model',str(model),'--output',str(out)]
    update(status='running',progress=1,message='Uruchamianie YOLO…')
    try:
        p=subprocess.Popen(cmd,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1)
        with (out/'analiza.log').open('w',encoding='utf-8') as log:
            for line in p.stdout:
                log.write(line); log.flush()
                m=re.search(r'Postep:\s*([\d.]+)%',line,re.I)
                if m:
                    n=max(1,min(99,int(float(m.group(1)))))
                    update(progress=n,message=f'Analizowanie nagrania… {n}%')
        code=p.wait()
        if code==0: update(status='completed',progress=100,message='Analiza zakończona.')
        else:
            lines=(out/'analiza.log').read_text(encoding='utf-8',errors='replace').splitlines()
            update(status='error',message='Analiza zakończyła się błędem.',error='\n'.join(lines[-15:]))
    except Exception as e: update(status='error',message='Nie udało się uruchomić analizy.',error=str(e))

@app.get('/')
def home(): return render_template('index.html',model_ready=model_file() is not None)

def read_slot_states(report_path):
    slots = {
        str(i): "unknown"
        for i in range(1, 9)
    }

    if not report_path or not report_path.is_file():
        return slots

    try:
        with report_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)

            for row in reader:
                slot = str(row.get("przegrodka", "")).strip()
                event = str(row.get("typ", "")).strip().upper()

                if slot not in slots:
                    continue

                if event == "DODANIE":
                    slots[slot] = "occupied"
                elif event in ("USUN", "USUNIĘCIE", "USUNIECIE"):
                    slots[slot] = "empty"

    except Exception as e:
        print("Błąd odczytu raportu:", e)

    return slots


@app.get('/api/status')
def status():
    s = snapshot()
    tid = s.get("id")

    folder = None
    if tid:
        folder = (RESULTS / tid).resolve()

        if not str(folder).startswith(str(RESULTS.resolve()) + os.sep):
            folder = None

    report_path = folder / "raport.csv" if folder else None
    video_path = folder / "annotated_video.mp4" if folder else None

    s["video_ready"] = bool(video_path and video_path.is_file())
    s["report_ready"] = bool(report_path and report_path.is_file())
    s["slots"] = read_slot_states(report_path)

    return jsonify(s)

@app.post('/api/analyze')
def analyze():
    m=model_file()
    if not m: return jsonify(error='Brak modelu. Skopiuj best.pt do folderu model/.'),400
    f=request.files.get('video')
    if not f or not f.filename: return jsonify(error='Wybierz plik wideo.'),400
    ext=f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED: return jsonify(error='Dozwolone formaty: MP4, AVI, MOV, MKV.'),400
    if snapshot()['status'] in ('queued','running'): return jsonify(error='Analiza już trwa.'),409
    tid=uuid.uuid4().hex[:12]; name=secure_filename(f.filename) or 'nagranie.mp4'
    UPLOADS.mkdir(exist_ok=True); path=UPLOADS/f'{tid}_{name}'; f.save(path)
    update(id=tid,status='queued',progress=0,message='Przyjęto nagranie…',video_name=name,error=None)
    threading.Thread(target=worker,args=(path,tid,m),daemon=True).start()
    return jsonify(ok=True,id=tid)

@app.get('/results/<tid>/<path:name>')
def result(tid, name):
    folder = (RESULTS / tid).resolve()
    results_root = RESULTS.resolve()

    if not str(folder).startswith(str(results_root) + os.sep):
        abort(404)

    file_path = (folder / name).resolve()

    if not str(file_path).startswith(str(folder) + os.sep):
        abort(404)

    if not file_path.is_file():
        abort(404)

    response = send_from_directory(
        folder,
        name,
        conditional=True,
        mimetype='video/mp4' if name.endswith('.mp4') else None
    )

    return response

@app.get('/api/events')
def events():
    tid=snapshot().get('id'); path=RESULTS/tid/'raport.csv' if tid else None
    if not path or not path.is_file(): return jsonify(events=[])
    with path.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    return jsonify(events=list(reversed(rows)))

@app.errorhandler(413)
def too_large(_): return jsonify(error='Plik przekracza limit 1 GB.'),413

if __name__=='__main__':
    for d in (UPLOADS,MODELS,RESULTS): d.mkdir(exist_ok=True)
    app.run(host='127.0.0.1',port=5000,debug=False,threaded=True)
