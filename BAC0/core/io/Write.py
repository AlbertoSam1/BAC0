#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2015 by Christian Tremblay, P.Eng <christian.tremblay@servisys.com>
# Licensed under LGPLv3, see file LICENSE in this source tree.
#
'''
Write.py - creation of WriteProperty requests

    Used while defining an app
    Example::

        class BasicScript(WhoisIAm, WriteProperty)

    Class::

        WriteProperty()
            def write()

    Functions::

        print_debug()

'''
#--- 3rd party modules ---
from bacpypes.pdu import Address
from bacpypes.object import get_datatype

from bacpypes.apdu import WritePropertyRequest, SimpleAckPDU

from bacpypes.primitivedata import Null, Atomic, Integer, Unsigned, Real
from bacpypes.constructeddata import Array, Any
from bacpypes.iocb import IOCB
from bacpypes.core import deferred

#--- this application's modules ---
from .IOExceptions import WritePropertyCastError, NoResponseFromController, WritePropertyException, WriteAccessDenied, ApplicationNotStarted
from ..utils.notes import note_and_log


#------------------------------------------------------------------------------

@note_and_log
class WriteProperty():
    """
    Defines BACnet Write functions: WriteProperty [WritePropertyMultiple not supported]

    """

    def write(self, args, vendor_id=0):
        """ Build a WriteProperty request, wait for an answer, and return status [True if ok, False if not].

        :param args: String with <addr> <type> <inst> <prop> <value> [ <indx> ] [ <priority> ]
        :returns: data read from device (str representing data like 10 or True)

        *Example*::

            import BAC0
            myIPAddr = '192.168.1.10'
            bacnet = BAC0.ReadWriteScript(localIPAddr = myIPAddr)
            bacnet.write('2:5 analogValue 1 presentValue 100')

        Direct the controller at (Network 2, address 5) to write 100 to the presentValues of 
        its analogValue 1 (AV:1)
        """
        if not self._started:
            raise ApplicationNotStarted(
                'BACnet stack not running - use startApp()')
        args = args.split()
        self.log_debug("do_write %r", args)

        try:
            # build a WriteProperty request
            iocb = IOCB(self.build_wp_request(args, vendor_id=vendor_id))
            # pass to the BACnet stack
            deferred(self.this_application.request_io, iocb)

        except WritePropertyException as error:
            # construction error
            self.log_error("exception: %r", error)

        iocb.wait()             # Wait for BACnet response

        if iocb.ioResponse:     # successful response
            if not isinstance(iocb.ioResponse, SimpleAckPDU):   # expect an ACK
                self.log_warning("- not an ack. Write has failed.")
                return

        if iocb.ioError:        # unsuccessful: error/reject/abort
            raise NoResponseFromController()

    def build_wp_request(self, args, vendor_id=0):
        addr, obj_type, obj_inst, prop_id = args[:4]
        vendor_id = vendor_id
        if obj_type.isdigit():
            obj_type = int(obj_type)
        obj_inst = int(obj_inst)
        value = args[4]

        indx = None
        if len(args) >= 6:
            if args[5] != "-":
                indx = int(args[5])
        self.log_debug("    - indx: %r", indx)

        priority = None
        if len(args) >= 7:
            priority = int(args[6])
        self.log_debug("    - priority: %r", priority)

        # get the datatype

        if prop_id.isdigit():
            prop_id = int(prop_id)
        datatype = get_datatype(obj_type, prop_id, vendor_id=vendor_id)
        self.log_debug("    - datatype: %r", datatype)
        # change atomic values into something encodeable, null is a special
        # case
        if value == 'null':
            value = Null()

        elif issubclass(datatype, Atomic):
            if datatype is Integer:
                value = int(value)
            elif datatype is Real:
                value = float(value)
            elif datatype is Unsigned:
                value = int(value)
            value = datatype(value)

        elif issubclass(datatype, Array) and (indx is not None):
            if indx == 0:
                value = Integer(value)
            elif issubclass(datatype.subtype, Atomic):
                value = datatype.subtype(value)
            elif not isinstance(value, datatype.subtype):
                raise TypeError(
                    "invalid result datatype, expecting %s" %
                    (datatype.subtype.__name__,))

        elif not isinstance(value, datatype):
            raise TypeError(
                "invalid result datatype, expecting %s" %
                (datatype.__name__,))
        self.log_debug(
            "    - encodeable value: %r %s",
            (value, type(value)))

        # build a request
        request = WritePropertyRequest(
            objectIdentifier=(obj_type, obj_inst), propertyIdentifier=prop_id)
        request.pduDestination = Address(addr)

        # save the value
        request.propertyValue = Any()
        try:
            request.propertyValue.cast_in(value)
        except WritePropertyCastError as error:
            self.log_error("WriteProperty cast error: %r", error)

        # optional array index
        if indx is not None:
            request.propertyArrayIndex = indx

        # optional priority
        if priority is not None:
            request.priority = priority

        self.log_debug("    - request: %r", request)
        return request
