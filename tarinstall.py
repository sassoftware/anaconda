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

import gettext
import os
import sys
_ = lambda x: gettext.ldgettext("anaconda", x)

import logging
from urlgrabber import grabber

from constants import DISPATCH_BACK
from flags import flags
from tarextract import TarExtractor
from tarcallbacks import ProgressCallback
from rpathbackendbase import rPathBackendBase, PackageSource
from product import productPath, productPackagePath

log = logging.getLogger('anaconda')


class TarBackend(rPathBackendBase):

    def __init__(self, anaconda):
        rPathBackendBase.__init__(self, anaconda)
        self.source = PackageSource(anaconda)
        self.manifests = [('tblist', False)]

    def addManifest(self, name, optional=False):
        self.manifests.append((name, optional))

    def doBackendSetup(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            return DISPATCH_BACK

        self.source.setup()
        self.comps = TarComps(self.source, anaconda.intf, self.manifests)
        if not self.comps.chunks:
            self.comps.processPackageData()

    def doInstall(self, anaconda):
        if flags.test:
            return

        totalSize = 0
        for chunk in self.comps.chunks:
            totalSize += chunk.size

        instProgress = ProgressCallback(anaconda, len(self.comps), totalSize)

        te = TarExtractor(anaconda.rootPath, progress=instProgress)

        scratchDir = '/tmp'

        for chunk in self.comps.chunks:
            # Try to retreive tarball chunk.
            while True:
                try:
                    path = os.path.join(productPackagePath, chunk.fn)
                    tempPath = os.path.join(scratchDir,
                            os.path.basename(chunk.fn))
                    fn = self.source.grab(chunk.disc, path, tempPath)
                    break
                except grabber.URLGrabError:
                    self.source.unmount()
                    anaconda.intf.messageWindow(_("Error"),
                        _("The file %s cannot be opened. This is due "
                          "to a missing or corrupt file.  "
                          "If you are installing from CD media this usually "
                          "means the CD media is corrupt, or the CD drive is "
                          "unable to read the media.\n\n"
                          "Press <return> to try again.") % chunk.fn)

            log.info('installing %s' % chunk.fn)

            # Extract chunk
            sha1sum = te.extractFile(fn)

            # Verify tar chunk
            if chunk.sha1sum and chunk.sha1sum != sha1sum.encode('hex'):
                log.critical('file failed to verify: %s' % chunk.fn)
                log.critical('expected %s, but got %s'
                    % (chunk.sha1sum, sha1sum.encode('hex')))
                self.source.unmount()
                rc = anaconda.intf.messageWindow(_('Error'),
                        _("The file %s cannot be verified. This is due "
                          "to a missing or corrupt file.  "
                          "If you are installing from CD media this usually "
                          "means the CD media is corrupt, or the CD drive is "
                          "unable to read the media.") % chunk.fn,
                        type='custom',
                        custom_icon='error',
                        custom_buttons=[_('_Exit'), ])
                if not rc:
                    if flags.rootpath:
                        msg =  _("The installer will now exit...")
                        buttons = [_("_Exit installer")]
                    else:
                        msg =  _("Your system will now be rebooted...")
                        buttons = [_("_Reboot")]

                    anaconda.intf.messageWindow(_("Exiting"),
                        msg,
                        type="custom",
                        custom_icon="warning",
                        custom_buttons=buttons)
                    sys.exit(1)
            elif chunk.sha1sum:
                log.info('verified %s' % chunk.fn)

            if fn == tempPath:
                # Only unlink if a temporary file was used.
                os.unlink(fn)

        te.done()
        anaconda.id.instProgress = None
        self.source.unmount()

    def getRequiredMedia(self):
        return self.comps.getRequiredMedia()


class TarComps(object):
    def __init__(self, source, intf, manifests):
        self.source = source
        self.intf = intf
        self.manifests = list(manifests)
        self.chunks = []

    def __len__(self):
        return len(self.chunks)

    def _getFiles(self):
        log.info('copying needed files')

        fullPaths = []
        for name, optional in self.manifests:
            relPath = productPath + '/base/' + name
            fullPath = None
            try:
                fullPath = self.source.grab(1, relPath)
            except grabber.URLGrabError:
                log.error("Error copying manifest file %s", relPath)

            if fullPath and not os.path.exists(fullPath):
                log.error("Manifest file %s is missing", relPath)
                fullPath = None

            if fullPath:
                fullPaths.append(fullPath)
            elif not optional:
                raise grabber.URLGrabError

        self.manifests = fullPaths

    def _parseTbList(self):
        log.info('parsing tblist')
        for path in self.manifests:
            for i, line in enumerate(open(path).readlines()):
                line = line.strip()
                parts = line.split()
                # Allow for lines with more elements, ignore extra elements.
                if len(parts) >= 4:
                    chunkfile, size, disc, sha1sum = parts[:4]
                elif len(parts) == 3:
                    chunkfile, size, disc = parts
                    sha1sum = None
                else:
                    log.warn('invalid line in tblist: %s: %s' % (i, line))
                    continue

                size = long(size)
                disc = int(disc)

                chunk = TarChunk(chunkfile, size, disc, sha1sum)
                if chunk not in self.chunks:
                    self.chunks.append(chunk)

    def processPackageData(self):
        title = _('Parsing Package Data')

        win = self.intf.waitWindow(title,
                    _('Copying needed files...'))

        self._getFiles()

        win.pop()
        win = self.intf.waitWindow(title,
                    _('Parsing File List...'))

        self._parseTbList()

        win.pop()

    def getRequiredMedia(self):
        discs = []
        for chunk in self.chunks:
            if chunk.disc not in discs:
                discs.append(chunk.disc)
        return discs


class TarChunk(object):
    __slots__ = ('fn', 'size', 'disc', 'sha1sum')

    def __init__(self, fn, size, disc, sha1sum):
        self.fn = fn
        self.size = size
        self.disc = disc
        self.sha1sum = sha1sum

    def __cmp__(self, other):
        if self.fn == other.fn:
            if not self.sha1sum and other.sha1sum:
                self.sha1sum = other.sha1sum
            elif not other.sha1sum and self.sha1sum:
                other.sha1sum = self.sha1sum
            return 0
        elif self.fn > other.fn:
            return 1
        elif self.fn < other.fn:
            return -1

    def __repr__(self):
        return ('<TarChunk(fn=%s, size=%s, disc=%s, sha1sum=%s)>'
                % (self.fn, self.size, self.disc, self.sha1sum))
