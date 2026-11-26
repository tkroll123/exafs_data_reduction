# Example Usage:
#os.chdir(r'to/your/path/of/data')
import os
from XAS_Worker import XAS_Worker
from matplotlib import pyplot as plt
os.chdir(os.path.join('/Users/jeet2811/documents/data/SSRL/XAS-XES/BL9_3','ImportPyspline'))
file='CoIIIoximeS2_s1_130_A_Processed_Full_Data_Pysplined.dat'
worker = XAS_Worker(beamline='7-3', manual_drops=['FF1'])
Co_III=worker.import_pyspline(file)
fig, axs =plt.subplots(2,1,dpi=100)

axs[0].plot(Co_III.eV,Co_III.Flattened)
axs[0].set_title('Flattened XAS Spectrum')
axs[0].set_xlabel('Energy (eV)')

axs[1].plot(Co_III.K,Co_III.EXAFS)
axs[1].set_title('EXAFS Spectrum')
axs[1].set_xlabel('K ($\mathrm{\AA^{-1}}$)')
axs[1].set_ylabel('K$^{3}$$\chi$(k)($\mathrm{\AA^{-3}}$)')


plt.tight_layout()
plt.show()