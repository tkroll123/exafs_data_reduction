"""
Configurable reader / processor for SSRL "EXAFS Data Collector" ASCII files.

This ports the processing logic of xas_worker-master/XAS_Worker_*.py
(auto bad-channel dropping, summed fluorescence ratio, foil calibration,
per-file statistics) but replaces the hard-coded pieces with parameters:

  hard-coded in XAS_Worker          -> parameter here
  ---------------------------------    -------------------------------
  'Achieved Energy' index            -> energy
  'I0', 'I1'                         -> i0, i1
  'scatter' (7-3) / 'I2' (9-3) foil  -> foil_num, foil_den, foil_method
  regex 'FF*' + SCA1_ -> FF rename   -> fluor_channels (auto-guessed;
                                        original column names are kept)
  skiprows = endColumn + 21          -> header parsed by locating "Data:"
  auto-drop threshold 5              -> auto_drop_threshold
  self.element                       -> element
"""
import re
import numpy as np

FOILS = {'Sc': 4492.8, 'Ti': 4966.4, 'V': 5465.1, 'Cr': 5989.2, 'Mn': 6539.0,
         'Fe': 7111.2, 'Co': 7708.9, 'Ni': 8332.8, 'Cu': 8978.9, 'Zn': 9658.6}

FLUOR_RE = re.compile(r'^(SCA\d*_|FF)\d+$', re.I)
BEAMLINE_RE = re.compile(r'^\s*(\d)(\d)\s+[A-Za-z]')   # '73 unfocused ...' -> 7, 3
GROUP_RE = re.compile(r'^(.*?)_?\d+$')   # 'SCA1_12' -> 'SCA1', 'FF3' -> 'FF'
ICR_RE = re.compile(r'^ICR_?\d+$', re.I)


class ParseError(Exception):
    pass


def _floats(line):
    try:
        return [float(x) for x in line.split()]
    except ValueError:
        return None


APP_MARK = 'EXAFS Data Reduction (Flask) - '


def parse_processed(lines, filename):
    """Read a *_processed.dat or *_merged_*.dat written by this app."""
    kind = 'merged' if 'merged XAS data' in lines[0] else 'processed'
    first = next((i for i, l in enumerate(lines) if l.strip() and not l.startswith('#')), None)
    if first is None:
        raise ParseError('Processed file contains no data rows.')
    header = [l[2:] if l.startswith('# ') else l[1:] for l in lines[:first]]
    columns = header[-1].split()
    sections, sec = {}, 'top'
    for h in header[1:-1]:
        m = re.match(r'^\[(.+)\]$', h.strip())
        if m:
            sec = m.group(1); sections[sec] = {}; continue
        if ': ' in h and not h.startswith(' ') and not h.startswith('---'):
            k, v = h.split(': ', 1)
            sections.setdefault(sec, {})[re.split(r'\s*\(', k.strip())[0]] = v.strip()
    rows = []
    for l in lines[first:]:
        v = _floats(l)
        if v is not None and len(v) == len(columns):
            rows.append(v)
    src = sections.get('source', {})
    meta = {'filename': filename, 'kind': kind,
            'format': f'{kind} file (this app)', 'rows_read': len(rows), 'rows_skipped': 0,
            'date': src.get('collected'), 'sections': sections,
            'comments': [h.split(': ', 1)[1] for h in header if h.startswith('comment: ')],
            'original_header': header[:-1]}
    bl = re.match(r'BL(\d-\d)', src.get('beamline', ''))
    if bl:
        meta['beamline_guess'] = bl.group(1)
    if kind == 'processed':
        meta['source_file'] = src.get('file')
    return {'meta': meta, 'header': header, 'columns': columns, 'weights': None, 'offsets': None,
            'data': np.array(rows)}


