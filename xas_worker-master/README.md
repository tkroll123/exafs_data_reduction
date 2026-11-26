# XAS Data Processing Script

This script is designed for processing X-ray Absorption Spectroscopy (XAS) data obtained from experiments. It performs various data processing tasks, including data extraction, calibration, and visualization.

# XAS Worker Documentation

## Overview

The `XAS_Worker` class is designed to streamline the processing of X-ray Absorption Spectroscopy (XAS) data. It offers methods to import, process, and aggregate XAS data, as well as generate calibration plots and handle various aspects of the analysis workflow.

For the EXAFS analysis workflow please see: https://docs.google.com/document/d/1srpQxFJeLqX7lK7VD9B2ALnowVvdSlPyglwPynpJ2gw/edit?usp=sharing

## Initialization

### `__init__(beamline, manual_drops=[])`

Initialize the `XAS_Worker` instance.

- `beamline`: Beamline identifier (e.g., '7-3', '9-3').
- `manual_drops`: List of channels to be manually dropped.

## File Handling

### `set_files_to_process(file_pattern)`

Set the files to be processed based on a file pattern.

### `set_manual_drops_per_file(modifications)`

Set manual drops on a per-file basis.

## Data Processing

### `workup_data(file_name, manual_drops=None)`

Process XAS data from a file.

- `file_name`: Name of the file to process.
- `manual_drops`: List of channels to be manually dropped (optional).

## Calibration

### `get_calibration(data, element='Co')`

Generate calibration plots for a given element.

- `data`: XAS data for calibration.
- `element`: Element for calibration (default is 'Co').

## Data Aggregation

### `aggregate_data(interpolate_to_first_scan=False)`

Aggregate processed XAS data.

- `interpolate_to_first_scan`: Interpolate values to the x-axis of the first scan (default is `False`).

## Output Logging

### `output_log()`

Output statistical information about the aggregation process.

# XAS Worker - Usage Guide


## Step 1: Initialization

Initialize the XAS worker instance.

```python
from XAS_Worker import XAS_Worker

# Initialize the XAS worker instance
worker = XAS_Worker(beamline='7-3', manual_drops=['FF1'])
```

Replace `'7-3'` with the appropriate beamline identifier. Optionally, provide a list of channels to be manually dropped (`manual_drops`).

---

## Step 2: Set Files to Process

Set the files to be processed using a file pattern.

```python
# Set the files to process using a file pattern
worker.set_files_to_process('*.00[0-9]')
```

Adjust the file pattern to match the files you want to process.

---

## Step 3: Set Manual Drops per File (Optional)

Set manual drops on a per-file basis if needed by index. You can see the indices of the files
based on the files_to_process attribute of the object.

```python
# Set manual drops on a per-file basis (if needed)
worker.set_manual_drops_per_file({0: ['FF2']})
```

Specify manual drops for individual files as a dictionary.

---

## Step 4: Data Processing/Aggregation

Aggregate processed XAS data.

```python
# Aggregate processed XAS data
worker.aggregate_data(interpolate_to_first_scan=False)
```

Optionally, set `interpolate_to_first_scan=True` to interpolate values to the x-axis of the first scan. Otherwise, the final x-axis will be an average of all x-axes processed.

---

## Step 5: Output Logging

Output statistical information about the aggregation process.

```python
# Output statistical information about the aggregation process
worker.output_log()
```

This step generates a JSON file (`output_log.json`) containing statistical information for each processed file.

---
## Step 6: TBD open and analyze with pyspline
## Step 7: TBD Output from pyspline and process for EXAFSPAK
## Step 8: TBD run feff
## Step 9: TBD run opt in EXAFSPAK

---

**Additional Notes**

Make sure to adjust parameters such as beamline and file patterns according to your specific experiment and data.

# Example Usage
```python
import os
from XAS_Worker import XAS_Worker
#os.chdir(r'to/your/path/of/data')
worker = XAS_Worker(beamline='7-3', manual_drops=['FF1'])
worker.set_files_to_process('*.00[0-9]')
worker.set_manual_drops_per_file({0: ['FF2']})  # Set manual drops for the first file
worker.aggregate_data()
worker.output_log()
```