# Author-Dariel Espinoza Lopez
# Description-Main entry point for add-in. Required for all add-ins and is used to start and stop the add-in.

from . import commands
from .lib import fusionAddInUtils as futil
import adsk.core

def run(context):
    try:
        # Display a message when the add-in is manually run.
        if not context['IsApplicationStartup']:
            app = adsk.core.Application.get()
            ui = app.userInterface
            ui.messageBox('The Fusion 360 Logger add-in has been loaded.')

       # Run the stop function for each command defined in commands/__init__.py
        commands.start()

    except:
        futil.handle_error('run')


def stop(context):
    try:
        # Remove all of the event handlers your app has created
        futil.clear_handlers()

        # Run the stop function for each command defined in commands/__init__.py
        commands.stop()

    except:
        futil.handle_error('stop')