def result_from_processed(scan):
    """Turn an opened processed/merged file into the same structure process() returns,
    so it can be shown and merged. Counts are recovered as SumRatio * I0 (exact)."""
    m, c, D = scan['meta'], scan['columns'], scan['data']
    col = lambda *names: next((D[:, c.index(n)] for n in names if n in c), None)
    energy = col('Energy_cal', 'Energy')
    if energy is None or col('SumRatio') is None:
        raise KeyError('Processed file lacks Energy / SumRatio columns.')
    e_raw = col('Energy_raw')
    i0 = col('I0', 'Sum_I0')
    sr = col('SumRatio')
    counts = col('Sum_counts')
    if counts is None:
        counts = sr * i0
    t = col('ln(I0/I1)', 'ln(sumI0/sumI1)')
    i1 = i0 / np.exp(t) if t is not None else None
    sec = m['sections']
    ch, cal = sec.get('channels', {}), sec.get('energy calibration', {})
    lst = lambda v: [] if not v or v == 'none' else v.split()
    if m['kind'] == 'merged':
        sm = sec.get('summary', {})
        mshift = re.search(r'mean=([+-]?[\d.]+)', sm.get('calibration_shift_eV', ''))
        shift, calibrated, det = (float(mshift.group(1)) if mshift else 0.0), True, 'merged file'
        kept = []
    else:
        sh = cal.get('energy_shift_eV', '')
        shift = float(sh.split()[0]) if sh and sh.split()[0] not in ('n/a',) else 0.0
        calibrated = cal.get('calibrated', '').startswith('yes')
        det, kept = ch.get('detector_used', 'n/a'), lst(ch.get('channels_used'))

    def stats(a):
        if a is None or not np.isfinite(a).any():
            return None
        return {'mean': float(np.nanmean(a)), 'min': float(np.nanmin(a)), 'max': float(np.nanmax(a))}
    return {
        'processed': {'kind': m['kind'], 'detector': det, 'calibrated': calibrated, 'shift': shift,
                      'element': cal.get('element'), 'edge_found': cal.get('edge_found_eV'),
                      'reference': cal.get('reference_energy_eV'), 'method': cal.get('method'),
                      'n_inputs': sum(1 for h in m['original_header'] if re.match(r'^\s*\d+\. ', h)) or None},
        'energy_raw': (e_raw if e_raw is not None else energy).tolist(), 'energy': energy.tolist(),
        'shift': shift, 'channels': {}, 'kept': kept,
        'auto_dropped': lst(ch.get('auto_dropped')), 'manual_dropped': lst(ch.get('manual_dropped')),
        'detectors': [{'name': det, 'selected': True, 'n_channels': len(kept), 'n_kept': len(kept),
                       'mean_ratio': None, 'jump': None, 'noise': None, 'snr': None}],
        'detector_mode': 'from file',
        'sumratio': _nan2none(sr), 'sumcounts': _nan2none(counts), 'i0': _nan2none(i0),
        'i1': _nan2none(i1) if i1 is not None else None,
        'transmission': _nan2none(t) if t is not None else None,
        'calibration': None,
        'stats': {'sumratio': stats(sr), 'i0': stats(i0), 'i1': stats(i1),
                  'energy_min': float(np.nanmin(energy)), 'energy_max': float(np.nanmax(energy)),
                  'calibration_shift': shift},
    }


def parse_ssrl(text, filename=''):
    """Parse an SSRL Data Collector file, a processed/merged file written by this app,
    or (fallback) a generic whitespace-delimited numeric ASCII file. Returns a dict."""
    lines = text.splitlines()
    if lines and lines[0].startswith('# ' + APP_MARK):
        return parse_processed(lines, filename)
    data_idx = next((i for i, l in enumerate(lines) if l.strip() == 'Data:'), None)

    meta = {'filename': filename, 'format': 'unknown'}
    header_lines = []
    weights = offsets = None

    if data_idx is not None:
        meta['format'] = 'SSRL EXAFS Data Collector'
        header_lines = [l.rstrip() for l in lines[:data_idx]]
        columns = []
        j = data_idx + 1
        while j < len(lines) and lines[j].strip():
            columns.append(lines[j].strip())
            j += 1
        body = lines[j:]

        # Header fields (fixed layout of Data Collector 4.0, read defensively)
        if header_lines:
            meta['collector'] = header_lines[0].strip()
        if len(header_lines) > 1:
            meta['date'] = header_lines[1].strip()
        for l in header_lines:
            m = re.search(r'PTS:\s*(\d+)\s+COLS:\s*(\d+)', l)
            if m:
                meta['pts'], meta['cols'] = int(m.group(1)), int(m.group(2))
        if len(header_lines) > 3:
            meta['detector_file'] = header_lines[3].strip()
        if len(header_lines) > 4:
            meta['region_file'] = header_lines[4].strip()
        # Beamline line, e.g. "73 unfocused  0.000 0 X 1.920000 20000" -> BL7-3.
        # Normally header line 6; otherwise any line starting with a 2-digit number + a word.
        cand = ([5] if len(header_lines) > 5 else []) + list(range(len(header_lines)))
        for k in cand:
            m = BEAMLINE_RE.match(header_lines[k])
            if m:
                meta['beamline_line'] = header_lines[k].strip()
                meta['beamline_guess'] = f'{m.group(1)}-{m.group(2)}'
                break
        else:
            if len(header_lines) > 5:
                meta['beamline_line'] = header_lines[5].strip()
        for k, l in enumerate(header_lines):
            if l.strip() == 'Weights:' and k + 1 < len(header_lines):
                weights = _floats(header_lines[k + 1])
            if l.strip() == 'Offsets:' and k + 1 < len(header_lines):
                offsets = _floats(header_lines[k + 1])
        stop = next((k for k, l in enumerate(header_lines) if l.strip() == 'Weights:'),
                    len(header_lines))
        if len(header_lines) > 6:
            meta['scan_params'] = header_lines[6].strip()
        meta['comments'] = [l.strip() for l in header_lines[7:stop] if l.strip()]
    else:
        # Generic ASCII: numeric block, optional header line just above it
        first = next((i for i, l in enumerate(lines) if _floats(l)), None)
        if first is None:
            raise ParseError('No numeric data found.')
        header_lines = lines[:first]
        ncol = len(_floats(lines[first]))
        columns = None
        if first > 0:
            cand = re.split(r'[\s,]+', lines[first - 1].lstrip('#').strip())
            if len(cand) == ncol:
                columns = cand
        columns = columns or [f'col{i + 1}' for i in range(ncol)]
        body = lines[first:]
        meta['format'] = 'generic ASCII'

    rows, skipped = [], 0
    for l in body:
        if not l.strip():
            continue
        v = _floats(l.replace(',', ' '))
        if v is None or len(v) != len(columns):
            skipped += 1
            continue
        rows.append(v)
    if not rows:
        raise ParseError('Header found but no data rows matched the column count.')

    data = np.array(rows)
    meta['rows_read'] = len(rows)
    meta['rows_skipped'] = skipped
    if 'pts' in meta and meta['pts'] != len(rows):
        meta['warning'] = f"Header says PTS={meta['pts']} but {len(rows)} rows were read."

    return {'meta': meta, 'header': header_lines, 'columns': columns,
            'weights': weights, 'offsets': offsets, 'data': data}


