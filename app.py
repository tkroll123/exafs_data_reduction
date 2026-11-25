"""EXAFS data reduction web app (Flask).

Run:  .venv/bin/python app.py      then open http://127.0.0.1:5050
"""
import uuid
from flask import Flask, Response, jsonify, render_template, request

import xas_core

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 200 * 1024 * 1024

SCANS = {}   # id -> parsed scan (in memory; cleared on restart)


def scan_summary(sid, s):
    return {'id': sid, 'filename': s['meta']['filename'], 'meta': s['meta'],
            'columns': s['columns'],
            'roles': xas_core.guess_roles(s['columns'], s['meta'].get('beamline_guess'))}


@app.route('/')
def index():
    return render_template('index.html', foils=xas_core.FOILS)


@app.post('/api/open')
def open_files():
    out, errors = [], []
    for f in request.files.getlist('files'):
        raw = f.read()
        try:
            text = raw.decode('utf-8')
        except UnicodeDecodeError:
            text = raw.decode('iso-8859-1')
        try:
            s = xas_core.parse_ssrl(text, f.filename)
        except xas_core.ParseError as e:
            errors.append({'filename': f.filename, 'error': str(e)})
            continue
        sid = uuid.uuid4().hex[:10]
        SCANS[sid] = s
        out.append(scan_summary(sid, s))
    return jsonify({'scans': out, 'errors': errors})


@app.get('/api/scan/<sid>')
def get_scan(sid):
    s = SCANS.get(sid)
    if s is None:
        return jsonify({'error': 'unknown scan'}), 404
    d = scan_summary(sid, s)
    d['header'] = s['header']
    d['offsets'] = s['offsets']
    d['weights'] = s['weights']
    d['data'] = {c: s['data'][:, i].tolist() for i, c in enumerate(s['columns'])}
    return jsonify(d)


@app.post('/api/process/<sid>')
def process_scan(sid):
    s = SCANS.get(sid)
    if s is None:
        return jsonify({'error': 'unknown scan'}), 404
    try:
        return jsonify(xas_core.process(s, request.get_json()))
    except (KeyError, ValueError) as e:
        return jsonify({'error': str(e)}), 400


@app.post('/api/export')
def export_scan():
    """Body: {id, cfg} (or {items: [{id, cfg}]} with one item). Returns the .dat as a download."""
    body = request.get_json()
    it = body['items'][0] if body.get('items') else body
    s = SCANS.get(it.get('id'))
    if s is None:
        return jsonify({'errors': [{'error': 'unknown scan (re-open the file)'}]}), 400
    name = s['meta']['filename']
    if s['meta'].get('kind'):
        return jsonify({'errors': [{'file': name, 'error': f'already a {s["meta"]["kind"]} file - nothing to re-export'}]}), 400
    try:
        res = xas_core.process(s, it['cfg'])
        text = xas_core.export_text(s, it['cfg'], res)
    except (KeyError, ValueError) as e:
        return jsonify({'errors': [{'file': name, 'error': str(e)}]}), 400
    fname = xas_core.output_basename(name) + '_processed.dat'
    return Response(text, mimetype='text/plain',
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})


def _processed_items(body):
    items = []
    for it in body.get('items', []):
        s = SCANS.get(it['id'])
        if s is None:
            raise ValueError('unknown scan (re-open the file)')
        items.append((s, it['cfg'], xas_core.process(s, it['cfg'])))
    return items


@app.post('/api/merge')
def merge_scans():
    """Body: {items: [{id, cfg}], mode: 'first' | 'pointwise'}."""
    body = request.get_json()
    try:
        items = _processed_items(body)
        return jsonify(xas_core.merge(items, body.get('mode', 'first')))
    except (KeyError, ValueError) as e:
        return jsonify({'error': str(e)}), 400


@app.post('/api/merge/export')
def export_merged():
    body = request.get_json()
    try:
        items = _processed_items(body)
        m = xas_core.merge(items, body.get('mode', 'first'))
    except (KeyError, ValueError) as e:
        return jsonify({'errors': [{'error': str(e)}]}), 400
    fname = f'{xas_core.merged_basename([s["meta"]["filename"] for s, _, _ in items])}_merged_{len(items)}scans.dat'
    return Response(xas_core.export_merged_text(items, m), mimetype='text/plain',
                    headers={'Content-Disposition': f'attachment; filename="{fname}"'})


@app.delete('/api/scan/<sid>')
def close_scan(sid):
    SCANS.pop(sid, None)
    return jsonify({'ok': True})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5050, debug=True)
