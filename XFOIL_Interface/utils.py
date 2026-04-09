import os
import re
import shutil
import tkinter as tk
import tkinter.filedialog as filedialog
import numpy as np

root = tk.Tk()
root.withdraw()

def parse_pacc(pacc_path, desired_aoas, flow_type):
    '''Parse the XFOIL PACC output file to extract CL, CD, CM, and if viscous, CDp, CDf, and transition locations for the desired AoA points.

    Returns: A dictionary keyed by AoA with the extracted data.'''
    results = {}
    try: # if the file doesn't exist, return empty results instead of crashing
        with open(pacc_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Polar file not found. XFOIL may not have written any results.")
        return results

    # convert desired_aoas to regular python floats for comparison
    desired_aoas_float = [float(a) for a in desired_aoas]

    for line in lines: # read through the file line by line, look for lines with 7 values which indicate a data row, and check if the AoA matches one of our desired points. If it does, extract the data into the results dictionary.
        line = line.strip()
        try:
            values = line.split()
            if len(values) == 7:
                aoa = round(float(values[0]), 2)
                if any(abs(aoa - d) < 0.001 for d in desired_aoas_float):
                    cd  = float(values[2])
                    cdp = float(values[3])
                    results[aoa] = {
                        "CL":       float(values[1]),
                        "CD":       cd,
                        "CDp":      cdp if flow_type == "visc" else None,
                        "CDf":      round(cd - cdp, 6) if flow_type == "visc" else None,
                        "CM":       float(values[4]),
                        "x_tr_top": float(values[5]) if flow_type == "visc" else None,
                        "x_tr_bot": float(values[6]) if flow_type == "visc" else None,
                    }
        except ValueError:
            continue

    return results

def write_filtered_pacc(pacc_path, desired_aoas, tmpdir, i):
    '''Write a filtered version of the PACC output file that only includes the desired AoA points. This can be useful for saving and appending results without duplicates.'''
    filtered_path = os.path.join(tmpdir, f"pf{i}.txt")
    try: # if the file doesn't exist, return None instead of crashing. This can happen if XFOIL failed to write results for some reason. The calling code should check for None and handle it appropriately.
        with open(pacc_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Polar file not found. Cannot write filtered polar.")
        return None

    # convert desired_aoas to plain floats for tolerance comparison
    desired_aoas_float = [float(a) for a in desired_aoas]

    header_lines = []
    data_lines = []
    for line in lines: # read through the file line by line, look for lines with 7 values which indicate a data row, and check if the AoA matches one of our desired points. If it does, keep the line. If not, skip it. Also keep all header lines that don't match the data format.
        stripped = line.strip()
        values = stripped.split()
        if len(values) == 7:
            try:
                aoa = round(float(values[0]), 2)
                # tolerance check instead of exact match — numpy's arange can accumulate
                # small floating-point errors over many steps, so we give it a 0.001° window
                if any(abs(aoa - d) < 0.001 for d in desired_aoas_float):
                    data_lines.append(line)
                # if aoa not in desired_aoas, skip it
                continue
            except ValueError:
                pass
        header_lines.append(line)  # keep header lines

    # sort data lines ascending by AoA
    data_lines.sort(key=lambda l: float(l.strip().split()[0]))

    with open(filtered_path, 'w') as f:
        f.writelines(header_lines)
        f.writelines(data_lines)

    return filtered_path

def append_pacc(saved_path, new_pacc_path, desired_aoas):
    '''Append new data points from new_pacc_path to saved_path, replacing any existing points with the same AoA.
    This allows us to combine results from multiple runs without duplicates and keep the file organized.'''
    try:
        with open(saved_path, 'r') as f:
            existing_lines = f.readlines()
    except FileNotFoundError:
        print("Existing polar file not found. Cannot append.")
        return

    try:
        with open(new_pacc_path, 'r') as f:
            new_lines = f.readlines()
    except FileNotFoundError:
        print("New polar file not found. Cannot append.")
        return

    # convert desired_aoas to plain floats for tolerance comparison
    desired_aoas_float = [float(a) for a in desired_aoas]

    # extract new data rows keyed by aoa
    new_data = {}
    for line in new_lines:
        values = line.strip().split()
        if len(values) == 7:
            try:
                aoa = round(float(values[0]), 2)
                # tolerance check instead of exact match — same reason as write_filtered_pacc
                if any(abs(aoa - d) < 0.001 for d in desired_aoas_float):
                    new_data[aoa] = line
            except ValueError:
                continue

    # rebuild — replace overlapping rows, keep non-overlapping
    header_lines = []
    data_lines = []
    for line in existing_lines:
        values = line.strip().split()
        if len(values) == 7:
            try:
                aoa = round(float(values[0]), 2)
                if aoa in new_data:
                    data_lines.append(new_data.pop(aoa))  # replace with new
                else:
                    data_lines.append(line)  # keep existing
                continue
            except ValueError:
                pass
        header_lines.append(line)  # keep header lines

    # append remaining new rows not in existing file
    for line in new_data.values():
        data_lines.append(line)

    # sort all data ascending by AoA
    data_lines.sort(key=lambda l: float(l.strip().split()[0]))

    with open(saved_path, 'w') as f:
        f.writelines(header_lines)
        f.writelines(data_lines)

    print(f"Polar file updated and sorted. {len(new_data)} new points added.")

def parse_pacc_all(pacc_path, flow_type):
    '''Parse all data points from a PACC polar file regardless of desired AoAs.'''
    results = {}
    try:
        with open(pacc_path, 'r') as f:
            lines = f.readlines()
    except FileNotFoundError:
        print("Polar file not found.")
        return results

    for line in lines:
        line = line.strip()
        try:
            values = line.split()
            if len(values) == 7:
                aoa = round(float(values[0]), 2)
                cd  = float(values[2])
                cdp = float(values[3])
                results[aoa] = {
                    "CL":       float(values[1]),
                    "CD":       cd,
                    "CDp":      cdp if flow_type == "visc" else None,
                    "CDf":      round(cd - cdp, 6) if flow_type == "visc" else None,
                    "CM":       float(values[4]),
                    "x_tr_top": float(values[5]) if flow_type == "visc" else None,
                    "x_tr_bot": float(values[6]) if flow_type == "visc" else None,
                }
        except ValueError:
            continue
    return results

def display_results(results, flow_type="visc"):
    '''Display the extracted results from the PACC file in a clear tabular format.

    For viscous runs: shows CL, CD, CM, CDp, CDf, x_tr_top, x_tr_bot.
    For inviscid runs: shows only CL, CD, CM — the viscous-only columns (CDp, CDf,
    x_tr_top, x_tr_bot) are hidden entirely rather than printing N/A for every row.

    Arguments: - results: dictionary keyed by AoA with aerodynamic coefficient data
               - flow_type: "visc" or "inviscid" — controls which columns are shown.
                 inviscid runs hide CDp, CDf, x_tr_top, x_tr_bot entirely since those
                 values are meaningless without a boundary layer solution.'''
    print("\n--- XFOIL Results ---")

    if flow_type == "visc":
        # viscous: show all columns including boundary layer data
        print(f"{'AoA':>8} {'CL':>10} {'CD':>10} {'CM':>10} {'CDp':>10} {'CDf':>10} {'x_tr_top':>10} {'x_tr_bot':>10}")
        print("-" * 92)
        for aoa, data in sorted(results.items()):
            if data is None:
                print(f"{aoa:>8.2f} {'FAILED':>10}")
            else:
                cdp  = f"{data['CDp']:>10.4f}"      if data.get('CDp')      is not None else f"{'N/A':>10}"
                cdf  = f"{data['CDf']:>10.4f}"      if data.get('CDf')      is not None else f"{'N/A':>10}"
                xtr1 = f"{data['x_tr_top']:>10.4f}" if data.get('x_tr_top') is not None else f"{'N/A':>10}"
                xtr2 = f"{data['x_tr_bot']:>10.4f}" if data.get('x_tr_bot') is not None else f"{'N/A':>10}"
                print(f"{aoa:>8.2f} {data['CL']:>10.4f} {data['CD']:>10.4f} {data['CM']:>10.4f} {cdp} {cdf} {xtr1} {xtr2}")
    else:
        # inviscid: CDp, CDf, x_tr_top, x_tr_bot are meaningless — hide the columns entirely
        print(f"{'AoA':>8} {'CL':>10} {'CD':>10} {'CM':>10}")
        print("-" * 50)
        for aoa, data in sorted(results.items()):
            if data is None:
                print(f"{aoa:>8.2f} {'FAILED':>10}")
            else:
                print(f"{aoa:>8.2f} {data['CL']:>10.4f} {data['CD']:>10.4f} {data['CM']:>10.4f}")

def load_experimental_data():
    '''Prompt the user to load experimental data files for lift and drag comparison. The user can load multiple files,
    specify which columns correspond to AoA, CL, and CD, and provide labels for each dataset.

    Returns: Two dictionaries: one for lift data and one for drag data, keyed by the dataset label.'''

    exp_data_lift = {}
    exp_data_drag = {}

    while True:
        print("\nLoad experimental data file (or press Enter to skip):")
        root.lift()
        root.attributes('-topmost', True)
        filepath = filedialog.askopenfilename(
            title="Select experimental data file",
            filetypes=[("Data files", "*.dat *.txt *.csv"), ("All files", "*.*")]
        )
        root.attributes('-topmost', False)

        if not filepath:
            break

        # read file and show first few lines so user can see format
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print("File not found. Try again.")
            continue

        print("\nFirst 10 lines of file:")
        for i, line in enumerate(lines[:10]):
            print(f"  {i+1}: {line.rstrip()}")

        # ask which row data starts on
        while True:
            try:
                start_row = int(input("Which row does data start on? (1-indexed): ").strip())
                if start_row < 1:
                    print("Must be at least 1.")
                    continue
                break
            except ValueError:
                print("Invalid input. Enter a number.")

        # ask delimiter
        delim_input = input("Delimiter — (1) space/whitespace  (2) comma  (3) tab [default 1]: ").strip()
        if delim_input == "2":
            delimiter = ","
        elif delim_input == "3":
            delimiter = "\t"
        else:
            delimiter = None  # None means split on whitespace

        # parse data rows
        data_rows = []
        for line in lines[start_row - 1:]:
            line = line.strip()
            if not line:
                continue
            try:
                if delimiter:
                    parts = [float(x.strip()) for x in line.split(delimiter)]
                else:
                    parts = [float(x) for x in line.split()]
                data_rows.append(parts)
            except ValueError:
                continue  # skip header or non-numeric lines

        if not data_rows:
            print("No numeric data found. Check your start row and delimiter.")
            continue

        # show column count and ask user to map columns
        n_cols = len(data_rows[0])
        print(f"\nFound {n_cols} columns and {len(data_rows)} data rows.")
        print("Column mapping (enter column number, 1-indexed, or 0 to skip):")

        while True:
            try:
                aoa_col = int(input("Which column is AoA (alpha)? ").strip()) - 1
                cl_col  = int(input("Which column is CL? ").strip()) - 1
                cd_col  = int(input("Which column is CD? (0 to skip): ").strip()) - 1
                break
            except ValueError:
                print("Invalid input. Enter column numbers.")

        # extract columns
        try:
            aoas = [row[aoa_col] for row in data_rows]
            cls  = [row[cl_col]  for row in data_rows]
            cds  = [row[cd_col]  for row in data_rows if cd_col >= 0] if cd_col >= 0 else []
        except IndexError:
            print("Column index out of range. Check your column numbers.")
            continue

        # validate — check aoa range is reasonable
        if min(aoas) < -90 or max(aoas) > 90:
            print(f"Warning: AoA range {min(aoas):.1f} to {max(aoas):.1f} seems outside physical range. Check your column mapping.")

        # ask for a label for this dataset
        dataset_label = input("Enter a label for this dataset (e.g. 'Experimental Re=3e5'): ").strip()
        if dataset_label == "":
            dataset_label = os.path.basename(filepath)

        exp_data_lift[dataset_label] = (aoas, cls)
        if cds:
            exp_data_drag[dataset_label] = (cds, cls)

        print(f"Loaded {len(aoas)} data points.")

        while True:
            more = input("Load another experimental data file? (y/n): ").strip().lower()
            if more == "y":
                break
            elif more == "n":
                break
            else:
                print("Please enter 'y' or 'n'.")
        if more == "n":
            break

    return exp_data_lift if exp_data_lift else None, exp_data_drag if exp_data_drag else None

def get_airfoil_input():
    '''Prompt the user to enter an airfoil name (NACA 4 or 5 digit), a path to a .dat file, or browse for a file.
    Validates input and returns a command string to load the airfoil in XFOIL.

    For .dat files, validates both that the file exists AND that it contains at least 3 rows
    of valid two-column numeric coordinate data before accepting it. This prevents silently
    passing a bad file to XFOIL which would fail with an unhelpful Fortran error.

    Returns: A string command to load the airfoil in XFOIL, either a NACA designation (e.g. "naca2412") or a load command with file path (e.g. "load C:/path/to/airfoil.dat").'''
    def is_valid_naca(name):
        '''Validates any NACA airfoil designation. Accepts 4 or 5 digit NACA numbers, with or without "naca" prefix, and ignores spaces.'''
        name = name.replace(" ", "") # remove spaces for validation
        return bool(re.match(r'^naca\d{4,5}$', name.lower())) # matches naca followed by 4 or 5 digits

    while True:
        airfoil = input("Enter airfoil name (e.g. naca2412), full path to .dat file, or press Enter to browse: ").strip()
        # if user just presses Enter, open file dialog to select .dat file
        if airfoil == "":
            root.lift()
            root.attributes('-topmost', True)
            airfoil = filedialog.askopenfilename(title="Select airfoil .dat file", filetypes=[("DAT files", "*.dat"), ("All files", "*.*")])
            root.attributes('-topmost', False)
            if not airfoil:
                print("No file selected. Please try again.")
                continue

        if airfoil.lower().endswith(".dat"):
            # assume it's a file path, validate it exists
            if not os.path.isfile(airfoil):
                print("File not found. Please check the path and try again.")
                continue

            # also check that the file actually has coordinate data in it — just checking
            # that it exists isn't enough, a text or empty file would pass through and
            # cause a confusing XFOIL error instead of a clear message here
            valid_rows = 0
            try:
                with open(airfoil, 'r') as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            try:
                                float(parts[0])
                                float(parts[1])
                                valid_rows += 1
                            except ValueError:
                                continue
            except Exception:
                print("Could not read file. Please check the path and try again.")
                continue

            if valid_rows < 3:
                print(f"File does not appear to contain valid airfoil coordinates "
                      f"(found {valid_rows} numeric rows, need at least 3). "
                      f"Check that the file has two columns of x/y values.")
                continue

            return f"load {airfoil}"

        elif airfoil.lower().startswith("naca"):
            # validate NACA designation
            airfoil = airfoil.replace(" ", "")
            if not is_valid_naca(airfoil):
                print("Invalid NACA designation. Use 4 or 5 digit NACA (e.g. naca2412, naca23012).")
                continue
            return airfoil

        else:
            print("Invalid input. Enter a NACA designation (e.g. naca2412) or a path to a .dat file.")
            continue

def get_ncrit():
    '''Prompt the user to enter a Ncrit value for transition prediction in XFOIL. Validates that the input is numeric and within a reasonable range (e.g. 5-12).

    Returns: A float representing the Ncrit value to use in XFOIL, or 9 if the user selects default.'''
    while True:
        try:
            ncrit_input = input("Enter Ncrit value (default is 9, typical range 5-12): ").strip()
            # if user presses Enter, use default of 9
            if ncrit_input == "" or ncrit_input.lower() == "default":
                return 9
            ncrit = float(ncrit_input)
            if ncrit < 1 or ncrit > 20:
                print("Warning: Ncrit outside typical range. Enter valid Ncrit: ")
                continue
            return ncrit
        except ValueError:
            print("Invalid input. Enter a numeric value: ")

def get_moment_center():
    '''Prompt the user to enter a moment center location as a fraction of chord (e.g. 0.25 for quarter-chord). Validates that the input is numeric and between 0 and 1.

    Returns: Moment center as a float, or 0.25 if the user presses Enter for default.
    '''
    while True:
        try:
            cm_input = input("Enter moment center X (x/c, default is 0.25 for quarter-chord): ").strip()
            if cm_input == "" or cm_input.lower() == "default":
                return 0.25
            cm = float(cm_input)
            if cm < 0 or cm > 1:
                print("Moment center must be between 0 and 1 (e.g. 0.25 for quarter-chord).")
                continue
            return cm
        except ValueError:
            print("Invalid input. Please enter a decimal value.")

def get_flow_type():
    '''Prompt the user to select flow type (viscous or inviscid). If viscous is selected, also prompt for Ncrit value. Validates input.

    Returns: A tuple of (flow_type, ncrit) where flow_type is "visc" or "inviscid" and ncrit is a float or None.'''
    while True:
        flow_type = input("Select flow type (1 for Viscous, 2 for Inviscid): ").strip()
        if flow_type == "1":
            return "visc", get_ncrit()
        elif flow_type == "2":
            return "inviscid", None
        else:
            print("Invalid selection. Please enter 1 or 2.")

def get_reynolds_number():
    '''Prompt the user to enter a Reynolds number. Validates that the input is numeric and within a reasonable range for XFOIL (e.g. 1e3 to 1e9).

    Returns: Reynolds number as a float.'''
    while True:
        try:
            reynolds_input = input("Enter Reynolds number (e.g. 1e6): ").strip()
            reynolds_number = float(reynolds_input)
            if reynolds_number <= 0:
                print("Reynolds number must be positive.")
                continue
            elif reynolds_number < 1000:
                print("Reynolds number below 1000 is outside physical range for XFOIL.")
                continue
            elif reynolds_number > 1e9:
                print("Reynolds number above 1,000,000,000 is outside reliable XFOIL range.")
                continue
            return reynolds_number
        except ValueError:
            print("Invalid input. Please enter a numeric value.")

def get_mach_number():
    '''Prompt the user to enter a Mach number. Validates that the input is numeric and between 0 and 0.5, since XFOIL is a low subsonic tool.

    Returns: Mach number as a float, or 0 if the user presses Enter for default.'''
    while True:
        try:
            mach_input = input("Enter Mach number (default is 0, max reliable is 0.5): ").strip()
            if mach_input == "" or mach_input.lower() == "default":
                return 0
            mach = float(mach_input)
            if mach < 0:
                print("Mach number cannot be negative.")
                continue
            elif mach > 0.5:
                print("Mach number above 0.5 is outside XFOIL's reliable range. XFOIL is a low subsonic tool.")
                continue
            return mach
        except ValueError:
            print("Invalid input. Please enter a numeric value.")

def get_aoa_range():
    '''Prompt the user to select AoA input mode: either a range with step size or one individual point. Validates that the inputs are numeric and that the step size is positive.

    Returns: A list of [aoa_start, aoa_end, aoa_step].'''
    while True:
        try:
            mode_input = input("Select AoA input mode (1 for range with step size, 2 for one individual point): ").strip()
            if mode_input == "1":
                aoa_start = float(input("Enter start angle of attack (degrees): ").strip())
                aoa_end = float(input("Enter end angle of attack (degrees): ").strip())
                aoa_step = float(input("Enter step size (degrees): ").strip())
                if aoa_step <= 0:
                    print("Step size must be positive.")
                    continue
                elif aoa_step > 1:
                    print("Warning: Step size above 1 degree may lead to convergence errors. Consider using a smaller step size.")
                    retry = input("Would you like to retry with a smaller step size? (y/n): ").strip().lower()
                    if retry == "y" or retry == "yes":
                        continue
                return [aoa_start, aoa_end, aoa_step]
            elif mode_input == "2":
                aoa = float(input("Enter angle of attack (degrees): ").strip())
                return [aoa, aoa, 0.1]
            else:
                print("Invalid selection. Please enter 1 or 2.")
        except ValueError:
            print("Invalid input. Please enter numeric values.")

def get_max_iterations():
    '''Prompt the user to enter a maximum number of iterations for XFOIL to use in the OPER menu. Validates that the input is a positive integer.

    Returns: The max iterations as an int, or 1000 if the user presses Enter for default.'''
    while True:
        try:
            iter_input = input("Enter max iterations (default is 1000): ").strip()
            if iter_input == "" or iter_input.lower() == "default":
                return 1000
            max_iter = int(iter_input)
            if max_iter <= 0:
                print("Max iterations must be a positive integer.")
                continue
            else:
                return max_iter
        except ValueError:
            print("Invalid input. Please enter a whole number.")
