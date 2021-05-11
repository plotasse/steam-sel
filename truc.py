#!/usr/bin/python

#from steamfiles import appinfo
import appinfo2
import binascii
import json

def decode(d):
    o = {}
    for k,v in d.items():
        #print(k, type(k), v, type(v))
        if type(k) is bytes:
            k = k.decode()
        if type(k) is dict:
            k = decode(k)

        if k == "checksum" and type(v) is bytes:
            v = binascii.hexlify(v)
        if type(v) is bytes:
            v = v.decode()
        if type(v) is dict:
            v = decode(v)
        #print(k, type(k), v, type(v))
        o[k] = v
    return o

with open("appinfo.vdf","rb") as f:
    d = appinfo2.load(f)

print(json.dumps(decode(d)))
