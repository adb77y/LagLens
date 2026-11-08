"""Optional Windows GPU-engine counters, read through the documented PDH API.

This is sampled engine utilization, NOT per-frame GPU busy time or VRAM usage.
Unavailable counters produce None rather than a guessed utilization.
"""
import ctypes
import os
from ctypes import wintypes


class CounterValue(ctypes.Structure):
    _fields_ = [('status',wintypes.DWORD), ('value',ctypes.c_double)]


class CounterItem(ctypes.Structure):
    _fields_ = [('name',wintypes.LPWSTR), ('formatted',CounterValue)]


class GpuSampler:
    def __init__(self,pid):
        self.query=ctypes.c_void_p()
        self.counter=ctypes.c_void_p()
        self.pid=pid
        self.available=False
        if os.name!='nt':
            return
        self.pdh=ctypes.WinDLL('pdh')
        self.pdh.PdhOpenQueryW.argtypes=[wintypes.LPCWSTR,ctypes.c_size_t,ctypes.POINTER(ctypes.c_void_p)]
        self.pdh.PdhAddEnglishCounterW.argtypes=[ctypes.c_void_p,wintypes.LPCWSTR,ctypes.c_size_t,ctypes.POINTER(ctypes.c_void_p)]
        self.pdh.PdhCollectQueryData.argtypes=[ctypes.c_void_p]
        self.pdh.PdhGetFormattedCounterArrayW.argtypes=[ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(wintypes.DWORD),ctypes.POINTER(wintypes.DWORD),ctypes.c_void_p]
        self.pdh.PdhCloseQuery.argtypes=[ctypes.c_void_p]
        if self.pdh.PdhOpenQueryW(None,0,ctypes.byref(self.query)):
            return
        path=r'\GPU Engine(*)\Utilization Percentage'
        if self.pdh.PdhAddEnglishCounterW(self.query,path,0,ctypes.byref(self.counter)):
            self.close();return
        self.available=self.pdh.PdhCollectQueryData(self.query)==0

    def sample(self):
        if not self.available or self.pdh.PdhCollectQueryData(self.query):
            return None
        size,count=wintypes.DWORD(),wintypes.DWORD()
        self.pdh.PdhGetFormattedCounterArrayW(self.counter,0x200,ctypes.byref(size),ctypes.byref(count),None)
        if not size.value or size.value>16*1024*1024:
            return None
        buffer=ctypes.create_string_buffer(size.value)
        if self.pdh.PdhGetFormattedCounterArrayW(self.counter,0x200,ctypes.byref(size),ctypes.byref(count),buffer):
            return None
        values=[]
        items=ctypes.cast(buffer,ctypes.POINTER(CounterItem))
        for i in range(count.value):
            item=items[i]
            name=item.name or ''
            if name.startswith(f'pid_{self.pid}_') and '_engtype_3D' in name and item.formatted.status in (0,1):
                values.append(max(0,min(100,item.formatted.value)))
        return max(values) if values else None

    def close(self):
        if self.query.value:
            self.pdh.PdhCloseQuery(self.query)
            self.query=ctypes.c_void_p()
        self.available=False
