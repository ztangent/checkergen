"""Provides support for CRS VideoEyetracker Toolbox."""

import os.path

try:
    import win32com.client
    available = True
except ImportError:
    available = False

# COM ProgID of the Toolbox
ProgID = "crsVET.VideoEyeTracker"
RecordName = "etResultSet"
# VET application object
VET = None

class EyetrackingError(Exception):
    """Raised when something goes wrong with VET."""
    pass

if available:
    # Try dispatching object, else unavailable
    try:
        from win32com.client import gencache
        # Ensure makepy module is generated
        gencache.EnsureModule('{248DBF0C-A874-4032-82CE-DC5B307BB6E7}',
                              0, 3, 11)
        VET = win32com.client.Dispatch(ProgID)
        DummyResultSet = win32com.client.Record(RecordName, VET)
    except:
        available = False

if available:

    # For easier access to constants and standardization with MATLAB interface
    CRS = win32com.client.constants
    
    lastgoodstamp = 0

    def select_source(user_select = False, path = None):
        if user_select:
            if not VET.SelectVideoSource(CRS.vsUserSelect, ''):
                msg = 'could not select video source'
                raise EyetrackingError(msg)
        elif path != None:
            # Open from file
            if not VET.SelectVideoSource(CRS.vsFile, path):
                msg = 'could not use path as video source'
                raise EyetrackingError(msg)            
        else:
            # Default to 250 Hz High Speed Camera
            if not VET.SelectVideoSource(CRS.vsHighSpeedCamera250, ''):
                msg = 'could not select video source'
                raise EyetrackingError(msg)

    def is_source_ready():
        """Returns true if a video source has been selected."""
        if VET.VideoSourceType == 0:
            return False
        else:
            return True

    def show_camera():
        VET.CreateCameraScreen(0)

    def quit_camera():
        VET.DestroyCameraScreen()
        
    def setup(viewing_distance=None, screen_dims=None,
              fixation_period=None, fixation_range=None):
        """Calibrates the display and sets fixation properties."""
        if viewing_distance != None and screen_dims != None:
            if len(screen_dims) != 2:
                msg = 'screen_dims must be a 2-tuple'
                raise ValueError(msg)
            VET.SetDeviceParameters(CRS.deUser, viewing_distance,
                                    screen_dims[0], screen_dims[1])
        if fixation_period != None:
            VET.FixationPeriod = fixation_period
        if fixation_range != None:
            VET.FixationRange = fixation_range

    def calibrate(path = None):
        """Calibrate the subject.
           Optionally supply a path with no spaces to a 
           calibration file to load."""
        if path == None:
            if not VET.Calibrate():
                msg = 'calibration failed'
                raise EyetrackingError(msg)
        else:
            if not os.path.isfile(path):
                msg = 'specified file does not exist'
                raise EyetrackingError(msg)
            if not VET.LoadCalibrationFile(path):
                msg = 'file could not be loaded'
                raise EyetrackingError(msg)

    def is_calibrated():
        if VET.CalibrationStatus()[0] != 0:
            return True
        else:
            return False

    def start():
        """Start tracking the eye."""
        global lastgoodstamp
        if VET.CalibrationStatus()[0] == 0:
            msg = 'subject not yet calibrated'
            raise EyetrackingError(msg)
        lastgoodstamp = 0
        VET.ClearDataBuffer()
        VET.StartTracking()

    def stop():
        """Stop tracking the eye."""
        VET.StopTracking()

    def is_tracked():
        """Returns true if the eye is being tracked."""
        data = VET.GetLatestEyePosition(DummyResultSet)[1]
        return data.Tracked

    def is_fixated(fix_pos, fix_range, fix_period):
        """Checks whether subject is fixating on specificied location.

        fix_pos -- (x, y) position of desired fixation location in mm
        from center of screen

        fix_range -- (width, height) of box surrounding fix_pos within
        which fixation is allowed (in mm)

        fix_period -- duration in milliseconds within which subject is
        assumed to continue fixating after fixation is detected at a 
        specific time

        """
        global lastgoodstamp
        if VET.CalibrationStatus()[0] == 0:
            msg = 'subject not yet calibrated'
            raise EyetrackingError(msg)
        data = VET.GetLatestEyePosition(DummyResultSet)[1]
        pos = (data.ScreenPositionXmm, data.ScreenPositionYmm)
        diff = [abs(p - fp) for p, fp in zip(pos, fix_pos)]
        if data.Tracked == True:
            if diff[0] < fix_range[0] and diff[1] < fix_range[1]:
                lastgoodstamp = data.TimeStamp
                return True
            elif (data.Timestamp - lastgoodstamp) <= fix_period:
                return True
        elif (data.Timestamp - lastgoodstamp) <= fix_period:
            return True

        return False
