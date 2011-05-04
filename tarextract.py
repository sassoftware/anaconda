#!/usr/bin/python
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

import sha
from subprocess import Popen, PIPE

import logging

log = logging.getLogger('anaconda')

class TarExtractor(object):
    def __init__(self, root, progress=None):
        self.root = root

        if progress:
            self.progress = progress
        else:
            self.progress = ProgressStub()

        self._stdoutlog = open('/tmp/tarextract.out', 'w')
        self._stderrlog = open('/tmp/tarextract.err', 'w')

        self._proc = self._getPipe()
        self._bufferSize = 16*1024

    def _getPipe(self):
        proc = Popen(['tar', 'vvvzixf', '-'],
                    stdin=PIPE, stdout=self._stdoutlog,
                     stderr=self._stderrlog, cwd=self.root)
        return proc

    def extractFile(self, file):
        sha1 = sha.new()
        chunkfh = open(file)

        chunkfh.seek(0, 2)
        end = chunkfh.tell()
        chunkfh.seek(0)

        self.progress.setChunkSize(end)
        self.progress.startChunk()

        while chunkfh.tell() < end:
            pos = chunkfh.tell()
            if pos + self._bufferSize > end:
                size = end - pos
            else:
                size = self._bufferSize

            self.progress.setBufferSize(size)
            self.progress.startWriteBuffer()

            data = chunkfh.read(size)
            self._extract(data)
            sha1.update(data)

            self.progress.stopWriteBuffer()

        self.progress.stopChunk()

        return sha1.digest()

    def done(self):
        self._proc.stdin.flush()
        self._proc.stdin.close()
        self._proc.wait()
        self._stdoutlog.close()
        self._stderrlog.close()
        self._proc = None

    def _extract(self, data):
        self._proc.stdin.write(data)
        self._proc.stdin.flush()


class TarExtractError(Exception):
    pass


class ProgressStub:
    def __getattr__(self, name):
        return self.foo
    def foo(self, *args, **kwargs):
        pass


if __name__ == '__main__':
    import os
    import sys
    import epdb
    from conary.lib import util

    sys.excepthook = util.genExcepthook()

    def usage():
        print 'usage: %s <directory of tarballs> <root to expand into>' % sys.argv[0]
        sys.exit(1)

    if len(sys.argv) != 3:
        usage()

    tbPath = sys.argv[1]
    root = sys.argv[2]

    epdb.st()

    te = TarExtractor(root)

    tbList = os.listdir(tbPath)
    tbList.sort()

    for tb in tbList:
        fullPath = os.path.join(tbPath, tb)
        epdb.st()
        te.extractFile(fullPath)
