#!/usr/bin/python3
# SPDX-License-Identifier: GPL-2.0-only
# Copyright (C) 2024 Bardia Moshiri <fakeshell@bardia.tech>

from dbus_next.aio import MessageBus
from dbus_next.service import (ServiceInterface,
                               method, dbus_property, signal)
from dbus_next.constants import PropertyAccess
from dbus_next import Variant, DBusError, BusType

import asyncio
import dbus
import os
import re

class FWUPDInterface(ServiceInterface):
    def __init__(self, loop, bus):
        super().__init__('org.freedesktop.fwupd')
        self.loop = loop
        self.bus = bus
        self.props = {
            'DaemonVersion': Variant('s', '1.9.12'),
            'HostBkc': Variant('s', ''),
            'HostVendor': Variant('s', ''),
            'HostProduct': Variant('s', ''),
            'HostMachineId': Variant('s',''),
            'HostSecurityId': Variant('s', '1'),
            'Tainted': Variant('b', False),
            'Interactive': Variant('b', False),
            'Status': Variant('u', 1),
            'Percentage': Variant('u', 0),
            'BatteryLevel': Variant('u', 101), # 101 means unknown
            'OnlyTrusted': Variant('b', True),
            # anything from here onwards is not shown as properties, they are used by methods instead,
            'Devices': Variant('aa{sv}', []),
            'Plugins': Variant('aa{sv}', [{'Name': Variant('s', 'hybris')}])
        }

        self.set_props()

    def set_props(self):
        vendor = self.extract_prop('ro.product.vendor.manufacturer')
        self.props['HostVendor'] = Variant('s', vendor.upper() if vendor != '' else '')

        codename = self.extract_prop('ro.product.vendor.name')
        self.props['HostProduct'] = Variant('s', codename.upper() if codename != '' else '')

        if os.path.exists("/etc/machine-id"):
            with open("/etc/machine-id", "r") as machine_id_file:
                machine_id = machine_id_file.read()
        else:
            machine_id = ""

        self.props['HostMachineId'] = Variant('s', machine_id)

        try:
            with open('/proc/bootconfig', 'r') as file:
                for line in file:
                    if 'androidboot.bootloader' in line:
                        parts = line.split('=')
                        if len(parts) == 2:
                            bootloader = parts[1].strip().strip('"')
                    if 'androidboot.serialno' in line:
                        parts = line.split('=')
                        if len(parts) == 2:
                            bootloader_serialno = parts[1].strip().strip('"')
        except Exception as e:
            bootloader = self.extract_prop('ro.bootloader')

        if bootloader:
            arr_bootloader = {
                'DeviceId': Variant('s', '1'),
                'Name': Variant('s', bootloader),
                'Vendor': Variant('s', f'{vendor.capitalize()} Bootloader' if vendor != '' else ''),
                'Version': Variant('s', '1'),
                'Plugin': Variant('s', 'hybris'),
                'Protocol': Variant('s', 'hybris'),
                'Flags': Variant('t', 2),
                'Serial': Variant('s', bootloader_serialno if bootloader_serialno != '' else '')
            }

            self.props['Devices'].value.append(arr_bootloader)

        try:
            bus = dbus.SystemBus()
            manager = dbus.Interface(bus.get_object('org.ofono', '/'), 'org.ofono.Manager')
            modems = manager.GetModems()
            for path, properties in modems:
                if "Revision" in properties:
                    modem_rev = properties["Revision"]
                if "Serial" in properties:
                    modem_serial = properties["Serial"]
                if "SoftwareVersionNumber" in properties:
                    modem_ver = properties["SoftwareVersionNumber"]

            ofono = True
        except Exception as e:
            ofono = False

        if ofono:
            arr_modem = {
                'DeviceId': Variant('s', '1'),
                'Name': Variant('s', modem_rev),
                'Vendor': Variant('s', f'{vendor.capitalize()} Modem' if vendor != '' else ''),
                'Version': Variant('s', modem_ver if modem_ver != '' else '1'),
                'Plugin': Variant('s', 'hybris'),
                'Protocol': Variant('s', 'hybris'),
                'Flags': Variant('t', 2),
                'Serial': Variant('s', modem_serial if modem_serial != '' else '')
            }

            self.props['Devices'].value.append(arr_modem)

        sensor_hal = ['1.0', '2.0', '2.1']
        sensor_out = ""

        for version in sensor_hal:
            command = f'binder-call -d /dev/hwbinder android.hardware.sensors@{version}::ISensors/default 1 reply i32 "[ {{ i32 i32 hstr hstr i32 }} ]"'
            sensor_out = os.popen(command).read()

            if sensor_out.strip():
                # print(f"Successful output with version {version}")
                break

        if sensor_out.strip():
            pattern = re.compile(r'{ (\d+) \d+ "([^"]+)"H "([^"]+)"H (\d+) }')
            matches = pattern.findall(sensor_out)

            if matches:
                for match in matches:
                    sensor_id, sensor_name, sensor_vendor, sensor_ver = match
                    # print(f"Sensor: {sensor_name}\nVendor: {sensor_vendor}\nVersion: {sensor_ver}\n")

                    arr_sensor = {
                        'DeviceId': Variant('s', '1'),
                        'Name': Variant('s', sensor_name),
                        'Vendor': Variant('s', f'{sensor_vendor}' if sensor_vendor != '' else ''),
                        'Version': Variant('s', sensor_ver if sensor_ver != '' else '1'),
                        'Plugin': Variant('s', 'hybris'),
                        'Protocol': Variant('s', 'hybris'),
                        'Flags': Variant('t', 2),
                        'Serial': Variant('s', sensor_id if sensor_id != '' else '')
                    }

                    self.props['Devices'].value.append(arr_sensor)

    @dbus_property(access=PropertyAccess.READ)
    async def DaemonVersion(self) -> 's':
        return self.props['DaemonVersion'].value

    @dbus_property(access=PropertyAccess.READ)
    async def HostBkc(self) -> 's':
        return self.props['HostBkc'].value

    @dbus_property(access=PropertyAccess.READ)
    async def HostVendor(self) -> 's':
        return self.props['HostVendor'].value

    @dbus_property(access=PropertyAccess.READ)
    async def HostProduct(self) -> 's':
        return self.props['HostProduct'].value

    @dbus_property(access=PropertyAccess.READ)
    async def HostMachineId(self) -> 's':
        return self.props['HostMachineId'].value

    @dbus_property(access=PropertyAccess.READ)
    async def HostSecurityId(self) -> 's':
        return self.props['HostSecurityId'].value

    @dbus_property(access=PropertyAccess.READ)
    async def Tainted(self) -> 'b':
        return self.props['Tainted'].value

    @dbus_property(access=PropertyAccess.READ)
    async def Interactive(self) -> 'b':
        return self.props['Interactive'].value

    @dbus_property(access=PropertyAccess.READ)
    async def Status(self) -> 'u':
        return self.props['Status'].value

    @dbus_property(access=PropertyAccess.READ)
    async def Percentage(self) -> 'u':
        return self.props['Percentage'].value

    @dbus_property(access=PropertyAccess.READ)
    async def BatteryLevel(self) -> 'u':
        return self.props['BatteryLevel'].value

    @dbus_property(access=PropertyAccess.READ)
    async def OnlyTrusted(self) -> 'b':
        return self.props['OnlyTrusted'].value

    @method()
    def GetDevices(self) -> 'aa{sv}':
        return self.props['Devices'].value

    @method()
    def GetPlugins(self) -> 'aa{sv}':
        return self.props['Plugins'].value

    # anything from here onwards is mostly useless, implemented for sake of completeness
    @method()
    def GetReleases(self, device_id: 's') -> 'aa{sv}':
        return []

    @method()
    def GetDowngrades(self, device_id: 's') -> 'aa{sv}':
        return []

    @method()
    def GetUpgrades(self, device_id: 's') -> 'aa{sv}':
        return []

    @method()
    def GetDetails(self, handle: 'h') -> 'aa{sv}':
        return []

    @method()
    def GetHistory(self) -> 'aa{sv}':
        return []

    @method()
    def GetHostSecurityAttrs(self) -> 'aa{sv}':
        return []

    @method()
    def GetHostSecurityEvents(self, limit: 'u') -> 'aa{sv}':
        return []

    @method()
    def GetReportMetadata(self) -> 'a{ss}':
        return []

    @method()
    def SetHints(self, hints: 'a{ss}'):
        pass

    @method()
    def Install(self, id: 's', handle: 'h', options: 'a{sv}'):
        pass

    @method()
    def Verify(self, id: 's'):
        pass

    @method()
    def Unlock(self, id: 's'):
        pass

    @method()
    def Activate(self, id: 's'):
        pass

    @method()
    def GetResults(self, id: 's') -> 'a{sv}':
        return []

    @method()
    def GetRemotes(self) -> 'aa{sv}':
        return []

    @method()
    def GetApprovedFirmware(self) -> 'as':
        return []

    @method()
    def SetApprovedFirmware(self, checksums: 'as'):
        pass

    @method()
    def GetBlockedFirmware(self) -> 'as':
        return []

    @method()
    def SetBlockedFirmware(self, checksums: 'as'):
        pass

    @method()
    def SetFeatureFlags(self, feature_flags: 't'):
        pass

    @method()
    def ClearResults(self, id: 's'):
        pass

    @method()
    def ModifyDevice(self, device_id: 's', key: 's', value: 's'):
        pass

    @method()
    def ModifyConfig(self, key: 's', value: 's'):
        pass

    @method()
    def UpdateMetadata(self, remote_id: 's', data: 'h', signature: 'h'):
        pass

    @method()
    def ModifyRemote(self, remote_id: 's', key: 's', value: 's'):
        pass

    @method()
    def FixHostSecurityAttr(self, appstream_id: 's'):
        pass

    @method()
    def UndoHostSecurityAttr(self, appstream_id: 's'):
        pass

    @method()
    def SelfSign(self, data: 's', options: 'a{sv}') -> 's':
        return ''

    @method()
    def SetBiosSettings(self, settings: 'a{ss}'):
        pass

    @method()
    def GetBiosSettings(self) -> 'aa{sv}':
        return []

    @method()
    def Inhibit(self, reason: 's') -> 's':
        return ''

    @method()
    def Uninhibit(self, inhibit_id: 's'):
        pass

    @method()
    def Quit(self):
        pass

    @method()
    def EmulationLoad(self, data: 'ay'):
        pass

    @method()
    def EmulationSave(self) -> 'ay':
        return []

    def extract_prop(self, prop):
        prop_files = [
            '/var/lib/lxc/android/rootfs/vendor/build.prop',
            '/android/vendor/build.prop',
            '/vendor/build.prop',
            '/var/lib/lxc/android/rootfs/odm/etc/build.prop',
            '/android/odm/etc/build.prop',
            '/odm/etc/build.prop',
            '/vendor/odm_dlkm/etc/build.prop'
        ]

        for file in prop_files:
            if os.path.exists(file):
                prop_file = file
                break

        with open(file, 'r') as f:
            for line in f:
                if line.startswith(prop):
                    return line.split('=')[1].strip()

        return ''

async def main():
    bus = await MessageBus(bus_type=BusType.SYSTEM).connect()
    loop = asyncio.get_running_loop()
    fwupd_interface = FWUPDInterface(loop, bus)
    bus.export('/', fwupd_interface)
    await bus.request_name('org.freedesktop.fwupd')
    await bus.wait_for_disconnect()

asyncio.run(main())
