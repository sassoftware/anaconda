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
_ = lambda x: gettext.ldgettext("anaconda", x)

import security
import tarinstall
from installclass import BaseInstallClass
from rhel import InstallClass as RHELInstallClass


class InstallClass(RHELInstallClass):
    id = 'rpath'
    name = _('rPath Appliance Base')
    description = _('default install class for rPath based appliances')

    sortPriority = 25000
    hidden = 1

    def getBackend(self):
        return tarinstall.TarBackend

    def setInstallData(self, anaconda):
        # Copied from rhel.py because supercalling it is hard due to a
        # weird importer bug.
        BaseInstallClass.setInstallData(self, anaconda)
        self.setDefaultPartitioning(anaconda.id.storage, anaconda.platform)
        # Don't overwrite selinux config by default.
        anaconda.id.security.setSELinux(security.SELINUX_DONT_CHANGE)
