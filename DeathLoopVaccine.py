import re
import os
import signal
import configparser

from datetime import datetime

import psutil

import EverquestLogFile


#
# simple utility to prevent Everquest Death Loop
#
# The utility functions by parsing the current (most recent) Everquest log file, and if it detects
# Death Loop symptoms, it will respond by initiating a system process kill of all "eqgame.exe"
# processes (there should usually only be one).
#
# We will define a death loop as any time a player experiences X deaths in Y seconds, and no player
# activity during that time.  The values for X and Y are configurable, via the DeathLoopVaccine.ini file.
#
# For testing purposes, there is a back door feature, controlled by sending a tell to the following
# non-existent player:
#
#   death_loop:     Simulates a player death.
#
#                   Note however that this also sets a flag that disarms the conceptual
#                   "process-killer gun", which will allow every bit of the code to
#                   execute and be tested, but will stop short of actually killing any
#                   process
#
#                   The "process-killer gun" will then be armed again after the simulated
#                   player deaths trigger the simulated process kill, or after any simulated
#                   player death events "scroll off" the death loop monitoring window.
#
class DeathLoopVaccine(EverquestLogFile.EverquestLogFile):
    """
    the class derives from the EverquestLogFile class and relies on the base class
    for the log parsing functions.

    the class overloads the process_line() method to customize the parsing for this particular need
    """

    def __init__(self, base_directory: str, logs_directory: str, server_name: str, heartbeat: int,
                 deathloop_deaths: int, deathloop_seconds: int) -> None:
        """
        ctor

        :param base_directory: Base installation directory for Everquest
        :param logs_directory: Logs directory, typically '\\logs\\'
        :param server_name: Name of the server, i.e. 'P1999Green'
        :param heartbeat: Number of seconds of logfile inactivity before a check is made to re-determine most recent logfile
        :param deathloop_deaths: Define a deathloop as (number of deaths) in (number of seconds)
        :param deathloop_seconds: Define a deathloop as (number of deaths) in (number of seconds)
        """
        # parent ctor
        super().__init__(base_directory, logs_directory, server_name, heartbeat)

        self.deathloop_deaths = deathloop_deaths
        self.deathloop_seconds = deathloop_seconds

        # list of death messages
        # this will function as a scrolling queue, with the oldest message at position 0,
        # newest appended to the other end.  Older messages scroll off the list when more
        # than deathloop_seconds have elapsed.  The list is also flushed any time
        # player activity is detected (i.e. player is not AFK).
        #
        # if/when the length of this list meets or exceeds deathloop_deaths, then
        # the deathloop response is triggered
        self._death_list = list()

        # flag indicating whether the "process killer" gun is armed
        self._kill_armed = True

    def reset(self) -> None:
        """
        Utility function to clear the death_list and reset the armed flag
        """
        self._death_list.clear()
        self._kill_armed = True

    def process_line(self, line: str) -> None:
        """
        This method gets called by the base class parsing thread once for each parsed line.
        We overload it here to perform our special case parsing tasks.

        :param line: string with a single line from the logfile
        """
        # start with base class behavior, i.e. print the line to screen
        # check for death messages
        # check for indications the player is really not AFK
        # are we death looping?  if so, kill the process
        super().process_line(line)
        self.check_for_death(line)
        self.check_not_afk(line)
        self.deathloop_response()

    def check_for_death(self, line: str) -> None:
        """
        check for indications the player just died, and if we find it,
        save the message for later processing

        :param line: string with a single line from the logfile
        """

        # cut off the leading date-time stamp info
        trunc_line = line[27:]

        # does this line contain a death message
        slain_regexp = r'^You have been slain'
        m = re.match(slain_regexp, trunc_line)
        if m:
            # add this message to the list of death messages
            self._death_list.append(line)
            EverquestLogFile.starprint(f'DeathLoopVaccine:  Death count = {len(self._death_list)}')

        # a way to test - send a tell to death_loop
        slain_regexp = r'^death_loop'
        m = re.match(slain_regexp, trunc_line)
        if m:
            # add this message to the list of death messages
            # since this is just for testing, disarm the kill-gun
            self._death_list.append(line)
            EverquestLogFile.starprint(f'DeathLoopVaccine:  Death count = {len(self._death_list)}')
            self._kill_armed = False

        # only do the list-purging if there are already some death messages in the list, else skip this
        if len(self._death_list) > 0:

            # create a datetime object for this line, using the very capable datetime.strptime()
            now = datetime.strptime(line[0:26], '[%a %b %d %H:%M:%S %Y]')

            # now purge any death messages that are too old
            done = False
            while not done:
                # if the list is empty, we're done
                if len(self._death_list) == 0:
                    self.reset()
                    done = True
                # if the list is not empty, check if we need to purge some old entries
                else:
                    oldest_line = self._death_list[0]
                    oldest_time = datetime.strptime(oldest_line[0:26], '[%a %b %d %H:%M:%S %Y]')
                    elapsed_seconds = now - oldest_time

                    if elapsed_seconds.total_seconds() > self.deathloop_seconds:
                        # that death message is too old, purge it
                        self._death_list.pop(0)
                        EverquestLogFile.starprint(f'DeathLoopVaccine:  Death count = {len(self._death_list)}')
                    else:
                        # the oldest death message is inside the window, so we're done purging
                        done = True

    def check_not_afk(self, line: str) -> None:
        """
        check for "proof of life" indications the player is really not AFK

        :param line: string with a single line from the logfile
        """

        # only do the proof of life checks if there are already some death messages in the list, else skip this
        if len(self._death_list) > 0:

            # check for proof of life, things that indicate the player is not actually AFK
            # begin by assuming the player is AFK
            afk = True

            # cut off the leading date-time stamp info
            trunc_line = line[27:]

            # does this line contain a proof of life - casting
            regexp = r'^You begin casting'
            m = re.match(regexp, trunc_line)
            if m:
                # player is not AFK
                afk = False
                EverquestLogFile.starprint(f'DeathLoopVaccine:  Player Not AFK: {line}')

            # does this line contain a proof of life - communication
            # this captures tells, say, group, auction, and shout channels
            regexp = f'^(You told|You say|You tell|You auction|You shout|{self.char_name} ->)'
            m = re.match(regexp, trunc_line)
            if m:
                # player is not AFK
                afk = False
                EverquestLogFile.starprint(f'DeathLoopVaccine:  Player Not AFK: {line}')

            # does this line contain a proof of life - melee
            regexp = r'^You( try to)? (hit|slash|pierce|crush|claw|bite|sting|maul|gore|punch|kick|backstab|bash)'
            m = re.match(regexp, trunc_line)
            if m:
                # player is not AFK
                afk = False
                EverquestLogFile.starprint(f'DeathLoopVaccine:  Player Not AFK: {line}')

            # if they are not AFK, then go ahead and purge any death messages from the list
            if not afk:
                self.reset()

    def deathloop_response(self) -> None:
        """
        are we death looping?  if so, kill the process
        """

        # if the death_list contains more deaths than the limit, then trigger the process kill
        if len(self._death_list) >= self.deathloop_deaths:

            EverquestLogFile.starprint('---------------------------------------------------')
            EverquestLogFile.starprint('DeathLoopVaccine - Killing all eqgame.exe processes')
            EverquestLogFile.starprint('---------------------------------------------------')
            EverquestLogFile.starprint('DeathLoopVaccine has detected deathloop symptoms:')
            EverquestLogFile.starprint(f'    {self.deathloop_deaths} deaths in less than '
                                       f'{self.deathloop_seconds} seconds, with no player activity')

            # show all the death messages
            EverquestLogFile.starprint('Death Messages:')
            for line in self._death_list:
                EverquestLogFile.starprint('    ' + line)

            # get the list of eqgame.exe process ID's, and show them
            pid_list = get_eqgame_pid_list()
            EverquestLogFile.starprint(f'eqgame.exe process id list = {pid_list}')

            # kill the eqgame.exe process / processes
            for pid in pid_list:
                EverquestLogFile.starprint(f'Killing process [{pid}]')

                # for testing the actual kill process using simulated player deaths, uncomment the following line
                # self._kill_armed = True
                if self._kill_armed:
                    os.kill(pid, signal.SIGTERM)
                else:
                    EverquestLogFile.starprint('(Note: Process Kill only simulated, since death(s) were simulated)')

            # purge any death messages from the list
            self.reset()


