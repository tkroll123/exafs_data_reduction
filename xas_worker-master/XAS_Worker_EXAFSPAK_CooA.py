# Example Usage:
#os.chdir(r'to/your/path/of/data')
import os
from XAS_Worker import XAS_Worker
from matplotlib import pyplot as plt
#os.chdir(os.path.join('Examples','EXAFPAKWorkup'))
os.chdir('/Users/jeet2811/documents/data/SSRL/XAS-XES/BL9_3/DataReduction')
file='Ferrous_ChCooA_pyspline.dat'
worker = XAS_Worker(beamline='9-3', manual_drops=['FF1'])
worker.convert_pyspline(file)
#7725 eV is the threshold energy for cobalt.
worker.write_exafspak_keystroke(7129,'process_out.txt')
#At this point you can run exafspak manually as: /path/to/exafspak/process /RECOVER=PROCESS.LOG /LOG=TEST.LOG
#if the process executeable is in your path you can run it directly from python
worker.run_exafspak_process()
