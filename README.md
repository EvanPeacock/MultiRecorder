# MultiRecorder

A simple Python based utility for controlling and monitoring multiple OBS instances and BlackMagic HyperDeck products over a network connection.

![image](https://github.com/EvanPeacock/OBS-Controller/assets/36444106/3fb39038-09bb-447a-b76a-5cbd507edf50)

Capabilities
------------
For each connected OBS instance, MultiRecorder:
* Displays an inital screenshot (if enabled via command line arguments)
* Displays current framerate, resolution, and recording time
* Allows for stopping, starting, pausing, and unpausing of recording

For each BlackMagic HyperDeck product, MultiRecorder:
* Displays current framerate, resolution, video interface, codec, and recording time
* Allows for stopping and starting, of recording

Usage
-----
MultiRecorder reads from a yaml configuration file which specifies:
* Name: A readable nickname for a connection for identification in the GUI
* Host: A hostname or IP address to connect to
* Port (OBS connections only): The port the OBS WebSocket server is running on

Each connection has a button to simply start or stop its individual recording. OBS connections have an additional button to pause or unpause recording. There are also buttons at the top of the GUI that can start and stop recording on all connections.
