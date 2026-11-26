# Example Usage:
#os.chdir(r'to/your/path/of/data')
import os
from XAS_Worker import XAS_Worker
os.chdir(os.path.join('Users','jeet2811','documents','data','SSRL','XAS-XES','BL9_3','DataReduction'))
#os.chdir('/Users/jeet2811/documents/data/SSRL/XAS-XES/BL9_3/DataReduction','DataReduction')
worker = XAS_Worker(beamline='9-3', manual_drops=['FF1'])
#Here if you want to pick files with a regular expression.
#worker.set_files_to_process('*.00[0-9]')
#Here you can use a modal window to select the files to analyze
worker.select_files_to_process()
#
worker.element='Fe'#used to set the Foil
worker.set_manual_drops_per_file({0: ['FF2']})  # Set manual drops for the first file
worker.aggregate_data(interpolate_to_first_scan=False)
worker.output_log()
