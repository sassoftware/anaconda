#
# Copyright (c) 2011 rPath, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import logging
import time

log = logging.getLogger('anaconda')


def postProcess(func):
    def wrapper(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self.processEvents()
        return result
    return wrapper

class ProgressCallback(object):
    def __init__(self, anaconda, totalChunks, totalSize):
        self.anaconda = anaconda
        self.progress = anaconda.id.instProgress
        self.totalChunks = totalChunks
        self.totalSize = totalSize

        self._label = ''
        self._chunkSize = 0
        self._bufferSize = 0
        self._timeRemaining = 0
        self._totalChunkTime = 0
        self._percentComplete = 0
        self._installedChunkSize = 0.0
        self._timeChunkStarted = None

        self._stats = []

    def setChunkSize(self, size):
        self._installedChunkSize += size
        self._chunkSize = size

    def setBufferSize(self, size):
        if not self._bufferSize:
            self._bufferSize = size

    def processEvents(self):
        self._updateDisplay()
        self.progress.set_fraction(self._percentComplete)
        self.progress.set_label(self._label)
        self.progress.processEvents()

    def _updateDisplay(self):
        self._label = """\
Time Remaining: %s
""" % (self._formatTime(self._timeRemaining))

    def _getAverageSecondsPerByte(self):
        sum = 0
        for x in self._stats:
            sum += x
        if sum:
            avrg = sum / len(self._stats)
        else:
            avrg = 0
        return avrg

    def _formatTime(self, t):
        minutes = int(round(t) / 60)
        seconds = int(round(t) % 60)
        minutesStr = str(minutes)
        secondsStr = str(seconds)
        if minutes < 10:
            minutesStr = '0%s' % minutes
        if seconds < 10:
            secondsStr = '0%s' % seconds
        return '%s:%s' % (minutesStr, secondsStr)

    def startChunk(self):
        self._timeChunkStarted = time.time()

    @postProcess
    def stopChunk(self):
        t = time.time() - self._timeChunkStarted
        self._timeChunkStarted = None

        self._totalChunkTime += t

        if self._chunkSize:
            log.debug('t: %s' % t)

            self._stats.append(t / float(self._chunkSize))

            avrgSecsPerByte = self._getAverageSecondsPerByte()
            bytesRemaining = self.totalSize - self._installedChunkSize

            log.debug('average secs per byte: %s' % avrgSecsPerByte)
            log.debug('bytes remaining: %s' % bytesRemaining)

            if bytesRemaining > 0:
                self._timeRemaining = avrgSecsPerByte * bytesRemaining
            else:
                self._timeRemaining = 0
            self._percentComplete = self._installedChunkSize / self.totalSize

            log.debug('timeRemaining: %s' % self._timeRemaining)
            log.debug('percentComplete: %s' % self._percentComplete)

    def startWriteBuffer(self):
        pass

    @postProcess
    def stopWriteBuffer(self):
        pass
