"""Module for setting process priority. Currently only for Windows."""

import os
import sys

available = dict({'win32':False, 'cygwin':False,
                  'linux2':False, 'darwin':False})

if sys.platform in ['win32', 'cygwin']:
    try:
        import win32api
        import win32process
        import win32con
        available[sys.platform] = True
    except ImportError:
        pass

def set(level=1, pid=None):
    """Sets priority of specified process.
    
    level -- Can be low, normal, high or realtime. Users should be wary
    when using realtime and provide a reliable way to exit the process,
    since it may cause input to be dropped and other programs to become
    unresponsive.

    pid -- Process id. If None, current process id is used.
    
    """
    if sys.platform not in available or not available[sys.platform]:
        msg = 'Setting priority not available on {0}'.format(sys.platform)
        raise NotImplementedError(msg)
    elif level in [0,'low','idle']:
        set_low(pid)
    elif level in [1, 'normal']:
        set_normal(pid)
    elif level in [2, 'high']:
        set_high(pid)
    elif level in [3, 'realtime']:
        set_realtime(pid)
    else:
        msg = '{0} is not a valid priority level'.format(level)
        raise ValueError(msg)
        
if sys.platform not in available or not available[sys.platform]:
    msg = 'Setting priority not available on {0}'.format(sys.platform)
    def set_low(pid, msg=msg):
        raise NotImplementedError(msg)
    def set_normal(pid, msg=msg):
        raise NotImplementedError(msg)
    def set_high(pid, msg=msg):
        raise NotImplementedError(msg)
    def set_realtime(pid, msg=msg):
        raise NotImplementedError(msg)
elif sys.platform in ['win32', 'cygwin']:
    CUR_PID = win32api.GetCurrentProcessId()
    def set_low(pid):
        if pid == None:
            pid = CUR_PID
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        win32process.SetPriorityClass(handle,
                                      win32process.IDLE_PRIORITY_CLASS)
    def set_normal(pid):
        if pid == None:
            pid = CUR_PID
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        win32process.SetPriorityClass(handle,
                                      win32process.NORMAL_PRIORITY_CLASS)
    def set_high(pid):
        if pid == None:
            pid = CUR_PID
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        win32process.SetPriorityClass(handle,
                                      win32process.HIGH_PRIORITY_CLASS)
    def set_realtime(pid):
        if pid == None:
            pid = CUR_PID
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        win32process.SetPriorityClass(handle,
                                      win32process.REALTIME_PRIORITY_CLASS)

