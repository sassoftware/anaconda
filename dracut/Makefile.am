# dracut/Makefile.am for anaconda
#
# Copyright (C) 2012 Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Author: Will Woods <wwoods@redhat.com>

dracutdir = /usr/lib/dracut/modules.d/80$(PACKAGE_NAME)
dist_dracut_DATA = module-setup.sh \
                   pythondeps.sh \
		   anaconda-lib.sh \
		   parse-anaconda-options.sh \
		   parse-anaconda-repo.sh \
		   parse-anaconda-kickstart.sh \
		   repo-genrules.sh \
		   anaconda-nfsroot \
		   anaconda-hdroot \
		   anaconda-copy-ks.sh \
		   fetch-kickstart \
		   parse-kickstart


MAINTAINERCLEANFILES = Makefile.in