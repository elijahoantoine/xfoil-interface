import os
import re
import shutil
import tempfile
import numpy as np
from winpty import PtyProcess
from utils import parse_pacc
import tkinter.filedialog as filedialog

#======== XFOIL Communication Functions ========
def read_until_prompt(prompts=("c>", 'Type "!" to continue', "VISCAL:  Convergence failed", "s>", "y/n)")):
    '''Read output from XFOIL character by character until we see a prompt indicating it's ready for the next command.
    
    Arguments:
    prompts -- a tuple of strings to check for at the end of the output. These are common XFOIL prompts that indicate it's waiting for user input. 
    We check if the output ends with any of these.

    Returns:    The full output string read from XFOIL up until the prompt. This can be useful for debugging or checking for convergence failure messages.
    '''
    output = ""
    while True:
        char = process.read(1)
        output += char
        if any(output.endswith(p) for p in prompts):
            break
    return output

def send_command(command):
    '''Send a command to XFOIL and read until the next prompt. Returns the output from XFOIL after sending the command.
    
    Arguments: command -- the string command to send to XFOIL (e.g. "OPER", "ALFA 5", "PACC", etc.)
    
    Returns: The output from XFOIL after sending the command, up until the next prompt. This can include convergence messages or errors.'''
    process.write(command + "\r\n")
    result = read_until_prompt()
    return result

# ======== XFOIL Study Functions ========
def run_xfoil_study(airfoil, flow_type, reynolds, mach, ncrit, aoa_range, max_iter, moment_center, pacc_path, cpwr_paths, tmpdir):
    '''Run a single XFOIL study for the given parameters. This includes loading the airfoil, setting up the flow conditions, running the AoA sweep, and extracting results.

    Arguments:
        airfoil (str): The path to the airfoil file.
        flow_type (str): The type of flow ('inviscid' or 'visc').
        reynolds (float): The Reynolds number.
        mach (float): The Mach number.
        ncrit (float): The transition criteria.
        aoa_range (tuple): A tuple of (start, end, step) for the AoA sweep.
        max_iter (int): The maximum number of iterations.
        moment_center (float): The moment center.
        pacc_path (str): The path to the PACC output file.
        cpwr_paths (dict): A dictionary mapping AoA values to CPWR output file paths.
        tmpdir (str): The temporary directory for storing intermediate files.

    Returns: A tuple of (results, coord_path, desired_aoas) where results is a dictionary of the extracted data from the PACC file, coord_path is the path to the saved airfoil coordinates, and desired_aoas is the list of AoA points that were analyzed.'''
    
    aoa_start = aoa_range[0]
    aoa_end = aoa_range[1]
    aoa_step = aoa_range[2]

    if aoa_start > aoa_end: # if sweeping from high to low AoA, generate desired_aoas in descending order and use a smaller internal step size for better convergence at high AoA
        desired_aoas = [round(a, 2) for a in np.arange(aoa_start, aoa_end - aoa_step, -aoa_step)]
        internal_step = min(0.025, aoa_step)
        internal_aoas = [round(a, 2) for a in np.arange(aoa_start, aoa_end - internal_step, -internal_step)]
    else: # sweeping from low to high AoA, generate desired_aoas in ascending order and use a smaller internal step size for better convergence at high AoA
        desired_aoas = [round(a, 2) for a in np.arange(aoa_start, aoa_end + aoa_step, aoa_step)]
        internal_step = min(0.05, aoa_step)
        internal_aoas = [round(a, 2) for a in np.arange(aoa_start, aoa_end + internal_step, internal_step)]

    

    
    send_command(airfoil)
    send_command("PANE")
    

    coord_path = os.path.join(tmpdir, "xy.dat")
    send_command("SAVE")
    send_command(coord_path.replace("\\", "/"))
    
    

    send_command(f"XYCM {moment_center} 0")
    send_command("OPER")
    

    if flow_type == "visc":
        send_command(f"VISC {reynolds}")
        

    if mach != 0:
        send_command(f"MACH {mach}")
        

    if flow_type == "visc":
        send_command("VPAR")
        send_command(f"N {ncrit}")
        send_command("")
        

    send_command(f"ITER {max_iter}")
    

    send_command("PACC")
    send_command(pacc_path)
    send_command("")
    
    
    while True: # loop through the AoA sweep, and if we encounter a convergence failure at a desired AoA point, we will pause and ask the user if they want to retry that point or skip it. If they choose to retry, we will attempt to run that AoA point again immediately. If they choose to skip, we will move on to the next AoA point in the sweep. This allows the user to have control over how to handle convergence issues without crashing the entire program.
        try:
            for aoa in internal_aoas:
                
                output = send_command(f"ALFA {aoa}")

                if "VISCAL:  Convergence failed" in output:
                    if any(abs(aoa - d) < 0.001 for d in desired_aoas):
                        while True:
                            choice = input(f"\nConvergence failed at AoA = {aoa}. Enter 'r' to retry, 's' to skip: ").strip().lower()
                            if choice == "r":
                                output = send_command(f"ALFA {aoa}")
                                break
                            elif choice == "s":
                                break
                            else:
                                print("Please enter 'r' or 's'.")

                if aoa in desired_aoas:
                    cpwr_path_i = os.path.join(tmpdir, f"cpwr_{aoa}.txt")
                    send_command(f"CPWR {cpwr_path_i}")
                    cpwr_paths[aoa] = cpwr_path_i

            break  # loop finished naturally, exit while True

        except KeyboardInterrupt: # if user presses Ctrl+C during the sweep, catch the KeyboardInterrupt and ask if they want to continue or quit. This allows them to pause the sweep if they see it's struggling at certain points and decide how to proceed.
            print("\n\nSweep paused.")
            while True:
                choice = input("(c) Continue  (q) Quit and save results so far: ").strip().lower()
                if choice == "c":
                    break  # breaks inner while, outer while loops back
                elif choice == "q":
                    break
                else:
                    print("Please enter 'c' or 'q'.")
            if choice == "q":
                break  # breaks outer while, falls through to PACC toggle and save

                

    send_command("PACC")
    results = parse_pacc(pacc_path, desired_aoas, flow_type)
    return results, coord_path, desired_aoas

def restart_xfoil():
    '''Restart the XFOIL process to run a new study for multi-Re studies'''
    global process
    import time
    try:
        send_command("QUIT")
    except:
        pass
    
    process = PtyProcess.spawn([xfoil_path])

xfoil_path = shutil.which("xfoil") # search PC for XFOIL
'''Search user's PC for XFOIL executable. If not found, prompt user to locate it manually. 
This allows the program to work even if XFOIL is not in the PATH, as long as the user can point to the executable.'''

if xfoil_path is None: 
    print("XFOIL executable not found in PATH.")
    xfoil_path = filedialog.askopenfilename(title="Select XFOIL Executable", filetypes=[("Executable Files", "*.exe"), ("All files", "*.*")])
    if not xfoil_path: 
        print("No file selected.")
        exit()
    elif "xfoil" not in xfoil_path.lower():
        print("Selected file does not appear to be XFOIL.")
        exit()
process = PtyProcess.spawn([xfoil_path]) # open XFOIL