#################################################################################################
#
# standalone functions
#

def get_eqgame_pid_list() -> list[int]:
    """
    get list of process ID's for eqgame.exe, using psutil module
    returns a list of process ID's (in case multiple versions of eqgame.exe are somehow running)

    :return: list of process ID integers
    """

    pid_list = list()
    for p in psutil.process_iter(['name']):
        if p.info['name'] == 'eqgame.exe':
            pid_list.append(p.pid)
    return pid_list


#################################################################################################


def main():

    # todo - what if ini file is not present
    # begin by reading in the config data
    config = configparser.ConfigParser()
    config.read('DeathLoopVaccine.ini')

    base_dir = config.get('Everquest', 'BASE_DIRECTORY', fallback=None)
    logs_dir = config.get('Everquest', 'LOGS_DIRECTORY', fallback='\\logs\\')
    server_name = config.get('Everquest', 'SERVER_NAME', fallback='P1999Green')
    heartbeat = config.getint('Everquest', 'HEARTBEAT', fallback=15)

    dl_deaths = config.getint('DeathLoop', 'DEATHS', fallback=4)
    dl_seconds = config.getint('DeathLoop', 'SECONDS', fallback=120)

    # print a startup message
    EverquestLogFile.starprint('-------------------------------------------------')
    EverquestLogFile.starprint('DeathLoopVaccine - Help prevent DeathLoop disease')
    EverquestLogFile.starprint('-------------------------------------------------')
    EverquestLogFile.starprint(f'Checking for '
                               f'{dl_deaths} deaths in '
                               f'{dl_seconds} seconds, '
                               f'with no player activity in the interim (AFK)')

    # create and start the DLV parser
    dlv = DeathLoopVaccine(base_dir, logs_dir, server_name, heartbeat, dl_deaths, dl_seconds)
    dlv.go()

    # note that as soon as the main thread ends, so will the child threads
    while True:
        pass


if __name__ == '__main__':
    main()