# Beamline-specific foil (reference) channels: (numerator, denominator) for mu = ln(num/den)
FOIL_DEFAULTS = {'7-3': ('I0', 'Scatter')}


def guess_roles(columns, beamline=None):
    """Best guess at which column plays which role (beamline-aware for the foil)."""
    lc = {c.lower(): c for c in columns}

    def pick(*names):
        for n in names:
            if n.lower() in lc:
                return lc[n.lower()]
        return None

    fluor = [c for c in columns if FLUOR_RE.match(c)]
    foil_num, foil_den = pick('I1'), pick('I2')
    foil_note = 'default I1 / I2'
    if beamline in FOIL_DEFAULTS:
        n, d = FOIL_DEFAULTS[beamline]
        if pick(n) and pick(d):
            foil_num, foil_den = pick(n), pick(d)
            foil_note = f'BL{beamline} default {n} / {d}'
        else:
            missing = ' and '.join(x for x in (n, d) if not pick(x))
            foil_note = f'BL{beamline} default is {n} / {d}, but no "{missing}" column - using I1 / I2'
    return {
        'energy': pick('Achieved Energy', 'Requested Energy', 'energy', 'eV') or columns[0],
        'i0': pick('I0'),
        'i1': pick('I1'),
        'foil_num': foil_num,
        'foil_den': foil_den,
        'foil_note': foil_note,
        'fluor_channels': fluor,
        'icr_channels': [c for c in columns if ICR_RE.match(c)],
    }


def _col(scan, name):
    if name not in scan['columns']:
        raise KeyError(f'Column "{name}" not in file.')
    return scan['data'][:, scan['columns'].index(name)]


def _safe_div(a, b):
    with np.errstate(divide='ignore', invalid='ignore'):
        r = a / b
    r[~np.isfinite(r)] = np.nan
    return r


def gaussian_smooth(e, y, fwhm):
    """Gaussian smoothing on a (possibly non-uniform) energy grid.
    fwhm in eV; each point becomes the Gaussian-weighted mean of its neighbours."""
    if not fwhm or fwhm <= 0:
        return y.copy()
    sigma = fwhm / 2.3548
    out = np.empty_like(y)
    for i, ei in enumerate(e):
        m = np.abs(e - ei) <= 4 * sigma
        w = np.exp(-0.5 * ((e[m] - ei) / sigma) ** 2)
        out[i] = np.sum(w * y[m]) / np.sum(w)
    return out


