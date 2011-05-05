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
import shutil
_ = lambda x: gettext.ldgettext("anaconda", x)

import image
import isys
import iutil
import logging
import network
import packages
import security
from constants import DISPATCH_BACK, productName
from flags import flags
from backend import AnacondaBackend
from urlgrabber import grabber

log = logging.getLogger('anaconda')


class rPathBackendBase(AnacondaBackend):

    def __init__(self, anaconda):
        AnacondaBackend.__init__(self, anaconda)

        self.supportsUpgrades = False
        self.supportsPackageSelection = False

    def doPreInstall(self, anaconda):
        if anaconda.dir == DISPATCH_BACK:
            for d in ("/selinux", "/dev", "/proc/bus/usb"):
                try:
                    isys.umount(anaconda.rootPath + d, removeDir = False)
                except Exception, e:
                    log.error("unable to unmount %s: %s" %(d, e))
            return

        dirList = ['/var', '/var/lib', '/var/lib/rpm', '/tmp', '/dev', '/etc',
                   '/etc/sysconfig', '/etc/sysconfig/network-scripts',
                   '/etc/X11', '/root', '/var/tmp', '/etc/rpm', '/var/cache',
                   '/var/cache/yum', '/etc/modprobe.d']

        # If there are any protected partitions we want to mount, create their
        # mount points now.
        for protected in anaconda.id.storage.protectedDevices:
            if getattr(protected.format, "mountpoint", None):
                dirList.append(protected.format.mountpoint)

        for i in dirList:
            try:
                os.mkdir(anaconda.rootPath + i)
            except os.error, (errno, msg):
                pass
#            log.error("Error making directory %s: %s" % (i, msg))

        self.initLog(anaconda.id, anaconda.rootPath)

        # SELinux hackery (#121369)
        if flags.selinux:
            try:
                os.mkdir(anaconda.rootPath + "/selinux")
            except Exception, e:
                pass
            try:
                isys.mount("/selinux", anaconda.rootPath + "/selinux", "selinuxfs")
            except Exception, e:
                log.error("error mounting selinuxfs: %s" %(e,))

        # For usbfs
        try:
            isys.mount("/proc/bus/usb", anaconda.rootPath + "/proc/bus/usb", "usbfs")
        except Exception, e:
            log.error("error mounting usbfs: %s" %(e,))

        # Write the fstab here as in yuminstall, it will be re-invoked after
        # the contents are laid down.
        self.anaconda = anaconda
        self.writeConfiguration(preInstall=True)

    def writeConfiguration(self, preInstall=False):
        anaconda = self.anaconda
        # write out the fstab
        anaconda.id.storage.fsset.write(anaconda.rootPath)
        if os.access("/etc/modprobe.d/anaconda.conf", os.R_OK):
            shutil.copyfile("/etc/modprobe.d/anaconda.conf", 
                            anaconda.rootPath + "/etc/modprobe.d/anaconda.conf")
        anaconda.id.network.write()
        anaconda.id.network.copyConfigToPath(instPath=anaconda.rootPath)
        anaconda.id.storage.write(anaconda.rootPath)
        if not anaconda.id.isHeadless:
            anaconda.id.keyboard.write(anaconda.rootPath)

        # make a /etc/mtab so mkinitrd can handle certain hw (usb) correctly
        f = open(anaconda.rootPath + "/etc/mtab", "w+")
        f.write(anaconda.id.storage.mtab)
        f.close()

        if not preInstall:
            # fstab and such may have changed, regenerate the initrd.
            w = anaconda.intf.waitWindow(_("Configuring"),
                    _("Configuring initramfs for your hardware"))
            for (n, arch, tag) in self.kernelVersionList():
                packages.recreateInitrd(n, self.anaconda.rootPath)
            w.pop()

            # Since tarballs don't have SELinux contexts, force a relabel if
            # anaconda has overwritten the SELinux config. If selinux is set to
            # "don't change" then also don't write the relabel file, it is up to
            # the image creator to do so.
            if anaconda.id.security.getSELinux() > security.SELINUX_DISABLED:
                open(anaconda.rootPath + '/.autorelabel', 'w').close()

    def kernelVersionList(self, rootPath='/'):
        l = []

        for file in os.listdir(self.instPath + '/boot'):
            if file.startswith('vmlinuz'):
                if 'domU' in file:
                    tag = 'xenU'
                elif 'dom0' in file:
                    tag = 'xen0'
                elif 'xen' in file:
                    tag = 'xen'
                elif 'smp' in file:
                    tag = 'smp'
                else:
                    tag = ''
                n = file.split('-')
                version = '-'.join(n[1:])
                arch = n[-1]
                l.append([version, arch, tag])
        return l

    # Stubs for packageless images

    def writePackagesKS(self, f, anaconda):
        pass

    def selectGroup(self, group, *args):
        pass

    def getDefaultGroups(self, anaconda):
        return []


