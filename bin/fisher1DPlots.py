import matplotlib
matplotlib.use('Agg')
from ConfigParser import SafeConfigParser 
import cPickle as pickle
import sys
import numpy as np

from orphics.tools.io import FisherPlots


def getFisher(expName,calName,saveName,inParamList,suffix):
    saveId = expName + "_" + calName + "_" + suffix

    paramList,FisherTot = pickle.load(open("data/savedFisher_"+saveId+"_"+saveName+".pkl",'rb'))
    assert paramList==inParamList
    return FisherTot




iniFile = "input/pipeline.ini"
Config = SafeConfigParser()
Config.optionxform=str
Config.read(iniFile)

fishSection = "mnu"
noatm = ""
#noatm = "-noatm"
#cal = "CMB_all"
cal = "owl2"
derivSet = "wstep"

paramName = "mnu"
width = 0.1
paramCent = 0.06
paramStep = 0.001

# paramName = "w0"
# width = 0.1
# paramCent = -1.
# paramStep = 0.001

cosmoFisher = Config.get('fisher-'+fishSection,'saveSuffix')

paramList = Config.get('fisher-'+fishSection,'paramList').split(',')
paramLatexList = Config.get('fisher-'+fishSection,'paramLatexList').split(',')
fparams = {} 
for (key, val) in Config.items('params'):
    param = val.split(',')[0]
    fparams[key] = float(param)


"""RES STUDY"""
# cmbfisher3 = getFisher("S4-3m"+noatm,cal,cosmoFisher,paramList,derivSet)
# cmbfisher5 = getFisher("S4-5m"+noatm,cal,cosmoFisher,paramList,derivSet)
# cmbfisher6 = getFisher("S4-6m"+noatm,cal,cosmoFisher,paramList,derivSet)
# cmbfisher7 = getFisher("S4-7m"+noatm,cal,cosmoFisher,paramList,derivSet)
# fplots = FisherPlots(paramList,paramLatexList,fparams)
# fplots.addFisher('S4-3m',cmbfisher3)
# fplots.addFisher('S4-5m',cmbfisher5)
# fplots.addFisher('S4-6m',cmbfisher6)
# fplots.addFisher('S4-7m',cmbfisher7)
# listFishers = ['S4-3m','S4-5m','S4-6m','S4-7m']
# fplots.plot1d(paramName,np.arange(paramCent-width,paramCent+width,paramStep),listFishers,labels=listFishers,saveFile="/gpfs01/astro/www/msyriac/s41d"+paramName+"_"+cal+noatm+"_"+cosmoFisher+"_"+derivSet+".png")

"""OWL"""
res = "7m"
owl2 = getFisher("S4-"+res+noatm,"owl2",cosmoFisher,paramList,derivSet)
owl1 = getFisher("S4-"+res+noatm,"owl1",cosmoFisher,paramList,derivSet)
fplots = FisherPlots(paramList,paramLatexList,fparams)
fplots.addFisher('S4-'+res+'-owl2',owl2)
fplots.addFisher('S4-'+res+'-owl1',owl1)
listFishers = ['S4-'+res+'-owl2','S4-'+res+'-owl1']
labFishers = ['S4-'+res+' + LSST-like ($z<2$)','S4-'+res+' + LSST-like ($z<1$)']
fplots.plot1d(paramName,np.arange(paramCent-width,paramCent+width,paramStep),listFishers,labels=labFishers,saveFile="/gpfs01/astro/www/msyriac/s41dOWL"+res+paramName+"_"+cal+noatm+"_"+cosmoFisher+"_"+derivSet+".png",labloc='center left')
