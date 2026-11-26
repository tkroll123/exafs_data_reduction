import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import json
import os
import glob
import tkinter as tk
from tkinter import filedialog
from warnings import simplefilter

simplefilter(action="ignore", category=pd.errors.PerformanceWarning)


class XAS_Worker:
    def __init__(self, beamline, manual_drops=[]):
        """
        Initialize an instance of XAS_Worker.

        Parameters:
        - beamline (str): The beamline identifier at SSRL: 7-3 or 9-3.
        - manual_drops (list): List of channels to be manually dropped during data processing.
        """
        self.beamline = beamline
        self.manual_drops = manual_drops
        self.BL = beamline
        self.endColumn = {'7-3': 70, '9-3': 212}
        self.indexColumn = {'7-3': 3, '9-3': 1}
        self.column = {'7-3': 3, '9-3': 1}
        self.files_to_process = []
        self.manual_drops = manual_drops
        self.manual_drops_per_file = {}
        self.element = 'Fe'
        self.foil_channels = ['I2', 'I0']
        self.foils = {'Sc': 4492.8,
                      'Ti': 4966.4,
                      'V': 5465.1,
                      'Cr': 5989.2,
                      'Mn': 6539.0,
                      'Fe': 7111.2,
                      'Co': 7708.9,
                      'Ni': 8332.8,
                      'Cu': 8978.9,
                      'Zn': 9658.6
                      }
        self.aggregation_info = {}

    def select_files_to_process(self):
        root = tk.Tk()
        root.withdraw()
        file_paths = list(filedialog.askopenfilenames())
        self.files_to_process = file_paths

    def set_files_to_process(self, file_pattern):
        """
        Set the files to be processed based on a file pattern.

        Parameters:
        - file_pattern (str): The file pattern to match files.
        """
        self.files_to_process = glob.glob(file_pattern)
        self.manual_drops_per_file = {i: self.manual_drops.copy() for i in range(len(self.files_to_process))}

    def set_manual_drops_per_file(self, modifications):
        """
        Set manual channel drops for a specific file.

        Parameters:
        - file_index (int): Index of the file to set drops for.
        - drops (list): List of channels to be manually dropped for the specified file.
        """
        for file_index, drops in modifications.items():
            if 0 <= file_index < len(self.files_to_process):
                self.manual_drops_per_file[file_index] = drops
            else:
                print(f"Invalid file index: {file_index}")

    def get_foil_energy(self, element):
        """
        Get the energy of the foil for a given element.

        Parameters:
        - element (str): The chemical element.

        Returns:
        - float: The energy of the foil for the specified element.
        """
        foils = {'Sc': 4492.8, 'Ti': 4966.4, 'V': 5465.1, 'Cr': 5989.2, 'Mn': 6539.0,
                 'Fe': 7111.2, 'Co': 7708.9, 'Ni': 8332.8, 'Cu': 8978.9, 'Zn': 9658.6}
        # Check if the element is in the dictionary
        if element in foils:
            return foils[element]
        else:
            print(f'Error: Element {element} not found in dictionary.')
            return None

    def get_column_names(self, filename):
        """
        Get column names from a data file. Converts SCA1 (BL7-3) to FF (BL9-3) to simplify analysis.

        Parameters:
        - filename (str): Path to the data file.

        Returns:
        - list: List of column names.
        """
        with open(filename, 'r') as file:
            lines = file.readlines()

        # Find the "Data:" line and determine the column names
        inside_data_section = False
        column_names = []
        for i, line in enumerate(lines):
            if line.strip() == "Data:":
                inside_data_section = True
                continue  # Skip the "Data:" line itself

            if inside_data_section:
                if not line.strip():
                    break  # End of column names section
                column_names.append(line.strip())

        # Update self.endColumn for the specific beamline
        self.endColumn[self.beamline] = len(column_names)

        # Replace SCA1_ with FF for specific beamlines
        if self.beamline == '7-3' or self.beamline == '9-3':
            column_names = [w.replace('SCA1_', 'FF') for w in column_names]

        return column_names

    def get_data(self, filename):
        """
        Read and process data from a file.

        Parameters:
        - filename (str): Path to the data file.

        Returns:
        - pandas.DataFrame: Processed data.
        """
        name_list = self.get_column_names(filename)
        out_data = pd.read_csv(filename, delimiter=r'\s+', encoding='iso-8859-1', header=None, names=name_list,
                               skiprows=self.endColumn[self.beamline] + 21, index_col=False, skip_blank_lines=True,
                               skipinitialspace=True)
        out_data = out_data.set_index('Achieved Energy')
        out_data = out_data.drop(labels='', axis=1, errors='ignore')
        return out_data

    def import_pyspline(self, file):
        """
        Import data from a file using the PySpline format.

        Parameters:
        - file (str): Path to the PySpline format file.

        Returns:
        - pandas.DataFrame: Imported data.
        """
        p_spline = pd.read_csv(file, skiprows=6, delimiter=',', names=['eV', 'K', 'I0', 'RAW', 'Background', 'Normal',
                                                                       'Spline', 'EXAFS'])
        return p_spline

    def flattenPyspline(self, pyspline):

        pyspline['Flattened'] = np.where(pyspline['K'] == 0, pyspline['Normal'],
                                         pyspline['Normal'] / pyspline['Spline'])

        return pyspline

    def convert_pyspline(self, file):
        """
        Convert PySpline data to the format required by exafspak.

        Parameters:
        - file (str): Path to the PySpline format file.

        Returns:
        - pandas.DataFrame: Converted data.
        """
        output = self.import_pyspline(file)
        output = output[(output['K'] != 0)]
        output['EXAFS'] = output['EXAFS'] / output['K'] ** 3
        output.to_csv('forEXAFSPAK.txt', header=False, index=False)
        return output

    def write_exafspak_keystroke(self, E0, out_file):
        """
        Write EXAFSPAK keystroke file.

        Parameters:
        - in_file (str): Input file path.
        - E0 (float): Energy value.
        - out_file (str): Output file path.
        """
        text_file = f'\n\n6\n4\n1\nforEXAFSPAK.txt\n8\n \n \n \n \n \n \n9\n7\n0\n\n\n1\n{E0}\n1\n5\n4\n1\n\n\n\n\n\n\n\n\n\n\n1\n1\n \n \n \n\n\n \n \n\n \n\n\n\n\n\n\n\n\n\n\n\n5\n6\n1\n{out_file}.ave\n5\n9\n \n '
        with open('PROCESS.LOG', 'w') as f:
            f.write(text_file)

    def run_exafspak_process(self):
        """
        Run the EXAFSPAK process using the written keystroke file.
        """
        from subprocess import call
        call(["process", "/RECOVER=PROCESS.LOG", "/LOG=TEST.LOG"])

    def convert_pyspline_for_artemis(self, file):
        """
        Convert PySpline data for Artemis.

        Parameters:
        - file (str): Path to the PySpline format file.

        Returns:
        - pandas.DataFrame: Converted data for Artemis.
        """
        output = self.import_pyspline(file)
        output = output[(output['K'] != 0)]
        output['EXAFS'] = output['EXAFS'] / output['K'] ** 3
        output = output.drop(['eV', 'I0', 'RAW', 'Background', 'Normal', 'Spline'], axis=1)
        output.to_csv('forArtemis.txt', header=False, index=False)
        return output

    def process_pyspline(self, pyspline_file, threshold=7130, run=True):
        """
        Process PySpline data.

        Parameters:
        - pyspline_file (str): Path to the PySpline format file.
        - run (bool): If True, run the EXAFSPAK process after processing.
        """
        self.convert_pyspline(pyspline_file)

        self.write_exafspak_keystroke(threshold, 'out.txt')
        if run:
            self.run_exafspak_process()

    def auto_bad_channels(self, data, threshold, manual_drops=[]):
        """
        Automatically identify and drop channels with low intensity.

        Parameters:
        - data (pandas.DataFrame): Input data.
        - threshold (int): Intensity threshold for dropping channels.
        - manual_drops (list): List of channels to be manually dropped.

        Returns:
        - tuple: Tuple containing processed data and list of dropped channels.
        """
        if manual_drops != []:
            data.drop(labels=manual_drops, axis=1, inplace=True)
        droppers = data.filter(regex='FF*').columns[(data.filter(regex='FF*') == 0.0).sum() >= threshold].tolist()
        data.drop(labels=droppers, axis=1, inplace=True)
        droppers.extend(manual_drops)
        return data, droppers

    def get_calibration(self, data, element='Fe'):
        """
        Get calibration value from foil, identify shift for data by first inflection, plot resulting foil spectrum.

        Parameters:
        - data (pandas.DataFrame): Input data.
        - element (str): Chemical element for calibration.

        Returns:
        - list: List containing calibration plot and calibration shift.
        """
        element = self.element
        cal_val = self.get_foil_energy(element)
        data['prefoil'] = (data['I2'] / data['I0'])
        data['prefoil'] = data['prefoil'] - np.min(data['prefoil'])
        data['foil'] = data['prefoil'].apply(np.log10)

        v = data[(data.index > cal_val - 10) & (data.index <= cal_val + 10)]['foil'].sort_index(ascending=False).diff(2)

        if len(v) == 0:
            raise Exception(
                f'The foil is currently set to {self.element} but the measured data is not close to this foil energy.')
        ax = plt.figure(figsize=(8.5, 11))
        plt.suptitle("Calibration")

        ax.add_subplot(1, 2, 1)
        v.plot()
        m = v.idxmax()
        plt.xlim(cal_val - 10, cal_val + 10)
        plt.axvline(x=m, color='k', linestyle='--')

        ax.add_subplot(1, 2, 2)
        v[(v.index > cal_val - 4) & (v.index < cal_val + 4)].plot()
        plt.axvline(x=m, color='k', linestyle='--')

        cur_axes = plt.gca()
        cur_axes.ticklabel_format(style='plain')
        cur_axes.get_xaxis().get_major_formatter().set_useOffset(False)
        cur_axes.yaxis.set_tick_params(labelright='on', labelleft='off')
        cur_axes.invert_xaxis()

        plt.annotate(f'Calibration Energy Value {m}\nData Shifted by: {cal_val - m}', (0, 0), (0, -50),
                     xycoords='axes fraction', textcoords='offset points', va='top')

        return [ax, cal_val - m]

    def workup_data(self, file_name, manual_drops=None):
        """
        Process and analyze data from a file: drop bad channels, calibrate energy, normalize by I0, calculate statistics.

        Parameters:
        - file_name (str): Path to the data file.
        - manual_drops (list, optional): List of channels to be manually dropped for this file.

        Returns:
        - tuple: Tuple containing processed data (SumRatio, I0, I1).
        """
        if manual_drops is None:
            manual_drops = self.manual_drops

        XAS_df = self.get_data(file_name)
        [XAS_df, bad] = self.auto_bad_channels(XAS_df, 5, manual_drops)
        XAS_df['SumRatio'] = XAS_df.filter(regex='FF*', axis=1).sum(axis=1) / XAS_df['I0']
        plot_me = XAS_df.filter(regex='FF*').div(XAS_df['I0'], axis=0)
        p = 0
        [cal_fig, cal_val] = self.get_calibration(XAS_df)
        XAS_df.index = XAS_df.index + cal_val
        # Capture and store statistical information for logging
        mean_intensity = XAS_df['SumRatio'].mean()
        min_intensity = XAS_df['SumRatio'].min()
        max_intensity = XAS_df['SumRatio'].max()
        mean_i0 = XAS_df['I0'].mean()
        min_i0 = XAS_df['I0'].min()
        max_i0 = XAS_df['I0'].max()
        mean_i1 = XAS_df['I1'].mean()
        min_i1 = XAS_df['I1'].min()
        max_i1 = XAS_df['I1'].max()
        min_energy = XAS_df.index.min()
        max_energy = XAS_df.index.max()

        # Create a dictionary to store the statistical information
        statistical_info = {
            'mean_intensity': mean_intensity,
            'min_intensity': min_intensity,
            'max_intensity': max_intensity,
            'mean_i0': mean_i0,
            'min_i0': min_i0,
            'max_i0': max_i0,
            'mean_i1': mean_i1,
            'min_i1': min_i1,
            'max_i1': max_i1,
            'calibration_shift': cal_val,
            'min_energy': min_energy,
            'max_energy': max_energy
        }

        self.aggregation_info[file_name] = statistical_info

        z = 1
        max_subplots = (len(plot_me.columns) // 5) + ((len(plot_me.columns) % 5 > 0))
        channel_fig = plt.figure(figsize=(8.0, max_subplots * 3))
        ax1 = channel_fig.add_subplot(max_subplots, 1, z)
        for i in plot_me.columns:
            plot_me[i].plot()
            p = p + 1
            if p % 5 == 0 and p != len(plot_me.columns):
                cur_axes = plt.gca()
                cur_axes.axes.get_yaxis().set_ticklabels([])
                cur_axes.axes.get_yaxis().set_ticks([])
                plt.legend(loc=2, fontsize='large', ncol=2, frameon=False)
                if z != max_subplots:
                    z = z + 1
                channel_fig.add_subplot(max_subplots, 1, z, sharex=ax1)
            if p == len(plot_me.columns):
                cur_axes = plt.gca()
                cur_axes.axes.get_yaxis().set_ticklabels([])
                cur_axes.axes.get_yaxis().set_ticks([])
                plt.legend(loc=2, fontsize='large', ncol=2, frameon=False)
        plt.tight_layout()
        sum_fig = plt.figure(figsize=(8.0, 10))
        plt.title("Calibrated Summed Ratio")
        XAS_df['SumRatio'].plot()
        plt.annotate('Channels Removed:\n' + str(bad), (0, 0), (0, -50), xycoords='axes fraction',
                     textcoords='offset points', va='top')
        file_name = os.path.basename(file_name).split('.')[0] + os.path.basename(file_name).split('.')[1]
        with PdfPages(file_name + '_Processed.pdf') as pdf:
            cal_fig.suptitle(file_name + ' Calibration', fontsize=12)
            pdf.savefig(cal_fig, )
            channel_fig.suptitle(file_name + ' Channel Check', fontsize=12)
            pdf.savefig(channel_fig, )
            sum_fig.suptitle(file_name + ' Summed Calibrated Data', fontsize=12)
            pdf.savefig(sum_fig)
            plt.close(cal_fig)
            plt.close(channel_fig)
            plt.close(sum_fig)
        return XAS_df['SumRatio'], XAS_df['I0'], XAS_df['I1']

    def aggregate_data(self, interpolate_to_first_scan=False):
        """
        Aggregate processed data from multiple files.

        Parameters:
        - interpolate_to_first_scan (bool): If True, interpolate data to the x-axis of the first scan.
        """
        if not self.files_to_process:
            print("No files to process. Use set_files_to_process method to specify files.")
            return

        final_df = None

        for i, file in enumerate(self.files_to_process):
            print(file)

            file_manual_drops = self.manual_drops_per_file.get(i, self.manual_drops)

            summed_scan, i0_tot, i1_tot = self.workup_data(file, manual_drops=file_manual_drops)

            # Interpolate to the x-axis of the first scan if specified
            if interpolate_to_first_scan and final_df is not None and len(final_df) > 0:
                summed_scan = summed_scan.reindex(final_df_energy)
                summed_scan.interpolate(inplace=True)
                i0_tot = i0_tot.reindex(final_df_energy)
                i0_tot.interpolate(inplace=True)
                i1_tot = i1_tot.reindex(final_df_energy)
                i1_tot.interpolate(inplace=True)
            file = os.path.basename(file).split('.')[0]
            summed_scan.to_csv(file + '_Processed_scan.dat')

            if i == 0:
                final_df = pd.DataFrame(summed_scan.index.values, columns=['Energy'])
                final_df_energy = final_df['Energy'].copy(deep=True)
                final_df['Counts'] = summed_scan.values
                final_df['I0'] = i0_tot.values
                final_df['I1'] = i1_tot.values
            else:
                final_df['Energy'] =  final_df['Energy'] +summed_scan.index.values  
                final_df['Counts'] = final_df['Counts'] + summed_scan.values

                final_df['I0'] = final_df['I0'] + i0_tot.values
                final_df['I1'] = final_df['I1'] + i1_tot.values
        final_df /= len(self.files_to_process)
        if not interpolate_to_first_scan:
            final_df.set_index('Energy', inplace=True)
        file_name = os.path.basename(self.files_to_process[0]).split('.')[0] + \
                    os.path.basename(self.files_to_process[0]).split('.')[1]
        final_df['Counts'].to_csv(file_name + '_Processed_Full_Data.dat', header=False, sep=' ') 
        #final_df.to_csv(file_name + '_Processed_Full_Data.dat',header=['Energy', 'SumRatio'], index=False, sep=' ')
        final_df['I0'].to_csv(file_name + '_Processed_Full_Data_I0.dat', header=False, sep=' ')
        (final_df['I1'] / final_df['I0']).to_csv(file_name + '_Processed_Full_Data_I1I0.dat',
                                                 header=False, sep=' ')
        return final_df

    def output_log(self):
        """
        Output statistical log information to a JSON file.
        """
        with open("output_log.json", "w") as f:
            json.dump(self.aggregation_info, f, indent=4, sort_keys=True)




# Example Usage:
#os.chdir(r'to/your/path/of/data')
#os.chdir(r'/Users/lbgee/Library/CloudStorage/GoogleDrive-lbgee@ucdavis.edu/My Drive/SLAC/Projects/Biohybrids/EXAFS/112123/RuCobaloxime/main')
#worker = XAS_Worker(beamline='7-3', manual_drops=['FF1'])
#worker.set_files_to_process('*.00[0-9]')
#worker.set_manual_drops_per_file({0: ['FF2']})  # Set manual drops for the first file
#worker.aggregate_data(interpolate_to_first_scan=True)
#worker.output_log()