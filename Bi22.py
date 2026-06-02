""" calculation of the energy levels. and radiative transition rates
"""


""" calculation of the energy levels. and radiative transition rates
"""
import sys
from pfac.crm import *
from pfac import spm
from pfac import fac


#use openmoi
use_openmp = False
if len(sys.argv) == 2 and sys.argv[1] == 'openmp':
    use_openmp = True


if use_openmp:
    # enable openmp with 2 cores
    fac.InitializeMPI(16)

# atomic number
Z = 83
# number of electrons
K = 61

a = fac.ATOMICSYMBOL[Z]

p = '%s%02d'%(a,K)

fac.SetAtom(a)
SetUTA(0)

# '1s','2s','2p','3s','3p','3d','4s','4p' shells are closed
fac.Closed('1s','2s','2p','3s','3p','3d','4s','4p')

#4f14 group
fac.Config('4d10 4f14 5[s,p,d,f,g]', group = 'n2')
fac.Config('4d10 4f14 6[s,p,d,f,g]', group = 'n3')


#4f13 group
fac.Config('4d10 4f13 5s2',group = 'n4')
fac.Config('4d10 4f13 5s1 5[p,d,f,g]' ,group = 'n5')
fac.Config('4d10 4f13   5s1 6[s,p,d,f,g]', group = 'n6')
fac.Config('4d10 4f13 5p2 ',group = 'n7')
fac.Config('4d10 4f13 5p1 5[s,p,d,f,g]', group = 'n8')
fac.Config('4d10 4f13 5d2 ',group = 'n9')

#4f12 group
fac.Config('4d10 4f12 5s2 5[p,d,f,g]' ,group = 'n10')
fac.Config('4d10 4f12 5s1 5p2' ,group = 'n11')

#4f11 group
fac.Config('4d10 4f11 5s2 5p2' ,group = 'n12')


#ionization
fac.Config('4d10  4f14', group = 'i1')
fac.Config('4d10  4f13 5s1', group = 'i2')
fac.Config('4d10  4f12 5s2', group = 'i3')

fac.ConfigEnergy(0)
fac.OptimizeRadial(['n2','n3'])
fac.ConfigEnergy(1)
fac.GetPotential('Bi22.pot')

#structure
fac.Structure(p+'b.en', ['n2', 'n3','n4','n5','n6','n7','n8','n9','n10','n11','n12'])
fac.Structure(p+'b.en', ['i1', 'i2','i3'])

#energy level
fac.MemENTable(p+'b.en')
fac.PrintTable(p+'b.en',p+'a.en', 1)

#A-value
fac.TransitionTable(p+'b.tr', ['n2','n3','n4','n5','n6','n7','n8','n9','n10','n11','n12'],['n2','n3','n4','n5','n6','n7','n8','n9','n10','n11','n12'])
fac.PrintTable(p+'b.tr',p+'a.tr',1)

#excitation cross section
e = [100, 200, 300, 400, 500, 600, 700, 800]
fac.SetUsrCEGrid(e)
fac.CETable(p+'b.ce', ['n2','n3','n4','n5','n6','n7','n8','n9','n10','n11','n12'],['n2','n3','n4','n5','n6','n7','n8','n9','n10','n11','n12'])
fac.PrintTable(p+'b.ce',p+'a.ce', 1)

#ionization cross section
fac.SetUsrCIEGrid(e)
fac.CITable(p+'b.ci', ['n2','n3','n4','n5','n6','n7','n8','n9','n10','n11','n12'],['i1', 'i2','i3'])
fac.PrintTable(p+'b.ci',p+'a.ci', 1)


if use_openmp:
    FinalizeMPI()