def calibrate(energy, num, den, element, method='ln', window=10.0,
              smooth_fwhm=1.0, spline_step=0.01):
    """Locate the foil edge (max of dmu/dE) near the tabulated foil energy.

    method 'ln'     : mu = ln(num/den)
                      1. Gaussian smoothing of mu (smooth_fwhm eV, 0 = off)
                      2. cubic spline through smoothed mu (scipy CubicSpline,
                         not-a-knot = MATLAB spline())
                      3. derivative of the spline evaluated every spline_step eV
                         (0 = off: plain finite differences on the data points)
                      4. edge = position of the derivative maximum inside ref +/- window
    method 'legacy' : exactly XAS_Worker.get_calibration (no smoothing / spline):
                      log10(num/den - min), diff(2) on energy-descending data.
    Returns dict with mu, derivative(s), edge position and shift (ref - found).
    """
    ref = FOILS.get(element)
    if ref is None:
        raise KeyError(f'No foil energy tabulated for {element}.')
    order = np.argsort(energy)
    e = energy[order]
    out = {'ok': False, 'ref': ref, 'window': window, 'method': method, 'energy': e.tolist()}

    if method == 'legacy':
        pre = _safe_div(num, den)[order]
        pre = pre - np.nanmin(pre)
        with np.errstate(divide='ignore'):
            mu = np.log10(pre)
        mu[~np.isfinite(mu)] = np.nan
        deriv = np.full_like(mu, np.nan)
        deriv[2:] = mu[2:] - mu[:-2]   # = diff(2) of the descending series
        out.update(mu=_nan2none(mu), deriv=_nan2none(deriv))
        win = (e > ref - window) & (e <= ref + window) & np.isfinite(deriv)
        if not win.any():
            out['error'] = _range_error(e, ref, window, element)
            return out
        idx = np.where(win)[0][np.argmax(deriv[win])]
        found = float(e[idx])
    else:
        with np.errstate(divide='ignore', invalid='ignore'):
            mu = np.log(_safe_div(num, den))[order]
        good = np.isfinite(mu)
        eg, mug = e[good], mu[good]
        # spline needs strictly increasing x: average duplicate energies
        eg, inv = np.unique(eg, return_inverse=True)
        mug = np.bincount(inv, weights=mug) / np.bincount(inv)
        if len(eg) < 4:
            out['error'] = 'Not enough valid foil points.'
            return out
        mu_s = gaussian_smooth(eg, mug, smooth_fwhm)
        out.update(mu=_nan2none(mu), mu_energy=eg.tolist(), mu_smooth=_nan2none(mu_s),
                   deriv_raw=_nan2none(np.gradient(mug, eg)),
                   deriv=_nan2none(np.gradient(mu_s, eg)), deriv_energy=eg.tolist())
        if not ((eg > ref - window) & (eg <= ref + window)).any():
            out['error'] = _range_error(e, ref, window, element)
            return out
        if spline_step and spline_step > 0:
            from scipy.interpolate import CubicSpline
            cs = CubicSpline(eg, mu_s)          # bc_type='not-a-knot' like MATLAB spline
            lo, hi = max(ref - window, eg[0]), min(ref + window, eg[-1])
            ef = np.arange(lo, hi + spline_step / 2, spline_step)
            df = cs(ef, 1)
            found = round(float(ef[np.argmax(df)]), 6)
            # spline curve for plotting (a little wider than the search window)
            pl = np.arange(max(ref - 1.5 * window, eg[0]), min(ref + 1.5 * window, eg[-1]), spline_step)
            out.update(spline_energy=pl.tolist(), spline_deriv=cs(pl, 1).tolist(),
                       spline_mu=cs(pl).tolist(), found_deriv=float(cs(found, 1)))
        else:
            d = np.gradient(mu_s, eg)
            win = (eg > ref - window) & (eg <= ref + window)
            idx = np.where(win)[0][np.argmax(d[win])]
            found = float(eg[idx])
            out['found_deriv'] = float(d[idx])
        if abs(found - ref) >= window - 2 * max(spline_step or 0, 0.01):
            out['warning'] = ('Derivative maximum sits at the edge of the search window - '
                              'check element / foil channels.')

    out.update(ok=True, found=found, shift=ref - found)
    return out


def _range_error(e, ref, window, element):
    return (f'No foil data within ±{window} eV of the {element} edge ({ref} eV). '
            f'Scan covers {e.min():.1f}–{e.max():.1f} eV.')


def _nan2none(a):
    return [None if not np.isfinite(x) else float(x) for x in np.asarray(a, dtype=float)]


def detector_of(col):
    m = GROUP_RE.match(col)
    return m.group(1) if m else col


def score_detector(energy, summed_ratio, ref):
    """Edge-jump signal-to-noise of a detector's summed fluorescence / I0.

    jump  = mean(post-edge, ref+30..ref+100 eV) - mean(pre-edge, ref-80..ref-15 eV)
    noise = point-to-point scatter in the pre-edge, std(diff)/sqrt(2)
    snr   = jump / noise
    Falls back to the mean ratio if the scan does not cover both regions."""
    y = np.asarray(summed_ratio, dtype=float)
    out = {'mean_ratio': float(np.nanmean(y)) if np.isfinite(y).any() else None,
           'jump': None, 'noise': None, 'snr': None}
    if ref is None:
        return out
    pre = (energy >= ref - 80) & (energy <= ref - 15) & np.isfinite(y)
    post = (energy >= ref + 30) & (energy <= ref + 100) & np.isfinite(y)
    if pre.sum() >= 4 and post.sum() >= 3:
        order = np.argsort(energy[pre])
        jump = float(np.mean(y[post]) - np.mean(y[pre]))
        noise = float(np.std(np.diff(y[pre][order])) / np.sqrt(2))
        out.update(jump=jump, noise=noise, snr=jump / noise if noise > 0 else None)
    return out


