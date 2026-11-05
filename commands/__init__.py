# Here are the commands that are defined in this add-in. Each command is defined in its own module. 
# The modules are imported here and added to the list of commands. 

# TODO Import the modules corresponding to the commands you created.

# TODO add imported modules to this list.
# Fusion will automatically call the start() and stop() functions.
commands = []


# Assumes a defined a "start" function for each module.
# The start function will be run when the add-in is started.
def start():
    for command in commands:
        command.start()


# Assumes a defined "stop" function for each module.
# The stop function will be run when the add-in is stopped.
def stop():
    for command in commands:
        command.stop()