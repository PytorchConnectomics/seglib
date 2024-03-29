from imageio import imread, imwrite
import numpy as np
from emu.io import read_vol

class FileLoader:
    def __init__(self, fns = []):
        self.fid = 0
        self.fns = fns

    def getFilenames(self):
        pass

    def getFile(self):
        self.fid += 1
        return self.fns[self.fid - 1]

class AffinityLoader:
    def __init__(self, sz=[0,0,0], chunk_st=[0,0,0], chunk_sz=[0,0,0], filename=''):
        # zyx order
        self.sz = sz
        self.chunk_st = chunk_st
        self.chunk_sz = chunk_sz
        self.ran = [range(self.chunk_st[i], self.sz[i], self.chunk_sz[i]) for i in range(3)]

        self.filename = filename

    def getZchunk(self, z):
        pass

    def getZslice(self, zchunk, zi):
        pass

class MaskLoader:
    def __init__(self, name='mask', st=[0,0], sz=[0,0], filename='', erosion=0, ratio=[1,1,1]):
        self.name = name
        self.st = st
        self.sz = sz
        self.filename = filename
        self.ratio = ratio
        self.erosion = erosion
        self.mask = np.zeros(sz, np.uint8)

    def getZslice(self, z):
        pass

    def _getZslice(self, z):
        # find nearest z in the original resolution
        zz = (z + self.ratio[0]/2) // self.ratio[0] 
        # filename offset
        zz = int(zz + self.st[0])
        return read_vol(self.filename, zz)