def process(scan, cfg):
    """Workup of one scan (equivalent of XAS_Worker.workup_data, without the PDF).

    cfg keys: energy, i0, i1, fluor_channels, manual_drops, auto_drop_threshold,
              calibrate, element, foil_num, foil_den, foil_method,
              cal_window, smooth_fwhm, spline_step,
              detector ('auto' = best by edge-jump S/N, 'all', or a detector name e.g. 'SCA2')
    Files already processed by this app are returned as stored (cfg is ignored).
    """
    if scan['meta'].get('kind'):
        return result_from_processed(scan)
    energy = _col(scan, cfg['energy'])
    i0 = _col(scan, cfg['i0'])
    i1 = _col(scan, cfg['i1']) if cfg.get('i1') else None

    fluor = [c for c in cfg.get('fluor_channels', []) if c in scan['columns']]
    manual = set(cfg.get('manual_drops', []))
    thr = int(cfg.get('auto_drop_threshold', 5))

    channels, auto_dropped, kept = {}, [], []
    for c in fluor:
        v = _col(scan, c)
        nzero = int((v == 0.0).sum())
        if c in manual:
            status = 'manual'
        elif thr > 0 and nzero >= thr:
            status = 'auto'
            auto_dropped.append(c)
        else:
            status = 'kept'
            kept.append(c)
        channels[c] = {'name': c, 'status': status, 'zeros': nzero, 'detector': detector_of(c),
                       'ratio': _nan2none(_safe_div(v, i0))}

    # ---- detector selection: only one of SCA1 / SCA2 / ... carries the signal
    groups = {}
    for c in fluor:
        groups.setdefault(detector_of(c), []).append(c)
    ref = FOILS.get(cfg.get('element'))
    detectors = []
    for g, chs in groups.items():
        gk = [c for c in chs if c in kept]
        info = {'name': g, 'n_channels': len(chs), 'n_kept': len(gk)}
        if gk:
            ssum = scan['data'][:, [scan['columns'].index(c) for c in gk]].sum(axis=1)
            info.update(score_detector(energy, _safe_div(ssum, i0), ref))
        else:
            info.update(mean_ratio=None, jump=None, noise=None, snr=None)
        detectors.append(info)

    want = cfg.get('detector', 'auto')
    if len(groups) <= 1 or want == 'all':
        selected = list(groups)
    elif want in groups:
        selected = [want]
    else:   # auto: highest S/N, else highest mean ratio
        key = lambda d: (d['snr'] if d['snr'] is not None else -np.inf,
                         d['mean_ratio'] if d['mean_ratio'] is not None else -np.inf)
        selected = [max(detectors, key=key)['name']]
    for d in detectors:
        d['selected'] = d['name'] in selected
    for c, info in channels.items():
        if info['detector'] not in selected:
            info['status'] = 'off'
    kept = [c for c in kept if channels[c]['status'] == 'kept']
    auto_dropped = [c for c in auto_dropped if channels[c]['status'] == 'auto']

    if kept:
        summed = scan['data'][:, [scan['columns'].index(c) for c in kept]].sum(axis=1)
        sumratio = _safe_div(summed, i0)
    else:
        sumratio = np.full_like(energy, np.nan)

    cal = None
    shift = 0.0
    if cfg.get('calibrate') and cfg.get('foil_num') and cfg.get('foil_den'):
        cal = calibrate(energy, _col(scan, cfg['foil_num']), _col(scan, cfg['foil_den']),
                        cfg.get('element', 'Fe'), cfg.get('foil_method', 'ln'),
                        window=float(cfg.get('cal_window', 10.0)),
                        smooth_fwhm=float(cfg.get('smooth_fwhm', 1.0)),
                        spline_step=float(cfg.get('spline_step', 0.01)))
        if cal['ok']:
            shift = cal['shift']
    e_cal = energy + shift

    trans = None
    if i1 is not None:
        with np.errstate(divide='ignore', invalid='ignore'):
            trans = np.log(_safe_div(i0, i1))

    def stats(a):
        a = np.asarray(a, dtype=float)
        return {'mean': float(np.nanmean(a)), 'min': float(np.nanmin(a)),
                'max': float(np.nanmax(a))} if np.isfinite(a).any() else None

    return {
        'energy_raw': energy.tolist(),
        'energy': e_cal.tolist(),
        'shift': shift,
        'channels': channels,
        'kept': kept,
        'auto_dropped': auto_dropped,
        'manual_dropped': sorted(c for c in manual & set(fluor) if channels[c]['status'] == 'manual'),
        'detectors': detectors,
        'detector_mode': want,
        'sumratio': _nan2none(sumratio),
        'sumcounts': _nan2none(summed) if kept else None,
        'i1': _nan2none(i1) if i1 is not None else None,
        'transmission': _nan2none(trans) if trans is not None else None,
        'i0': _nan2none(i0),
        'calibration': cal,
        'stats': {'sumratio': stats(sumratio), 'i0': stats(i0),
                  'i1': stats(i1) if i1 is not None else None,
                  'energy_min': float(e_cal.min()), 'energy_max': float(e_cal.max()),
                  'calibration_shift': shift},
    }


