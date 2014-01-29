#!/bin/sh

if [[ "" = "$1" || "" = "$2" && "" = "$3" || "" = "$4" || "" != "$5" ]]; then
    echo usage: $0 COMMUNITY FILENAME TFTP_ADDRESS SNMP_ADDRESS >&2
    exit 1
fi

COMMUNITY="$1"
TFTP_FILE="$2"
TFTP_SERVER="$3"
DEVICE="$4"

I=$RANDOM # [0,32767]

echo "Row: $I"
snmpset -c $COMMUNITY -v 2c $DEVICE 1.3.6.1.4.1.9.9.96.1.1.1.1.2.$I i 1
snmpset -c $COMMUNITY -v 2c $DEVICE 1.3.6.1.4.1.9.9.96.1.1.1.1.3.$I i 4
snmpset -c $COMMUNITY -v 2c $DEVICE 1.3.6.1.4.1.9.9.96.1.1.1.1.4.$I i 1
snmpset -c $COMMUNITY -v 2c $DEVICE 1.3.6.1.4.1.9.9.96.1.1.1.1.5.$I a $TFTP_SERVER
snmpset -c $COMMUNITY -v 2c $DEVICE 1.3.6.1.4.1.9.9.96.1.1.1.1.6.$I s $TFTP_FILE
snmpset -c $COMMUNITY -v 2c $DEVICE 1.3.6.1.4.1.9.9.96.1.1.1.1.14.$I i 1