class PackageSource(object):
    def __init__(self, anaconda):
        self.anaconda = anaconda
        self._timestamp = None
        self._baseRepoURL = None

        # Only needed for hard drive and nfsiso installs.
        self._discImages = {}
        self.isodir = None

        # Only needed for media installs.
        self.currentMedia = None
        self.hasMedia = False

        # Where is the source media mounted?  This is the directory
        # where Packages/ is located.
        self.tree = "/mnt/source"

    def setup(self):
        # yum doesn't understand all our method URLs, so use this for all
        # except FTP and HTTP installs.
        self._baseRepoURL = "file://%s" % self.tree

        while True:
            try:
                self.configBaseURL()
                break
            except SystemError as exception:
                self.anaconda.methodstr = self.anaconda.intf.methodstrRepoWindow(self.anaconda.methodstr or "cdrom:",
                                                                                 exception)
    def _switchCD(self, discnum):
        if os.access("%s/.discinfo" % self.tree, os.R_OK):
            f = open("%s/.discinfo" % self.tree)
            self._timestamp = f.readline().strip()
            f.close()

        dev = self.anaconda.id.storage.devicetree.getDeviceByName(self.anaconda.mediaDevice)
        dev.format.mountpoint = self.tree

        # If self.currentMedia is None, then there shouldn't be anything
        # mounted.  Before going further, see if the correct disc is already
        # in the drive.  This saves a useless eject and insert if the user
        # has for some reason already put the disc in the drive.
        if self.currentMedia is None:
            try:
                dev.format.mount()

                if image.verifyMedia(self.tree, discnum, None):
                    self.currentMedia = discnum
                    return

                dev.format.unmount()
            except:
                pass
        else:
            image.unmountCD(dev, self.anaconda.intf.messageWindow)
            self.currentMedia = None

        dev.eject()

        while True:
            if self.anaconda.intf:
                self.anaconda.intf.beep()

            self.anaconda.intf.messageWindow(_("Change Disc"),
                _("Please insert %(productName)s disc %(discnum)d to continue.")
                % {'productName': productName, 'discnum': discnum})

            try:
                dev.format.mount()

                if image.verifyMedia(self.tree, discnum, self._timestamp):
                    self.currentMedia = discnum
                    break

                self.anaconda.intf.messageWindow(_("Wrong Disc"),
                        _("That's not the correct %s disc.")
                          % (productName,))

                dev.format.unmount()
                dev.eject()
            except:
                self.anaconda.intf.messageWindow(_("Error"),
                        _("Unable to access the disc."))

    def _switchImage(self, discnum):
        image.umountImage(self.tree, self.currentMedia)
        self.currentMedia = None

        # mountDirectory checks before doing anything, so it's safe to
        # call this repeatedly.
        image.mountDirectory(self.anaconda.methodstr,
                       self.anaconda.intf.messageWindow)

        self._discImages = image.mountImage(self.isodir, self.tree, discnum,
                                      self.anaconda.intf.messageWindow,
                                      discImages=self._discImages)
        self.currentMedia = discnum

    def unmount(self):
        if not self.currentMedia:
            return
        if self.isodir:
            image.umountImage(self.tree, self.currentMedia)
        elif self.hasMedia:
            dev = self.anaconda.id.storage.devicetree.getDeviceByName(
                    self.anaconda.mediaDevice)
            dev.format.mountpoint = self.tree
            image.unmountCD(dev, self.anaconda.intf.messageWindow)
        self.currentMedia = None

    def configBaseURL(self):
        # We only have a methodstr if method= or repo= was passed to
        # anaconda.  No source for this base repo (the CD media, NFS,
        # whatever) is mounted yet since loader only mounts the source
        # for the stage2 image.  We need to set up the source mount
        # now.
        if self.anaconda.methodstr:
            m = self.anaconda.methodstr

            if m.startswith("hd:"):
                if m.count(":") == 2:
                    (device, path) = m[3:].split(":")
                else:
                    (device, fstype, path) = m[3:].split(":")

                self.isodir = "/mnt/isodir/%s" % path

                # This takes care of mounting /mnt/isodir first.
                self._switchImage(1)
            elif m.startswith("nfsiso:"):
                self.isodir = "/mnt/isodir"

                # Calling _switchImage takes care of mounting /mnt/isodir first.
                if not network.hasActiveNetDev():
                    if not self.anaconda.intf.enableNetwork():
                        self._baseRepoURL = None
                        return

                    grabber.reset_curl_obj()

                self._switchImage(1)
            elif m.startswith("http") or m.startswith("ftp:"):
                self._baseRepoURL = m
            elif m.startswith("nfs:"):
                if not network.hasActiveNetDev():
                    if not self.anaconda.intf.enableNetwork():
                        self._baseRepoURL = None

                    grabber.reset_curl_obj()

                (opts, server, path) = iutil.parseNfsUrl(m)
                isys.mount(server+":"+path, self.tree, "nfs", options=opts)

                # This really should be fixed in loader instead but for now see
                # if there's images and if so go with this being an NFSISO
                # install instead.
                images = image.findIsoImages(self.tree, self.anaconda.intf.messageWindow)
                if images != {}:
                    isys.umount(self.tree, removeDir=False)
                    self.anaconda.methodstr = "nfsiso:%s" % m[4:]
                    self.configBaseURL()
                    return
            elif m.startswith("cdrom:"):
                self.hasMedia = True
                self._switchCD(1)
                self._baseRepoURL = "file://%s" % self.tree
        else:
            # No methodstr was given.  In order to find an installation source,
            # we should first check to see if there's a CD/DVD with packages
            # on it, and then default to the mirrorlist URL.  The user can
            # always change the repo with the repo editor later.
            cdr = image.scanForMedia(self.tree, self.anaconda.id.storage)
            if cdr:
                self.anaconda.mediaDevice = cdr
                self.currentMedia = 1
                log.info("found installation media on %s" % cdr)
            else:
                # No CD with media on it and no repo=/method= parameter, so
                # default to using whatever's enabled in /etc/yum.repos.d/
                self._baseRepoURL = None

    def grab(self, discnum, path, filename=None):
        # The package exists on media other than what's mounted right now.
        if discnum != self.currentMedia:
            log.info("switching from media #%s to #%s for %s" %
                     (self.currentMedia, discnum, path))

            # Unmount any currently mounted ISO images and mount the one
            # containing the requested packages.
            if self.isodir:
                self._switchImage(discnum)
            elif self.hasMedia:
                self._switchCD(discnum)

        ug = grabber.URLGrabber()
        return ug.urlgrab("%s/%s" % (self._baseRepoURL, path), filename)
