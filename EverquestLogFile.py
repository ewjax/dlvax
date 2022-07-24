import glob
import os
import re
import threading
import time


# allow for testing, by forcing the bot to read an old log file
TEST_ELF = False
# TEST_ELF = True


class EverquestLogFile(threading.Thread):
    """
    class to encapsulate Everquest log file operations.
    This class is intended as a base class for any
    child class that needs log parsing abilities.

    The custom log parsing logic in the child class is accomplished by
    overloading the process_line() method
    """

    # type-hint reference to base class data member _started, to quiet PEP warning
    # about unreferenced attribute
    _started: threading.Event

    def __init__(self, base_directory: str, logs_directory: str, server_name: str, heartbeat: int) -> None:
        """
        ctor

        :param base_directory: Base installation directory for Everquest
        :param logs_directory: Logs directory, typically '\\logs\\'
        :param server_name: Name of the server, i.e. 'P1999Green'
        :param heartbeat: Number of seconds of logfile inactivity before a check is made to re-determine most recent logfile
        """
        # parent ctor
        # the daemon=True parameter causes this child thread object to terminate
        # when the parent thread terminates
        super().__init__(daemon=True)

        # instance data
        self.base_directory = base_directory
        self.logs_directory = logs_directory
        self.char_name = 'Unknown'
        self.server_name = server_name
        self.filename = self.build_filename(self.char_name)
        self.file = None

        self._parsing = threading.Event()
        self._parsing.clear()

        self.prevtime = time.time()
        self.heartbeat = heartbeat

    def build_filename(self, charname: str) -> str:
        """
        build the file name.
        call this anytime that the filename attributes change

        :param charname: Everquest character log to be parsed
        :return: complete filename
        """
        rv = self.base_directory + self.logs_directory + 'eqlog_' + charname + '_' + self.server_name + '.txt'
        return rv

    def set_parsing(self) -> None:
        """
        called when parsing is active
        """
        self._parsing.set()

    def clear_parsing(self) -> None:
        """
        called when parsing is no longer active
        """
        self._parsing.clear()

    def is_parsing(self) -> bool:
        """
        is the file being actively parsed

        :return: boolean True/False
        """
        return self._parsing.is_set()

    def open_latest(self, seek_end=True) -> bool:
        """
        open the file with most recent mod time (i.e. latest).

        :param seek_end:  True if parsing is to begin at the end of the file, False if at the beginning
        :return: True if a new file was opened, False otherwise
        """
        # get a list of all log files, and sort on mod time, latest at top
        mask = self.base_directory + self.logs_directory + 'eqlog_*_' + self.server_name + '.txt'
        files = glob.glob(mask)
        files.sort(key=os.path.getmtime, reverse=True)

        # todo foo - what if there are no files in the list?
        latest_file = files[0]

        # extract the character name from the filename
        # note that windows pathnames must use double-backslashes in the pathname
        # note that backslashes in regular expressions are double-double-backslashes
        # this expression replaces double \\ with quadruple \\\\, as well as the filename mask asterisk to a
        # named regular expression
        charname_regexp = mask.replace('\\', '\\\\').replace('eqlog_*_', 'eqlog_(?P<charname>[\\w ]+)_')
        m = re.match(charname_regexp, latest_file)
        char_name = m.group('charname')

        rv = False

        # figure out what to do
        # if we are already parsing a file, and it is the latest file - do nothing
        if self.is_parsing() and (self.filename == latest_file):
            # do nothing
            pass

        # if we are already parsing a file, but it is not the latest file, close the old and open the latest
        elif self.is_parsing() and (self.filename != latest_file):
            # stop parsing old and open the new file
            self.close()
            rv = self.open(char_name, latest_file, seek_end)

        # if we aren't parsing any file, then open latest
        elif not self.is_parsing():
            rv = self.open(char_name, latest_file, seek_end)

        return rv

    def open(self, charname: str, filename: str, seek_end=True) -> bool:
        """
        open the file.
        seek file position to end of file if passed parameter 'seek_end' is true

        :param charname: character name whose log file is to be opened
        :param filename: full log filename
        :param seek_end:  True if parsing is to begin at the end of the file, False if at the beginning
        :return: True if a new file was opened, False otherwise
        """
        try:
            self.file = open(filename, 'r', errors='ignore')
            if seek_end:
                self.file.seek(0, os.SEEK_END)

            self.char_name = charname
            self.filename = filename
            self.set_parsing()
            return True
        except OSError as err:
            starprint('OS error: {0}'.format(err))
            starprint('Unable to open filename: [{}]'.format(filename))
            return False

    def close(self) -> None:
        """
        close the file
        """
        self.file.close()
        self.clear_parsing()

    def readline(self) -> str or None:
        """
        get the next line
        :return: a string containing the next line, or None if no new lines to be read
        """
        if self.is_parsing():
            return self.file.readline()
        else:
            return None

    def go(self) -> bool:
        """
        call this method to kick off the parsing thread

        :return: True if file is opened successfully for parsing
        """
        rv = False

        # already parsing?
        if self.is_parsing():
            starprint('Already parsing character log for: [{}]'.format(self.char_name))

        else:

            # use a back door to force the system to read a test file
            if TEST_ELF:

                # read a sample file for testing
                filename = 'test_log.txt'

                # start parsing, but in this case, start reading from the beginning of the file,
                # rather than the end (default)
                rv = self.open('Testing', filename, seek_end=False)

            # open the latest file
            else:
                # open the latest file, and kick off the parsing process
                rv = self.open_latest()

            # if the log file was successfully opened, then initiate parsing
            if rv:

                # status message
                starprint('Now parsing character log for: [{}]'.format(self.char_name))

                # if the thread is not already running,
                # create the background thread and kick it off
                if not self._started.is_set():
                    self.start()

            else:
                starprint('ERROR: Could not open character log file for: [{}]'.format(self.char_name))
                starprint('Log filename: [{}]'.format(self.filename))

        return rv

    def stop(self) -> None:
        """
        call this function when ready to stop (opposite of go() function)
        """
        self.close()

    def run(self) -> None:
        """
        override the thread.run() method
        this method will execute in its own thread
        """
        # run forever
        while True:

            # process the log file lines here
            if self.is_parsing():

                # read a line
                line = self.readline()
                now = time.time()
                if line:
                    self.prevtime = now

                    # process this line
                    self.process_line(line)

                else:

                    # don't check the heartbeat if we are just testing
                    if not TEST_ELF:

                        # check the heartbeat.  Has our logfile gone silent?
                        elapsed_seconds = (now - self.prevtime)

                        if elapsed_seconds > self.heartbeat:
                            starprint('[{}] heartbeat over limit, elapsed seconds = {:.2f}'.format(self.char_name, elapsed_seconds))
                            self.prevtime = now

                            # attempt to open latest log file - returns True if a new logfile is opened
                            if self.open_latest():
                                starprint('Now parsing character log for: [{}]'.format(self.char_name))

                    # if we didn't read a line, pause just for a 100 msec blink
                    time.sleep(0.1)

    def process_line(self, line: str) -> None:
        """
        virtual method, to be overridden in derived classes to do whatever specialized
        parsing is required for that application.

        Default behavior is to simply print() the line

        :param line: line from logfile to be processed
        """
        print(line.rstrip())


#################################################################################################
#
# standalone functions
#

def starprint(line: str) -> None:
    """
    utility function to print with leading and trailing ** indicators

    :param line: line to be printed
    """
    print(f'** {line.rstrip():<100} **')


#
# test driver
#
def main():
    print('creating and starting elf, then sleeping for 20')

    base_directory = 'c:\\users\\ewjax\\Documents\\Gaming\\Everquest-Project1999'
    logs_directory = '\\logs\\'
    server_name = 'P1999Green'
    heartbeat = 15

    elf = EverquestLogFile(base_directory, logs_directory, server_name, heartbeat)
    elf.go()
    time.sleep(20)

    # test the ability to stop and restart the parsing
    print('stopping elf, then sleeping for 5')
    elf.stop()
    time.sleep(5)

    print('restarting elf, then sleeping for 30')
    elf.go()
    time.sleep(30)

    print('done done')
    elf.stop()


if __name__ == '__main__':
    main()
