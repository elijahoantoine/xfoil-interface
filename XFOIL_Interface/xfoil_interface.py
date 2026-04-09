import os
import re
import queue
import shutil
import tempfile
import threading
import numpy as np
from winpty import PtyProcess
from utils import parse_pacc
import tkinter.filedialog as filedialog

# xfoil_path and process start as None and get set by init_xfoil() at startup.
# keeping them separate from module load means this file can be imported cleanly
# without needing XFOIL present (useful for testing).
xfoil_path = None
process = None


def init_xfoil():
    '''Locate the XFOIL executable and spawn the XFOIL process. Must be called once
    before run_xfoil_study or any other function that communicates with XFOIL.

    Searches the system PATH for "xfoil". If not found, opens a file browser so the
    user can locate the executable manually. Exits if no valid executable is selected.'''
    global xfoil_path, process

    xfoil_path = shutil.which("xfoil")  # search PC for XFOIL

    if xfoil_path is None:
        print("XFOIL executable not found in PATH.")
        xfoil_path = filedialog.askopenfilename(
            title="Select XFOIL Executable",
            filetypes=[("Executable Files", "*.exe"), ("All files", "*.*")]
        )
        if not xfoil_path:
            print("No file selected.")
            print("You can download XFOIL for Windows from: https://web.mit.edu/drela/Public/web/xfoil/")
            exit()
        elif "xfoil" not in xfoil_path.lower():
            print("Selected file does not appear to be XFOIL.")
            exit()

    process = PtyProcess.spawn([xfoil_path])  # open XFOIL


def read_until_prompt(prompts=("c>", 'Type "!" to continue', "VISCAL:  Convergence failed", "s>", "y/n)"), timeout=30):
    '''Read output from XFOIL character by character until we see a prompt indicating it's ready for the next command.

    Uses a background daemon thread to perform the blocking read so that the main thread
    can enforce a timeout. If no recognised prompt is seen within `timeout` seconds,
    a TimeoutError is raised rather than hanging forever.

    Arguments:
    prompts -- a tuple of strings to check for at the end of the output. These are common
               XFOIL prompts that indicate it is waiting for user input.
    timeout -- maximum seconds to wait before raising TimeoutError (default 30).
               Increase if running on a very slow machine or with a very high ITER count.

    Returns: The full output string read from XFOIL up until the prompt.

    Raises: TimeoutError if no prompt is seen within `timeout` seconds.
            RuntimeError if the PTY reader thread itself raises an exception.'''
    result_queue = queue.Queue()

    def _reader():
        '''Background daemon thread: reads chars from the PTY and puts the result
        on result_queue when a prompt is found, or puts an error if reading fails.'''
        try:
            buf = ""
            while True:
                char = process.read(1)
                buf += char
                if any(buf.endswith(p) for p in prompts):
                    result_queue.put(('ok', buf))
                    return
        except Exception as e:
            result_queue.put(('error', str(e)))

    t = threading.Thread(target=_reader, daemon=True)
    t.start()

    try:
        event, value = result_queue.get(timeout=timeout)
    except queue.Empty:
        # thread is still blocking on process.read() — it's a daemon so it won't
        # prevent exit, but we raise here so the caller can decide how to recover
        raise TimeoutError(
            f"XFOIL did not produce a recognised prompt within {timeout}s. "
            "It may be waiting for unexpected input, have stalled, or have crashed. "
            "Consider increasing `timeout` for high-iteration runs."
        )

    if event == 'error':
        raise RuntimeError(f"Error reading from XFOIL PTY: {value}")

    return value


def send_command(command):
    '''Send a command to XFOIL and read until the next prompt. Returns the output from XFOIL after sending the command.

    Arguments: command -- the string command to send to XFOIL (e.g. "OPER", "ALFA 5", "PACC", etc.)

    Returns: The output from XFOIL after sending the command, up until the next prompt. This can include convergence messages or errors.'''
    process.write(command + "\r\n")
    result = read_until_prompt()
    return result


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

    Returns: A tuple of (results, coord_path, desired_aoas, exit_reason) where results is a dictionary of the extracted data from the PACC file, coord_path is the path to the saved airfoil coordinates, desired_aoas is the list of AoA points that were analyzed, and exit_reason is "done", "n", or "q".'''

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

    # pre-compute desired_aoas as plain floats once for all tolerance comparisons below
    desired_aoas_float = [float(a) for a in desired_aoas]

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

    sweep_exit = ["done"]
    while True: # loop through the AoA sweep, and if we encounter a convergence failure at a desired AoA point, we will pause and ask the user if they want to retry that point or skip it. If they choose to retry, we will attempt to run that AoA point again immediately. If they choose to skip, we will move on to the next AoA point in the sweep. This allows the user to have control over how to handle convergence issues without crashing the entire program.
        try:
            for aoa in internal_aoas:

                output = send_command(f"ALFA {aoa}")

                if "VISCAL:  Convergence failed" in output:
                    if any(abs(aoa - d) < 0.001 for d in desired_aoas_float):
                        while True:
                            try:
                                choice = input(f"\nConvergence failed at AoA = {aoa}. Enter 'r' to retry, 's' to skip: ").strip().lower()
                                if choice == "r":
                                    output = send_command(f"ALFA {aoa}")
                                    break
                                elif choice == "s":
                                    break
                                else:
                                    print("Please enter 'r' or 's'.")
                            except KeyboardInterrupt:
                                print("\n\nSweep paused.")
                                while True:
                                    choice = input("(c) Continue  (n) Skip to next Re  (q) Quit entire study: ").strip().lower()
                                    if choice == "c":
                                        break
                                    elif choice == "n":
                                        break
                                    elif choice == "q":
                                        break
                                    else:
                                        print("Please enter 'c', 'n', or 'q'.")
                                if choice == "n" or choice == "q":
                                    sweep_exit[0] = choice
                                raise KeyboardInterrupt  # bubble up to outer handler

                # tolerance check instead of exact match — same reason as parse_pacc
                if any(abs(aoa - d) < 0.001 for d in desired_aoas_float):
                    cpwr_path_i = os.path.join(tmpdir, f"cpwr_{aoa}.txt")
                    send_command(f"CPWR {cpwr_path_i}")
                    cpwr_paths[aoa] = cpwr_path_i

            break  # loop finished naturally, exit while True

        except KeyboardInterrupt:
            print("\n\nSweep paused.")
            while True:
                choice = input("(c) Continue  (n) Skip to next Re  (q) Quit entire study: ").strip().lower()
                if choice == "c":
                    break
                elif choice == "n":
                    break
                elif choice == "q":
                    break
                else:
                    print("Please enter 'c', 'n', or 'q'.")
            if choice == "n" or choice == "q":
                sweep_exit[0] = choice
                break

    send_command("PACC")
    results = parse_pacc(pacc_path, desired_aoas, flow_type)
    return results, coord_path, desired_aoas, sweep_exit[0]


def restart_xfoil():
    '''Restart the XFOIL process to run a new study for multi-Re studies.
    Terminates the old PTY process before spawning a fresh one.'''
    global process

    # terminate the old process before spawning a new one so we don't leave
    # dead XFOIL processes running in the background across a multi-Re study
    try:
        process.terminate(force=True)
    except Exception:
        pass  # if it's already dead, just move on

    process = PtyProcess.spawn([xfoil_path])
