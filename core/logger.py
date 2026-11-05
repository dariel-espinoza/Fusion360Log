import adsk.core
import adsk.fusion
import math
import time
import traceback

app = adsk.core.Application.get()
ui = app.userInterface

# import global add-in variables
from . import config

# Constants
SEC_IN_MIN = 60
MIN_IN_HR = 60
HR_IN_DAY = 24

# Global Variables
TIME_ELAPESED = 0