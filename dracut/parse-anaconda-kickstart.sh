#!/bin/bash
# parse-anaconda-kickstart.sh: handle kickstart settings

# inst.ks: provide a "URI" for the kickstart file
kickstart="$(getarg ks= inst.ks=)"
if [ -z "$kickstart" ]; then
    getargbool 0 ks inst.ks && kickstart='nfs:auto'
fi
# no root? the kickstart will probably tell us what our root device is.
[ "$kickstart" ] && [ -z "$root" ] && root="kickstart"


# inst.ks.device: define which network device should be used for fetching ks
# XXX does this imply ip=dhcp if not set?
ksiface="$(getarg ksdevice= inst.ks.dev= inst.ks.device=)"
# look up the MAC for ksiface=bootif
if [ "$ksiface"  = "bootif" ]; then
    BOOTIF=$(getarg 'BOOTIF=')
    ksiface=$(fix_bootif "$BOOTIF")
fi


# inst.ks.sendmac: send MAC addresses in HTTP headers
if getargbool 0 kssendmac inst.ks.sendmac; then
    ifnum=0
    for ifname in /sys/class/net/*; do
        mac=$(cat $ifname/address)
        ifname=${ifname#/sys/class/net/}
        # TODO: might need to choose devices better
        if [ "$ifname" != "lo" ] && [ -n "$mac" ]; then
            set_http_header "X-RHN-Provisioning-MAC-$ifnum" "$ifname $mac"
            ifnum=$(($ifnum+1))
        fi
    done
fi


# inst.ks.sendsn: send system serial number as HTTP header
if getargbool 0 kssendsn inst.ks.sendsn; then
    system_serial=$(cat /sys/class/dmi/id/product_serial 2>/dev/null)
    if [ -z "$system_serial" ]; then
        warn "inst.ks.sendsn: can't find system serial number"
    else
        set_http_header "X-System-Serial-Number" "$system_serial"
    fi
fi