# --------------------------------------------------------------------------- export
def output_basename(filename):
    """XAS_Worker naming: 'name_A.001' -> 'name_A001'."""
    import os
    base = os.path.basename(filename)
    stem, dot, ext = base.rpartition('.')
    return (stem + ext) if dot else base


def export_text(scan, cfg, res, app_version='EXAFS Data Reduction (Flask)'):
    """Processed scan as text: '#' header with provenance, then whitespace columns."""
    import datetime
    m = scan['meta']
    cal = res.get('calibration')
    ch = res['channels']
    sel = [d['name'] for d in res['detectors'] if d['selected']]
    off = [c for c, v in ch.items() if v['status'] == 'off']
    f = lambda v, n=6: 'n/a' if v is None else f'{v:.{n}g}'

    H = [f'{app_version} - processed XAS scan',
         f'created: {datetime.datetime.now().isoformat(timespec="seconds")}',
         '',
         '[source]',
         f'file: {m.get("filename")}',
         f'format: {m.get("format")}',
         f'collected: {m.get("date", "n/a")}',
         f'beamline: {("BL" + m["beamline_guess"]) if m.get("beamline_guess") else "n/a"}'
         f'   ({m.get("beamline_line", "")})',
         f'detector_file: {m.get("detector_file", "n/a")}',
         f'region_file: {m.get("region_file", "n/a")}',
         f'scan_params: {m.get("scan_params", "n/a")}',
         f'points: {m.get("rows_read")}']
    for c in m.get('comments', []):
        H.append(f'comment: {c}')

    H += ['', '[channels]',
          f'energy_column: {cfg["energy"]}',
          f'I0: {cfg["i0"]}',
          f'I1: {cfg.get("i1") or "none"}',
          f'detector_mode: {res["detector_mode"]}',
          f'detector_used: {" + ".join(sel) or "none"}']
    for d in res['detectors']:
        H.append(f'detector {d["name"]}: used {d["n_kept"]}/{d["n_channels"]} channels, '
                 f'edge_jump={f(d["jump"])}, noise={f(d["noise"])}, S/N={f(d["snr"], 4)}'
                 f'{"  <- selected" if d["selected"] else ""}')
    H += [f'channels_used ({len(res["kept"])}): {" ".join(res["kept"]) or "none"}',
          f'auto_dropped (>= {cfg.get("auto_drop_threshold")} zero points) ({len(res["auto_dropped"])}): '
          f'{" ".join(res["auto_dropped"]) or "none"}',
          f'manual_dropped ({len(res["manual_dropped"])}): {" ".join(res["manual_dropped"]) or "none"}',
          f'other_detector_off ({len(off)}): {" ".join(off) or "none"}']

    H += ['', '[energy calibration]']
    if not cal:
        H.append('calibrated: no (energy not shifted)')
    else:
        H += [f'calibrated: {"yes" if cal["ok"] else "FAILED - energy not shifted"}',
              f'element: {cfg.get("element")}',
              f'reference_energy_eV: {cal["ref"]}',
              f'foil: {"ln" if cal["method"] == "ln" else "legacy log10"}({cfg.get("foil_num")}/{cfg.get("foil_den")})',
              f'method: {cal["method"]}',
              f'smoothing_fwhm_eV: {cfg.get("smooth_fwhm") if cal["method"] == "ln" else "n/a"}',
              f'spline_step_eV: {cfg.get("spline_step") if cal["method"] == "ln" else "n/a"}',
              f'search_window_eV: +/-{cal["window"]}']
        if cal['ok']:
            H += [f'edge_found_eV: {cal["found"]:.4f}',
                  f'energy_shift_eV: {cal["shift"]:+.4f}   (calibrated = raw + shift)']
        else:
            H.append(f'error: {cal.get("error")}')

    st = res['stats']
    H += ['', '[statistics]']
    for k in ('sumratio', 'i0', 'i1'):
        if st.get(k):
            H.append(f'{k}: mean={f(st[k]["mean"])} min={f(st[k]["min"])} max={f(st[k]["max"])}')
    H.append(f'energy_range_eV: {st["energy_min"]:.3f} - {st["energy_max"]:.3f}')

    cols = ['Energy_cal', 'Energy_raw', 'SumRatio', 'I0']
    arrs = [res['energy'], res['energy_raw'], res['sumratio'], res['i0']]
    if res.get('transmission') is not None:
        cols.append('ln(I0/I1)'); arrs.append(res['transmission'])
    H += ['', '[data]',
          'SumRatio = sum(channels_used) / I0;  Energy_cal = Energy_raw + energy_shift_eV',
          '   '.join(cols)]

    order = np.argsort(res['energy'])
    lines = ['# ' + h if h else '#' for h in H]
    for i in order:
        lines.append('  '.join('nan' if a[i] is None else f'{a[i]:.6f}' if j < 2 else f'{a[i]:.8g}'
                               for j, a in enumerate(arrs)))
    return '\n'.join(lines) + '\n'


