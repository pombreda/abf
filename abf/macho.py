#!/usr/bin/env python2
## -*- coding: utf-8 -*-
##
##  Jonathan Salwan - 2014-11-23
##
##  http://shell-storm.org
##  http://twitter.com/JonathanSalwan
##
##  This program is free software: you can redistribute it and/or modify
##  it under the terms of the GNU General Public License as published by
##  the Free Software  Foundation, either  version 3 of  the License, or
##  (at your option) any later version.
##

from abf.cpu        import *
from abf.exception  import *
from ctypes         import *




class MACH_HEADER(Structure):
    _fields_ = [
                ('magic',           c_uint),
                ('cputype',         c_uint),
                ('cpusubtype',      c_uint),
                ('filetype',        c_uint),
                ('ncmds',           c_uint),
                ('sizeofcmds',      c_uint),
                ('flags',           c_uint)
               ]




class LOAD_COMMAND(Structure):
    _fields_ = [
                ('cmd',             c_uint),
                ('cmdsize',         c_uint)
               ]




class SEGMENT_COMMAND(Structure):
    _fields_ = [
                ('cmd',             c_uint),
                ('cmdsize',         c_uint),
                ('segname',         c_ubyte * 16),
                ('vmaddr',          c_uint),
                ('vmsize',          c_uint),
                ('fileoff',         c_uint),
                ('filesize',        c_uint),
                ('maxprot',         c_uint),
                ('initprot',        c_uint),
                ('nsects',          c_uint),
                ('flags',           c_uint)
               ]




class SEGMENT_COMMAND64(Structure):
    _fields_ = [
                ('cmd',             c_uint),
                ('cmdsize',         c_uint),
                ('segname',         c_ubyte * 16),
                ('vmaddr',          c_ulonglong),
                ('vmsize',          c_ulonglong),
                ('fileoff',         c_ulonglong),
                ('filesize',        c_ulonglong),
                ('maxprot',         c_uint),
                ('initprot',        c_uint),
                ('nsects',          c_uint),
                ('flags',           c_uint)
               ]




class SECTION(Structure):
    _fields_ = [
                ('sectname',        c_ubyte * 16),
                ('segname',         c_ubyte * 16),
                ('addr',            c_uint),
                ('size',            c_uint),
                ('offset',          c_uint),
                ('align',           c_uint),
                ('reloff',          c_uint),
                ('nreloc',          c_uint),
                ('flags',           c_uint),
                ('reserved1',       c_uint),
                ('reserved2',       c_uint)
               ]




class SECTION64(Structure):
    _fields_ = [
                ('sectname',        c_ubyte * 16),
                ('segname',         c_ubyte * 16),
                ('addr',            c_ulonglong),
                ('size',            c_ulonglong),
                ('offset',          c_uint),
                ('align',           c_uint),
                ('reloff',          c_uint),
                ('nreloc',          c_uint),
                ('flags',           c_uint),
                ('reserved1',       c_uint),
                ('reserved2',       c_uint)
               ]




class MACHOFlags:
    CPU_TYPE_I386               = 0x7
    CPU_TYPE_X86_64             = (CPU_TYPE_I386 | 0x1000000)
    CPU_TYPE_MIPS               = 0x8
    CPU_TYPE_ARM                = 12
    CPU_TYPE_SPARC              = 14
    CPU_TYPE_POWERPC            = 18
    CPU_TYPE_POWERPC64          = (CPU_TYPE_POWERPC | 0x1000000)
    LC_SEGMENT                  = 0x1
    LC_SEGMENT_64               = 0x19
    S_ATTR_SOME_INSTRUCTIONS    = 0x00000400
    S_ATTR_PURE_INSTRUCTIONS    = 0x80000000




''' This class parses the Mach-O '''
class MACHO:
    def __init__(self, binary):
        self.__binary = bytearray(binary)

        self.__machHeader   = None
        self.__rawLoadCmd   = None
        self.__sections_l   = []

        self.__setHeader()
        self.__setLoadCmd()


    def __setHeader(self):
        self.__machHeader = MACH_HEADER.from_buffer_copy(self.__binary)

        if self.getArchMode() == CpuMode.MODE_32:
            self.__rawLoadCmd   = self.__binary[28:28+self.__machHeader.sizeofcmds]

        elif self.getArchMode() == CpuMode.MODE_64:
            self.__rawLoadCmd   = self.__binary[32:32+self.__machHeader.sizeofcmds]


    def __setLoadCmd(self):
        base = self.__rawLoadCmd
        for i in range(self.__machHeader.ncmds):
            command = LOAD_COMMAND.from_buffer_copy(base)

            if command.cmd == MACHOFlags.LC_SEGMENT:
                segment = SEGMENT_COMMAND.from_buffer_copy(base)
                self.__setSections(segment.nsects, base[56:], 32)

            elif command.cmd == MACHOFlags.LC_SEGMENT_64:
                segment = SEGMENT_COMMAND64.from_buffer_copy(base)
                self.__setSections(segment.nsects, base[72:], 64)

            base = base[command.cmdsize:]


    def __setSections(self, sectionsNumber, base, sizeHeader):
        for i in range(sectionsNumber):
            if sizeHeader == 32:
                section = SECTION.from_buffer_copy(base)
                base = base[68:]
                self.__sections_l += [section]
            elif sizeHeader == 64:
                section = SECTION64.from_buffer_copy(base)
                base = base[80:]
                self.__sections_l += [section]


    def getEntryPoint(self):
        for section in self.__sections_l:
            if section.sectname[0:6] == [95, 95, 116, 101, 120, 116]:
                return section.addr


    def getExecSections(self):
        ret = []
        for section in self.__sections_l:
            if section.flags & MACHOFlags.S_ATTR_SOME_INSTRUCTIONS or section.flags & MACHOFlags.S_ATTR_PURE_INSTRUCTIONS:
                ret +=  [{
                            'name'    : section.sectname,
                            'offset'  : section.offset,
                            'size'    : section.size,
                            'vaddr'   : section.addr,
                            'opcodes' : self.__binary[section.offset:section.offset+section.size]
                        }]
        return ret


    def getDataSections(self):
        ret = []
        for section in self.__sections_l:
            if not section.flags & MACHOFlags.S_ATTR_SOME_INSTRUCTIONS and not section.flags & MACHOFlags.S_ATTR_PURE_INSTRUCTIONS:
                ret +=  [{
                            'name'    : section.sectname,
                            'offset'  : section.offset,
                            'size'    : section.size,
                            'vaddr'   : section.addr,
                            'data'    : self.__binary[section.offset:section.offset+section.size]
                        }]
        return ret


    def getArch(self):
        if self.__machHeader.cputype == MACHOFlags.CPU_TYPE_I386 or self.__machHeader.cputype == MACHOFlags.CPU_TYPE_X86_64:
            return CpuArch.CPU_X86
        if self.__machHeader.cputype == MACHOFlags.CPU_TYPE_ARM:
            return CpuArch.CPU_ARM
        if self.__machHeader.cputype == MACHOFlags.CPU_TYPE_MIPS:
            return CpuArch.CPU_MIPS
        else:
            return CpuArch.CPU_UNKNOWN


    def getArchMode(self):
        if self.__machHeader.magic == 0xfeedface:
            return CpuMode.MODE_32
        elif self.__machHeader.magic == 0xfeedfacf:
            return CpuMode.MODE_64
        else:
            return CpuMode.MODE_UNKNOWN


    def getFormat(self):
        return 'Mach-O'


    @property
    def header(self):
        return self.__machHeader


    @property
    def sections(self):
        return self.__sections_l


