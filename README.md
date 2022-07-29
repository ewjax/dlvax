
DeathLoopVaccine
================

The purpose of the DeathLoopVaccine utility is to simply monitor an Everquest log file, and check for a "death loop" condition.  This can happen in Everquest if you somehow get into the situation where you are AFK, and your character begins to die near your bind point, such that you die, respawn, die, respawn, etc.  That condition is known as a death loop.

In this case, we define the symptoms of a death loop in the following manner:
  - D deaths (default 4), in
  - T seconds (default 120),
  - with no player activity (melee-ing, casting, or communicating) in the interim.
  
The values for D and T are configurable in the DeathLoopVaccine.ini file.

  - [DeathLoop]
  - DEATHS = 4
  - SECONDS = 120

If DeathLoopVaccine determines that the conditions for a death loop are met, then it will respond by killing the operating system process for 'eqgame.exe'.  


Testing
-------

To test the utility, you can simulate a death in-game by sending a tell to the non-existent user, 'death_loop', i.e.

  /t death_loop
  
DeathLoopVaccine will register this as a simulated death.  Since this is a simulated death, however, it will only simulate the actual killing of the eqgame.exe process.


Installation
------------

As a Windows executable:
  - Unzip the DeathLoopVaccine zip file
  - Copy DeathLoopVaccine.ini.example to DeathLoopVaccine.ini, and edit it for the location of your Everquest installation
  - Ensure the .exe and .ini files are in the same directory, and double-click the .exe file to run it
  - That's all that is needed.  The program will automatically begin monitoring the most recent character log file, and when you switch characters, it will automatically switch as well
  
As a python script:
  - Unzip the source file or clone the GitHub repository to your local computer
  - Copy DeathLoopVaccine.ini.example to DeathLoopVaccine.ini, and edit it for the location of your Everquest installation
  - Using make:  Type the command
      - make setup
  - Manually:  Type the command
      - pip install -r requirements.txt
  - Run the script with the command
      - py DeathLoopVaccine.py
      
      
  