# --------------------------------------------------------------------------- merging
def merge(items, mode='first'):
    """Combine several processed scans by ADDING channels (no scaling).

    For every energy point:
        merged = sum over scans of sum(channels_used counts)  /  sum over scans of I0
        transmission = ln(sum I0 / sum I1)
    i.e. all good channels of all scans are treated as one big detector, so each scan
    contributes in proportion to its counts.

    items: list of (scan, cfg, res) - each scan already processed with its own settings
           (channels, detector, drops, calibration).
    mode 'first'     : interpolate every scan onto the calibrated energy grid of the first
                       scan. No extrapolation: a scan only contributes inside its own range.
    mode 'pointwise' : combine point by point, energy = mean of the calibrated energies;
                       all scans must have the same number of points.
    """
    if len(items) < 2:
        raise ValueError('Check at least two files to merge.')
    for s, _, r in items:
        if r.get('sumcounts') is None:
            raise ValueError(f'{s["meta"]["filename"]}: no fluorescence channels in use.')
    has_t = all(r.get('i1') is not None for _, _, r in items)
    keys = ['sumcounts', 'i0', 'sumratio'] + (['i1'] if has_t else [])

    def arr(r, k):
        return np.array([np.nan if v is None else v for v in r[k]], dtype=float)

    cols = {k: [] for k in keys}
    if mode == 'pointwise':
        n = {len(r['energy']) for _, _, r in items}
        if len(n) != 1:
            raise ValueError(f'Point-by-point merging needs equal scan lengths, got {sorted(n)} points. '
                             'Use "interpolate to first scan".')
        E = []
        for _, _, r in items:
            o = np.argsort(r['energy'])
            E.append(np.asarray(r['energy'])[o])
            for k in keys:
                cols[k].append(arr(r, k)[o])
        grid = np.mean(E, axis=0)
    else:
        grid = np.sort(np.asarray(items[0][2]['energy'], dtype=float))
        for _, _, r in items:
            e = np.asarray(r['energy'], dtype=float); o = np.argsort(e); e = e[o]
            for k in keys:
                y = arr(r, k)[o]; ok = np.isfinite(y)
                cols[k].append(np.interp(grid, e[ok], y[ok], left=np.nan, right=np.nan))
    st = {k: np.vstack(v) for k, v in cols.items()}

    # a point only counts for a scan if both its counts and its I0 exist there
    valid = np.isfinite(st['sumcounts']) & np.isfinite(st['i0'])
    if has_t:
        valid_t = valid & np.isfinite(st['i1'])
    tot_counts = np.where(valid, st['sumcounts'], 0).sum(0)
    tot_i0 = np.where(valid, st['i0'], 0).sum(0)
    nscan = valid.sum(0)
    merged = _safe_div(tot_counts, tot_i0)
    merged[nscan == 0] = np.nan
    trans = None
    if has_t:
        ti0 = np.where(valid_t, st['i0'], 0).sum(0); ti1 = np.where(valid_t, st['i1'], 0).sum(0)
        with np.errstate(divide='ignore', invalid='ignore'):
            trans = np.log(_safe_div(ti0, ti1))
        trans[valid_t.sum(0) == 0] = np.nan

    scans = []
    for (s, cfg, r), y in zip(items, st['sumratio']):
        cal = r.get('calibration')
        scans.append({'file': s['meta']['filename'], 'kind': s['meta'].get('kind', 'raw'),
                      'detector': ' + '.join(d['name'] for d in r['detectors'] if d['selected']) or 'none',
                      'n_channels': len(r['kept']),
                      'dropped': r['auto_dropped'] + r['manual_dropped'],
                      'shift': r['shift'],
                      'calibrated': bool(cal and cal['ok']),
                      'element': cfg.get('element'),
                      'total_counts': float(np.nansum(arr(r, 'sumcounts'))),
                      'sumratio': _nan2none(y)})
    tot = sum(sc['total_counts'] for sc in scans)
    for sc in scans:
        sc['count_fraction'] = sc['total_counts'] / tot if tot else None
    return {'mode': mode, 'energy': grid.tolist(), 'n_scans': len(items),
            'n_per_point': nscan.tolist(),
            'sumratio': _nan2none(merged),
            'sumcounts': _nan2none(np.where(nscan > 0, tot_counts, np.nan)),
            'i0': _nan2none(np.where(nscan > 0, tot_i0, np.nan)),
            'transmission': _nan2none(trans) if has_t else None,
            'scans': scans}


def merged_basename(filenames):
    import os
    stems = [output_basename(f) for f in filenames]
    p = os.path.commonprefix(stems).rstrip('_-. ')
    return p or 'merged'


def export_merged_text(items, m, app_version='EXAFS Data Reduction (Flask)'):
    import datetime
    f = lambda v, n=6: 'n/a' if v is None else f'{v:.{n}g}'
    cfg0 = items[0][1]
    H = [f'{app_version} - merged XAS data ({m["n_scans"]} scans, channels added)',
         f'created: {datetime.datetime.now().isoformat(timespec="seconds")}',
         f'merge_mode: {"interpolated onto calibrated energy grid of first scan" if m["mode"] == "first" else "point-by-point average, energy = mean of calibrated energies"}',
         'combination: channels added - merged = sum over scans of sum(channels_used) / sum over scans of I0 (no scaling)',
         '', '[scans merged]']
    for i, sc in enumerate(m['scans'], 1):
        H.append(f'{i:2d}. {sc["file"]}  [{sc["kind"]}]  detector={sc["detector"]}  channels_used={sc["n_channels"] or "n/a"}  '
                 f'shift_eV={sc["shift"]:+.4f}{"" if sc["calibrated"] else " (NOT calibrated)"}  '
                 f'counts_fraction={sc["count_fraction"]:.3f}  '
                 f'dropped={" ".join(sc["dropped"]) or "none"}')
    H += ['', '[per-scan details]']
    for (s, cfg, r) in items:
        H.append(f'--- {s["meta"]["filename"]}')
        if s['meta'].get('kind'):
            H.append(f'    (opened as {s["meta"]["kind"]} file; its original header follows)')
            H += ['    | ' + h for h in s['meta']['original_header'] if h.strip()]
            continue
        for c in s['meta'].get('comments', []):
            H.append(f'    comment: {c}')
        H.append(f'    collected: {s["meta"].get("date", "n/a")}   beamline: '
                 f'{("BL" + s["meta"]["beamline_guess"]) if s["meta"].get("beamline_guess") else "n/a"}')
        H.append(f'    I0={cfg["i0"]}  I1={cfg.get("i1")}  energy={cfg["energy"]}')
        H.append(f'    channels_used ({len(r["kept"])}): {" ".join(r["kept"])}')
        cal = r.get('calibration')
        if cal and cal['ok']:
            H.append(f'    calibration: {cfg.get("element")} ref={cal["ref"]} eV, foil={cal["method"]}'
                     f'({cfg.get("foil_num")}/{cfg.get("foil_den")}), smooth={cfg.get("smooth_fwhm")} eV, '
                     f'spline_step={cfg.get("spline_step")} eV, found={cal["found"]:.4f} eV, shift={cal["shift"]:+.4f} eV')
        else:
            H.append('    calibration: none / failed (energy not shifted)')
    shifts = [sc['shift'] for sc in m['scans']]
    H += ['', '[summary]',
          f'calibration_shift_eV: mean={np.mean(shifts):+.4f}  min={min(shifts):+.4f}  max={max(shifts):+.4f}',
          f'energy_range_eV: {m["energy"][0]:.3f} - {m["energy"][-1]:.3f}  ({len(m["energy"])} points)']
    cols = ['Energy', 'SumRatio', 'Sum_counts', 'Sum_I0', 'N_scans']
    arrs = [m['energy'], m['sumratio'], m['sumcounts'], m['i0'], m['n_per_point']]
    if m.get('transmission') is not None:
        cols.append('ln(sumI0/sumI1)'); arrs.append(m['transmission'])
    H += ['', '[data]', 'SumRatio = Sum_counts / Sum_I0; Sum_counts = sum over scans of sum(channels_used); '
          'Sum_I0 = sum over scans of I0; N_scans = scans contributing to that point',
          '   '.join(cols)]
    lines = ['# ' + h if h else '#' for h in H]
    for i in range(len(m['energy'])):
        row = []
        for j, a in enumerate(arrs):
            v = a[i]
            row.append('nan' if v is None else f'{v:.6f}' if j == 0 else str(int(v)) if j == 4 else f'{v:.8g}')
        lines.append('  '.join(row))
    return '\n'.join(lines) + '\n'
