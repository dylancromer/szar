from __future__ import print_function
from __future__ import division
from future import standard_library
standard_library.install_aliases()
from builtins import zip
from builtins import range
from builtins import object
from past.utils import old_div
import numpy as np
from szar.counts import ClusterCosmology,Halo_MF
from szar.szproperties import gaussian
import emcee
import signals
#import simsTools
from scipy import special,stats
from scipy.interpolate import interp2d
from astropy.io import fits
from astLib import astWCS
from configparser import SafeConfigParser
from orphics.io import dict_from_section
import pickle as pickle
import matplotlib.pyplot as plt
from .tinker import dn_dlogM
import time

#import time
from enlib import bench

def read_MJH_noisemap(noiseMap,maskMap):
    #Read in filter noise map
    img = fits.open(noiseMap)
    rmsmap=img[0].data
    #Read in mask map
    img2 = fits.open(maskMap)
    mmap=img2[0].data
    return rmsmap*mmap

def read_clust_cat(fitsfile,qmin):
    list = fits.open(fitsfile)
    data = list[1].data
    SNR = data.field('SNR2p4')
    z = data.field('z')
    zerr = data.field('zErr')
    Y0 = data.field('y0tilde')
    Y0err = data.field('y0tilde_err')
    ind = np.where(SNR >= qmin)[0]
    return z[ind],zerr[ind],Y0[ind],Y0err[ind]

def read_mock_cat(fitsfile,qmin):
    list = fits.open(fitsfile)
    data = list[1].data
    SNR = data.field('fixed_SNR')
    z = data.field('redshift')
    zerr = data.field('redshiftErr')
    Y0 = data.field('fixed_y_c')
    Y0err = data.field('err_fixed_y_c')
    ind = np.where(SNR >= qmin)[0]
    return z[ind],zerr[ind],Y0[ind],Y0err[ind]

def read_full_mock_cat(fitsfile):
    list = fits.open(fitsfile)
    data = list[1].data
    ID = data.field('Cluster_ID')
    x = data.field('x_ind')
    y = data.field('y_ind')
    ra = data.field('RA')
    dec = data.field('DEC')
    z = data.field('redshift')
    zerr = data.field('redshiftErr')
    Y0 = data.field('fixed_y_c')
    Y0err = data.field('err_fixed_y_c')
    SNR = data.field('fixed_SNR')
    M = data.field('M500')
    return ID,x,y,ra,dec,z,zerr,Y0,Y0err,SNR,M

def read_test_mock_cat(fitsfile,mmin):
    list = fits.open(fitsfile)
    data = list[1].data
    z = data.field('redshift')
    m = data.field('Mass')
    zerr = data.field('redshift_err')
    merr = data.field('Mass_err')
    ind = np.where(m >= mmin)[0]
    print("number of clusters above threshold",mmin,"is", len(ind))#,m[ind]
    return z[ind],zerr[ind],m[ind],merr[ind]

def alter_fparams(fparams,parlist,parvals):
    for k,parvals in enumerate(parvals):
        fparams[parlist[k]] = parvals
    return fparams

class clusterLike(object):
    def __init__(self,iniFile,parDict,nemoOutputDir,noiseFile,fix_params,fitsfile,test=False,simtest=False,simpars=False):
        self.fix_params = fix_params
        self.test = test
        self.simtest = simtest
        self.simpars = simpars
        Config = SafeConfigParser()
        Config.optionxform=str
        Config.read(iniFile)

        self.fparams = {}
        for (key, val) in Config.items('params'):
            if ',' in val:
                param, step = val.split(',')
                self.fparams[key] = float(param)
            else:
                self.fparams[key] = float(val)

        bigDataDir = Config.get('general','bigDataDirectory')
        self.clttfile = Config.get('general','clttfile')
        self.constDict = dict_from_section(Config,'constants')
        #version = Config.get('general','version')
        
        #self.mgrid,self.zgrid,siggrid = pickle.load(open(bigDataDir+"szgrid_"+expName+"_"+gridName+ "_v" + version+".pkl",'rb'))
        logm_min = 13.7
        logm_max = 15.72
        logm_spacing = 0.02
        self.mgrid = np.arange(logm_min,logm_max,logm_spacing)
        self.zgrid = np.arange(0.1,2.01,0.1)        
        #print self.mgrid
        #print self.zgrid
        self.qmin = 5.6
        
        self.cc = ClusterCosmology(self.fparams,self.constDict,clTTFixFile=self.clttfile)
        self.HMF = Halo_MF(self.cc,self.mgrid,self.zgrid)

        self.diagnosticsDir=nemoOutputDir+"diagnostics" 
        self.filteredMapsDir=nemoOutputDir+"filteredMaps"
        self.tckQFit=simsTools.fitQ(parDict, self.diagnosticsDir, self.filteredMapsDir)
        FilterNoiseMapFile = nemoOutputDir + noiseFile
        MaskMapFile = self.diagnosticsDir + '/areaMask.fits'
        
        #if self.simtest or self.simpars:
        #    print "mock catalog"
            #clust_cat = nemoOutputDir + 'mockCatalog_equD56.fits' #'ACTPol_mjh_cluster_cat.fits'
        #    clust_cat = nemoOutputDir + 'mockCat_D56equ_v22.fits' #'ACTPol_mjh_cluster_cat.fits'
        #    self.clst_z,self.clst_zerr,self.clst_y0,self.clst_y0err = read_mock_cat(clust_cat,self.qmin)
        #else:
        #    print "real catalog"
        #    clust_cat = nemoOutputDir + 'E-D56Clusters.fits' #'ACTPol_mjh_cluster_cat.fits'
        #    self.clst_z,self.clst_zerr,self.clst_y0,self.clst_y0err = read_clust_cat(clust_cat,self.qmin)

        clust_cat = nemoOutputDir + fitsfile 
        if self.simtest or self.simpars:
            print("mock catalog")
            self.clst_z,self.clst_zerr,self.clst_y0,self.clst_y0err = read_mock_cat(clust_cat,self.qmin)
        else:
            print("real catalog")
            self.clst_z,self.clst_zerr,self.clst_y0,self.clst_y0err = read_clust_cat(clust_cat,self.qmin)

        self.rms_noise_map  = read_MJH_noisemap(FilterNoiseMapFile,MaskMapFile)
        print ('Number of clusters',len(self.clst_zerr))
        #self.wcs=astWCS.WCS(FilterNoiseMapFile) 
        #self.clst_RA,self.clst_DEC,
        #self.clst_xmapInd,self.clst_ymapInd = self.Find_nearest_pixel_ind(self.clst_RA,self.clst_DEC)

        self.num_noise_bins = 10
        self.area_rads = old_div(987.5,41252.9612) # fraction of sky - ACTPol D56-equ specific
        self.LgY = np.arange(-6,-3,0.01)

        count_temp,bin_edge =np.histogram(np.log10(self.rms_noise_map[self.rms_noise_map>0]),bins=self.num_noise_bins)
        self.frac_of_survey = count_temp*1.0 / np.sum(count_temp)
        self.thresh_bin = 10**(old_div((bin_edge[:-1] + bin_edge[1:]),2.))

    def Find_nearest_pixel_ind(self,wcs,RADeg,DECDeg):
        xx = np.array([])
        yy = np.array([])
        for ra, dec in zip(RADeg,DECDeg):
            x,y = wcs.wcs2pix(ra,dec)
            np.append(xx,np.round(x))
            np.append(yy,np.round(y))
        #return [np.round(x),np.round(y)]
        return np.round(xx),np.round(yy)

    def PfuncY(self,YNoise,M,z_arr,param_vals):
        LgY = self.LgY
        
        P_func = np.outer(M,np.zeros([len(z_arr)]))
        M_arr =  np.outer(M,np.ones([len(z_arr)]))

        for i in range(z_arr.size):
            P_func[:,i] = self.P_of_gt_SN(LgY,M_arr[:,i],z_arr[i],YNoise,param_vals)
        return P_func

    def P_Yo(self, LgY, M, z,param_vals):
        #M500c has 1/h factors in it
        Ma = np.outer(M,np.ones(len(LgY[0,:])))
        Om = old_div((param_vals['omch2'] + param_vals['ombh2']), (old_div(param_vals['H0'],100.))**2)
        OL = 1. - Om
        Ytilde, theta0, Qfilt =simsTools.y0FromLogM500(np.log10(param_vals['massbias']*Ma/(old_div(param_vals['H0'],100.))), z, self.tckQFit,sigma_int=param_vals['scat'],B0=param_vals['yslope'], H0 = param_vals['H0'], OmegaM0 = Om, OmegaL0 = OL)
        Y = 10**LgY
        numer = -1.*(np.log(Y/Ytilde))**2
        ans = 1./(param_vals['scat'] * np.sqrt(2*np.pi)) * np.exp(numer/(2.*param_vals['scat']**2))
        return ans

    def Y_erf(self,Y,Ynoise):
        qmin = self.qmin  # fixed 
        #Gaussian
        ans = 0.5 * (1. + special.erf((Y - qmin*Ynoise)/(np.sqrt(2.)*Ynoise)))
        #Heavy side
        #ans = Y*0.0
        #ans[Y - qmin*Ynoise > 0] = 1.
        return ans

    def P_of_gt_SN(self,LgY,MM,zz,Ynoise,param_vals):
        Y = 10**LgY
        sig_thresh = np.outer(np.ones(len(MM)),self.Y_erf(Y,Ynoise))
        LgYa = np.outer(np.ones(len(MM)),LgY)
        P_Y = np.nan_to_num(self.P_Yo(LgYa,MM,zz,param_vals))
        ans = np.trapz(P_Y*sig_thresh,LgY,np.diff(LgY),axis=1)
        return ans

    def P_of_Y_per(self,LgY,MM,zz,Y_c,Y_err,param_vals):
        P_Y_sig = np.outer(np.ones(len(MM)),self.Y_prob(Y_c,LgY,Y_err))
        LgYa = np.outer(np.ones(len(MM)),LgY)
        P_Y = np.nan_to_num(self.P_Yo(LgYa,MM,zz,param_vals))
        ans = np.trapz(P_Y*P_Y_sig,LgY,np.diff(LgY),axis=1)
        return ans

    def Y_prob (self,Y_c,LgY,YNoise):
        Y = 10**(LgY)
        ans = gaussian(Y,Y_c,YNoise)
        return ans

    def Pfunc_per(self,MM,zz,Y_c,Y_err,param_vals):
        LgY = self.LgY
        LgYa = np.outer(np.ones(len(MM)),LgY)
        P_Y_sig = self.Y_prob(Y_c,LgY,Y_err)
        P_Y = np.nan_to_num(self.P_Yo(LgYa,MM,zz,param_vals))
        ans = np.trapz(P_Y*P_Y_sig,LgY,np.diff(LgY),axis=1)
        return ans

    def Pfunc_per_zarr(self,MM,z_arr,Y_c,Y_err,int_HMF,param_vals):
        LgY = self.LgY

        P_func = np.outer(MM,np.zeros([len(z_arr)]))
        M_arr =  np.outer(MM,np.ones([len(z_arr)]))
        M200 = np.outer(MM,np.zeros([len(z_arr)]))
        for i in range(z_arr.size):
            P_func[:,i] = self.P_of_Y_per(LgY,M_arr[:,i],z_arr[i],Y_c,Y_err,param_vals)
            M200[:,i] = int_HMF.cc.Mass_con_del_2_del_mean200(self.HMF.M.copy(),500,z_arr[i])
        return P_func,M200

    def Ntot_survey(self,int_HMF,fsky,Ythresh,param_vals):

        z_arr = self.HMF.zarr.copy()        
        Pfunc = self.PfuncY(Ythresh,self.HMF.M.copy(),z_arr,param_vals)
        dn_dzdm = int_HMF.dn_dM(int_HMF.M200,200.)
        #print Pfunc
        N_z = np.trapz(dn_dzdm*Pfunc,dx=np.diff(int_HMF.M200,axis=0),axis=0)
        Ntot = np.trapz(N_z*int_HMF.dVdz,dx=np.diff(z_arr))*4.*np.pi*fsky
        return Ntot

    def Prob_per_cluster(self,int_HMF,cluster_props,dn_dzdm_int,param_vals):
        c_z, c_zerr, c_y, c_yerr = cluster_props
        if (c_zerr > 0):
            z_arr = np.arange(-3.*c_zerr,(3.+0.1)*c_zerr,c_zerr) + c_z
            Pfunc_ind,M200 = self.Pfunc_per_zarr(int_HMF.M.copy(),z_arr,c_y,c_yerr,int_HMF,param_vals)
            dn_dzdm = dn_dzdm_int(z_arr,np.log10(int_HMF.M.copy()))
            N_z_ind = np.trapz(dn_dzdm*Pfunc_ind,dx=np.diff(M200,axis=0),axis=0)
            N_per = np.trapz(N_z_ind*gaussian(z_arr,c_z,c_zerr),dx=np.diff(z_arr))
            ans = N_per            
        else:
            Pfunc_ind = self.Pfunc_per(int_HMF.M.copy(),c_z, c_y, c_yerr,param_vals)
            #print "PFunc",Pfunc_ind
            M200 = int_HMF.cc.Mass_con_del_2_del_mean200(int_HMF.M.copy(),500,c_z)
            dn_dzdm = dn_dzdm_int(c_z,np.log10(int_HMF.M.copy()))[:,0]
            #print "dndm", dn_dzdm,dn_dzdm_int(c_z,np.log10(int_HMF.M.copy()))
            #print "M200", M200
            N_z_ind = np.trapz(dn_dzdm*Pfunc_ind,dx=np.diff(M200,axis=0),axis=0)
            ans = N_z_ind
        return ans

    def lnprior(self,theta,parlist,priorval,priorlist):
        param_vals = alter_fparams(self.fparams,parlist,theta)
        prioravg = priorval[0,:]
        priorwth = priorval[1,:]
        lnp = 0.
        for k,prioravg in enumerate(prioravg):
            lnp += np.log(gaussian(param_vals[priorlist[k]],prioravg,priorwth[k],noNorm=True))

        try:
            if ((param_vals['scat'] < 0) or (param_vals['tau'] < 0)) :
                lnp += -np.inf
        except:
            pass
        
        if (self.simpars):
            pars = ['omch2','ombh2','H0','As','ns']
            mins = [0.001,0.005,40.,7.389056098930651e-10,0.8]
            maxs = [0.99,0.1,100.,5.459815003314424e-09,1.2]
        else:
            pars = ['omch2','ombh2','H0','As','ns','massbias','yslope','scat']
            mins = [0.001,0.005,40.,7.389056098930651e-10,0.8,0.2,-0.6,0.001 ]
            maxs = [0.99,0.1,100.,5.459815003314424e-09,1.2,1.4,0.6,0.8 ]

        for k,par in enumerate(pars):
            if param_vals[par]<mins[k] or param_vals[par]>maxs[k]: lnp += -np.inf

        return lnp


    def lnlike(self,theta,parlist):
        
        param_vals = alter_fparams(self.fparams,parlist,theta)
        for key in self.fix_params:
            if key not in list(param_vals.keys()): param_vals[key] = self.fix_params[key]

        print (param_vals)
        int_cc = ClusterCosmology(param_vals,self.constDict,clTTFixFile=self.clttfile) # internal HMF call
        int_HMF = Halo_MF(int_cc,self.mgrid,self.zgrid) # internal HMF call
        self.s8 = int_HMF.cc.s8

        if np.nan_to_num(self.s8)<0.1 or np.nan_to_num(self.s8)>10. or not(np.isfinite(self.s8)):
            self.s8 = 0.
        #     return -np.inf
        
        #dndm_int = int_HMF.inter_dndm(200.) # delta = 200
        dndm_int = int_HMF.inter_dndmLogm(200.) # delta = 200
        cluster_prop = np.array([self.clst_z,self.clst_zerr,self.clst_y0*1e-4,self.clst_y0err*1e-4])

        if self.test:
            Ntot = 60.
        else:
            Ntot = 0.
            for i in range(len(self.frac_of_survey)):
                Ntot += self.Ntot_survey(int_HMF,self.area_rads*self.frac_of_survey[i],self.thresh_bin[i],param_vals)
        #print 'NTOT', Ntot
        Nind = 0
        #Nind2 = 1.
        for i in range(len(self.clst_z)):
            
            N_per = self.Prob_per_cluster(int_HMF,cluster_prop[:,i],dndm_int,param_vals)
            #if (i < 3):
                #print np.log(N_per)
            Nind = Nind + np.log(N_per)
            #Nind2 *= N_per
            #print N_per
        print(-Ntot, Nind, -Ntot + Nind, theta)#, np.log(np.exp(-Ntot)*Nind2)
        return -Ntot + Nind

    def lnprob(self,theta, parlist, priorval, priorlist):
        if not (self.simtest):
            lp = self.lnprior(theta, parlist, priorval, priorlist)
            if not np.isfinite(lp):
                return -np.inf, 0.
        else:
            lp = 0
        lnlike = self.lnlike(theta, parlist)
        return lp + lnlike,np.nan_to_num(self.s8)

class MockCatalog(object):
    def __init__(self,iniFile,parDict,nemoOutputDir,noiseFile,params,parlist,mass_grid_log=None,z_grid=None,randoms=False):

        Config = SafeConfigParser()
        Config.optionxform=str
        Config.read(iniFile)

        if mass_grid_log:
            logm_min,logm_max,logm_spacing = mass_grid_log
        else:
            logm_min = 12.7
            logm_max = 15.72
            logm_spacing = 0.04
        if z_grid:
            zmin,zmax,zdel = z_grid
        else:
            zmin = 0.0
            zmax = 2.01
            zdel = 0.1



        self.fparams = {}
        for (key, val) in Config.items('params'):
            if ',' in val:
                param, step = val.split(',')
                self.fparams[key] = float(param)
            else:
                self.fparams[key] = float(val)

        self.param_vals = alter_fparams(self.fparams,parlist,params)

        bigDataDir = Config.get('general','bigDataDirectory')
        self.clttfile = Config.get('general','clttfile')
        self.constDict = dict_from_section(Config,'constants')

        if mass_grid_log:
            logm_min,logm_max,logm_spacing = mass_grid_log
        else:
            logm_min = 12.7
            logm_max = 15.72
            logm_spacing = 0.04
        if z_grid:
            zmin,zmax,zdel = z_grid
        else:
            zmin = 0.0
            zmax = 2.01
            zdel = 0.1
        
        if randoms:
            self.rand = 1
        else:
            self.rand = 0

        self.mgrid = np.arange(logm_min,logm_max,logm_spacing)
        self.zgrid = np.arange(zmin,zmax,zdel)

        self.Medges = 10.**self.mgrid
        self.Mcents = (self.Medges[1:]+self.Medges[:-1])/2.
        self.Mexpcents = np.log10(self.Mcents)
        self.zcents = (self.zgrid[1:]+self.zgrid[:-1])/2.

        self.cc = ClusterCosmology(self.param_vals,self.constDict,clTTFixFile=self.clttfile)
        self.HMF = Halo_MF(self.cc,self.mgrid,self.zgrid)

        self.diagnosticsDir=nemoOutputDir+"diagnostics"
        self.filteredMapsDir=nemoOutputDir+"filteredMaps"
        self.tckQFit=simsTools.fitQ(parDict, self.diagnosticsDir, self.filteredMapsDir)
        FilterNoiseMapFile = nemoOutputDir + noiseFile
        MaskMapFile = self.diagnosticsDir + '/areaMask.fits'

        self.rms_noise_map = read_MJH_noisemap(FilterNoiseMapFile,MaskMapFile)
        
        self.wcs=astWCS.WCS(FilterNoiseMapFile)

        self.fsky = 987.5/41252.9612 # in rads ACTPol D56-equ specific
        self.scat_val = 0.2
        self.seedval = np.int(np.round(time.time())) #1

    def Total_clusters(self,fsky):
        Nz = self.HMF.N_of_z()
        print (np.trapz(self.HMF.N_of_z_500()*fsky,dx=np.diff(self.HMF.zarr)))
        ans = np.trapz(Nz*fsky,dx=np.diff(self.HMF.zarr))
        return ans

    def Total_clusters_check(self,fsky):
        
        Marr = np.outer(self.Mcents,np.ones(len(self.HMF.zarr)))
        Medgearr = np.outer(self.Medges,np.ones(len(self.HMF.zarr)))
        dn_dzdm = self.HMF.N_of_Mz(Marr,200)
        N_z = np.zeros(self.HMF.zarr.size)
        for i in range(self.HMF.zarr.size):
            N_z[i] = np.dot(dn_dzdm[:,i],np.diff(Medgearr[:,i]))
        
        N_z *= 4.*np.pi
        ans = np.trapz(N_z*fsky,dx=np.diff(self.HMF.zarr))
        #print ('test diff z',np.diff(self.HMF.zarr))
        return ans

    def create_basic_sample(self,fsky):
        '''
        Create simple mock catalog of Mass and Redshift by sampling the mass function
        '''
        #if (self.rand):
        #    Ntot100 = np.int32(np.ceil(self.Total_clusters(fsky))*4.) ## Note for randoms increasing the number density by factor of 100
        #else:
        #    Ntot100 = np.int32(np.ceil(old_div(self.Total_clusters(fsky), 100.))) ## Note the default number of walkers in mcsample_mf is 100 

        #mlim = [np.min(self.mgrid),np.max(self.mgrid)]
        #zlim = [np.min(self.zgrid),np.max(self.zgrid)]

        #old MCMC
        #samples = self.HMF.mcsample_mf(200.,Ntot100,mthresh = mlim,zthresh = zlim)
        #return samples[:,0],samples[:,1]

        Ntot100 = self.Total_clusters(fsky) # np.int32(np.ceil(self.Total_clusters(fsky))) 
        Ntot = np.int32(np.random.poisson(Ntot100))
        print ("Mock cat gen internal counts and Poisson draw",Ntot100,Ntot)

        zsamps, msamps = self.HMF.cpsample_mf(200.,Ntot) 
        #print (zsamps, msamps) 
        return zsamps, msamps

    def create_basic_sample_Mat(self,fsky):
        '''                                                                                                                                                               Create simple mock catalog of Mass and Redshift by sampling the mass function                                                                                     '''
        nmzdensity = HMF.N_of_Mz(self.HMF.M200,200.)
        Ndz = np.multiply(nmzdensity,np.diff(self.zgrid).reshape((1,self.zgrid.size-1)))
        Nmz = np.multiply(Ndz,np.diff(10**self.mgrid).reshape((self.mgrid.size-1,1))) * 4.* np.pi
        Ntot = Nmz.sum() * fsky

        print ("fsky test",Ntot, np.int32(np.ceil(self.Total_clusters(fsky))))

        np.random.seed(self.seedval)
        nclusters = int(np.random.poisson(Ntot)) #if poisson else int(self.ntot)
        mzs = np.zeros((nclusters,2),dtype=np.float32)

        msamps = np.zeros((nclusters),dtype=np.float32)
        zsamps = np.zeros((nclusters),dtype=np.float32)
        print("Generating Nmz catalog...")
        for i in range(nclusters):
            linear_idx = np.random.choice(self.Nmz.size, p=self.Nmz.ravel()/float(self.Nmz.sum()))
            x, y = np.unravel_index(linear_idx, self.Nmz.shape)
            # mzs[i,0] = self.Mexpcents[x]                                                                                         
            # mzs[i,1] = self.zcents[y]                                                                                            
            msamps = np.random.uniform(self.Mexpcents[x].min(),self.Mexpcents[x].max())
            zsamps = np.random.uniform(self.zcents[y].min(),self.zcents[y].max())

        return zsamps, msamps

    def plot_basic_sample(self,fname='default_mockcat.png',):
        fsky = self.fsky
        sampZ,sampM = self.create_basic_sample(fsky)
        plt.figure()
        plt.plot(sampZ,sampM,'x') 
        plt.savefig(fname, bbox_inches='tight',format='png')  
        return sampZ,sampM

    def create_obs_sample(self,fsky):
        
        #include observational effects like scatter and noise into the detection of clusters
        sampZ,sampM = self.create_basic_sample(fsky)
        nsamps = len(sampM)

        Ytilde = sampM * 0.0
        
        Om = old_div((self.param_vals['omch2'] + self.param_vals['ombh2']), (old_div(self.param_vals['H0'],100.))**2)
        OL = 1.-Om 
        print("Omega_M", Om)

        #the function call now includes cosmological dependences
        for i in range(nsamps):
            Ytilde[i], theta0, Qfilt = simsTools.y0FromLogM500(np.log10(self.param_vals['massbias']*10**sampM[i]/(old_div(self.param_vals['H0'],100.))), sampZ[i], self.tckQFit,sigma_int=self.param_vals['scat'],B0=self.param_vals['yslope'], H0 = self.param_vals['H0'], OmegaM0 = Om, OmegaL0 = OL)
        #add scatter
        np.random.seed(self.seedval)
        ymod = np.exp(self.scat_val * np.random.randn(nsamps))
        sampY0 = Ytilde*ymod
        
        #calculate noise for a given object for a random place on the map and save coordinates

        np.random.seed(self.seedval+1)
        nmap = self.rms_noise_map #[::-1,:]
        
        ylims = nmap.shape[0]
        xlims = nmap.shape[1]
        xsave = np.array([])
        ysave = np.array([])
        sampY0err = np.array([])
        count = 0

        while count < nsamps:
            ytemp = np.int32(np.floor(np.random.uniform(0,ylims)))
            xtemp = np.int32(np.floor(np.random.uniform(0,xlims)))
            if nmap[ytemp,xtemp] > 0:
                count += 1
                xsave = np.append(xsave,xtemp)
                ysave = np.append(ysave,ytemp)
                sampY0err = np.append(sampY0err,nmap[ytemp,xtemp])
        return xsave,ysave,sampZ,sampY0,sampY0err,old_div(sampY0,sampY0err),sampM

    def plot_obs_sample(self,filename1='default_mockobscat',filename2='default_obs_mock_footprint'):
        fsky = self.fsky
        xsave,ysave,sampZ,sampY0,sampY0err,SNR,sampM = self.create_obs_sample(fsky)
        ind = np.where(SNR >= 5.6)[0]
        plt.figure()
        plt.plot(sampZ,sampM,'x')
        plt.plot(sampZ[ind],sampM[ind],'o')
        plt.savefig(filename1+'.png', bbox_inches='tight',format='png')

        nmap = self.rms_noise_map # np.flipud(self.rms_noise_map)#[::-1,:]
        plt.figure(figsize=(40,6))
        plt.imshow(nmap,cmap='Blues')
        plt.plot(xsave[ind],ysave[ind],'ko')
        plt.colorbar()
        plt.savefig(filename2+'.png', bbox_inches='tight',format='png')

        return xsave,ysave,sampZ,sampY0,sampY0err,SNR,sampM

    def write_test_cat_toFits(self, filedir,filename):
        '''
        Write out the catalog
        '''
        f1 = filedir+filename+'_testsamp_mz'
        sampZ,sampM = self.plot_basic_sample(f1)
        sampZerr = sampZ * 0.0
        sampMerr = sampM * 0.0

        #ind = np.where(10**sampM >= 2.0*10**(np.min(self.mgrid)))[0]

        clusterID = np.arange(len(sampM)).astype(str)
        hdu = fits.BinTableHDU.from_columns(
            [fits.Column(name='Cluster_ID', format='20A', array=clusterID),
             fits.Column(name='redshift', format='E', array=sampZ),
             fits.Column(name='redshift_err', format='E', array=sampZerr),
             fits.Column(name='Mass', format='E', array=sampM),
             fits.Column(name='Mass_err', format='E', array=sampMerr),])

        hdu.writeto(filedir+filename+'.fits',overwrite=True)

        return 0

    def test_cat_samp(self, filedir,filename, mcut):
        '''
        Write out the catalog
        '''
        f1 = filedir+filename+'_testsamp_mz'
        sampZ,sampM = self.plot_basic_sample(f1)

        print (sampM) 

        return 0

    def test_Mockcat_Nums(self, mmin):
        '''
        Quick write out of the number clusters in the mock catalog, for testing
        '''
        sampZ,sampM = self.create_basic_sample(self.fsky)
        ind = np.where(sampM >= mmin)[0]

        return len(ind)

    def write_obs_cat_toFits(self, filedir,filename):
        '''
        Write out the catalog
        '''
        f1 = filedir+filename+'_mockobscat'
        f2 = filedir+filename+'_obs_mock_footprint'

        xsave,ysave,z,sampY0,sampY0err,SNR,sampM = self.plot_obs_sample(filename1=f1,filename2=f2)

        ind = np.where(SNR >= 4.0)[0]
        ind2 = np.where(SNR >= 5.6)[0]
        print("number of clusters SNR >= 5.6", len(ind2), " SNR >= 4.0",len(ind))

        RAdeg = xsave*0.0
        DECdeg = ysave*0.0
        count = 0
        for xsv, ysv in zip(xsave,ysave):
            ra,dec = self.wcs.pix2wcs(xsv,ysv)
            RAdeg[count] = ra
            DECdeg[count] = dec
            count +=1

        clusterID = ind.astype(str)
        hdu = fits.BinTableHDU.from_columns(
            [fits.Column(name='Cluster_ID', format='20A', array=clusterID),
             fits.Column(name='x_ind', format='E', array=xsave[ind]),
             fits.Column(name='y_ind', format='E', array=ysave[ind]),
             fits.Column(name='RA', format='E', array=RAdeg[ind]),
             fits.Column(name='DEC', format='E', array=DECdeg[ind]),
             fits.Column(name='redshift', format='E', array=z[ind]),
             fits.Column(name='redshiftErr', format='E', array=z[ind]*0.0),
             fits.Column(name='fixed_y_c', format='E', array=sampY0[ind]*1e4),
             fits.Column(name='err_fixed_y_c', format='E', array=sampY0err[ind]*1e4),
             fits.Column(name='fixed_SNR', format='E', array=SNR[ind]),
             fits.Column(name='M500', format='E', array=sampM[ind]),])

        hdu.writeto(filedir+filename+'.fits',overwrite=True)

        return 0

    def Add_completeness(self,filedir,filename,compfile,zcut=False):
        '''
        Add in observing and filter completeness to the selection the mock catalogs
        '''

        fitsfile = filedir+filename+'.fits'
        ID,x,y,ra,dec,z,zerr,Y0,Y0err,SNR,M500 = read_full_mock_cat(fitsfile)
        
        rands = np.random.uniform(0,1,len(z))        
        
        compvals = np.load(compfile)
        inter = interp2d(compvals['log10M500c'],compvals['z'],compvals['M500Completeness'],kind='cubic',fill_value=0)
        use = 0.0*z

        for ii in range(len(z)):
            comp = inter(M500[ii],z[ii])
            if (comp > rands[ii]):
                use[ii] = 1

        if (zcut):
            ind = np.where((z < zcut)*(use > 0))[0]

        print("number of clusters SNR >= 4.0 plus completeness",len(ind))
        fitsout = filedir+filename+'_comp_added.fits'

        hdu = fits.BinTableHDU.from_columns(
            [fits.Column(name='Cluster_ID', format='20A', array=ID[ind]),
             fits.Column(name='x_ind', format='E', array=x[ind]),
             fits.Column(name='y_ind', format='E', array=y[ind]),
             fits.Column(name='RA', format='E', array=ra[ind]),
             fits.Column(name='DEC', format='E', array=dec[ind]),
             fits.Column(name='redshift', format='E', array=z[ind]),
             fits.Column(name='redshiftErr', format='E', array=zerr[ind]),
             fits.Column(name='fixed_y_c', format='E', array=Y0[ind]),
             fits.Column(name='err_fixed_y_c', format='E', array=Y0err[ind]),
             fits.Column(name='fixed_SNR', format='E', array=SNR[ind]),
             fits.Column(name='M500', format='E', array=M500[ind]),])

        hdu.writeto(fitsout,overwrite=True)

        return 0

class clustLikeTest(object):
    def __init__(self,iniFile,test_cat_file,fix_params,mmin=14.3):

        self.fix_params = fix_params
        Config = SafeConfigParser()
        Config.optionxform=str
        Config.read(iniFile)

        self.fparams = {}
        for (key, val) in Config.items('params'):
            if ',' in val:
                param, step = val.split(',')
                self.fparams[key] = float(param)
            else:
                self.fparams[key] = float(val)

        bigDataDir = Config.get('general','bigDataDirectory')
        self.clttfile = Config.get('general','clttfile')
        self.constDict = dict_from_section(Config,'constants')

        logm_min = 14.0
        logm_max = 15.702
        logm_spacing = 0.01
        self.mgrid = np.arange(logm_min,logm_max,logm_spacing)
        self.zgrid = np.arange(0.1,2.001,0.05)

        self.cc = ClusterCosmology(self.fparams,self.constDict,clTTFixFile=self.clttfile)
        self.HMF = Halo_MF(self.cc,self.mgrid,self.zgrid)

        self.fsky = old_div(987.5,41252.9612)
        self.mmin = mmin
        clust_cat = test_cat_file + '.fits' 
        self.clst_z,self.clst_zerr,self.clst_m,self.clst_merr = read_test_mock_cat(clust_cat,self.mmin)
        #self.clst_z,self.clst_m = read_mock_test_cat(clust_cat,self.mmin)

    def PfuncM(self,Mt,Marr):
        ans = Marr * 0.0
        ans[Marr >= Mt] = 1.0
        return ans

    def PfuncM_per(self,Mt,m_c):
        ans = 0
        if (m_c >= Mt):
            ans = 1.
        return ans

    def PfuncM_per_zarr(self,Mt,m_c,z_arr):
        ans = 0*z_arr
        if (m_c >= Mt):
            ans[:] = 1.
        return ans

    def Ntot_survey(self,int_HMF,fsky):
        z_arr = self.HMF.zarr.copy()
        Pfunc = np.outer(self.PfuncM(10**self.mmin,self.HMF.M.copy()),np.ones(len(z_arr)))
        #print Pfunc.shape
        dn_dzdm = int_HMF.dn_dM(int_HMF.M200,200.)
        #print "mass", int_HMF.M200
        #print dn_dzdm.shape
        #print "dndm test", dn_dzdm
        N_z = np.trapz(dn_dzdm*Pfunc,dx=np.diff(int_HMF.M200,axis=0),axis=0)
        Ntot = np.trapz(N_z*int_HMF.dVdz,dx=np.diff(z_arr))*4.*np.pi*fsky
        return Ntot

    def Ntot_survey_TEST(self,int_HMF,fsky):
        z_arr = self.HMF.zarr.copy()
        ind = np.where(self.HMF.M.copy() >= (10**self.mmin)*0.999)[0]
        #print np.min(self.HMF.M.copy()[ind]),10**self.mmin
        #print 10**self.mgrid
        #print self.HMF.M.copy(), 10**self.mmin

        #print len(ind), "of" , len(self.HMF.M.copy())
        dn_dzdm = int_HMF.dn_dM(int_HMF.M200,200.)
        #print "dndm test", dn_dzdm
        N_z = np.trapz(dn_dzdm[ind,:],dx=np.diff(int_HMF.M200[ind,:],axis=0),axis=0)
        #print "N_z test", N_z
        Ntot = np.trapz(N_z*int_HMF.dVdz,dx=np.diff(z_arr))*4.*np.pi*fsky
        return Ntot

    def Prob_per_cluster(self,int_HMF,cluster_props,dn_dzdm_int):
        c_z, c_zerr, c_m, c_merr = cluster_props
        if (c_zerr > 0):
            z_arr = np.arange(-3.*c_zerr,(3.+0.1)*c_zerr,c_zerr) + c_z
            dn_dzdm = dn_dzdm_int(z_arr,np.log10(c_m))
            N_per = np.trapz(dn_dzdm*gaussian(z_arr,c_z,c_zerr),dx=np.diff(z_arr))
            ans = N_per
        else:
            dn_dzdm = dn_dzdm_int(c_z,np.log10(c_m))
            ans = dn_dzdm
            #print dn_dzdm
            #kmin=1e-4
            #kmax=5.
            #knum=200

            #int_kh, int_pk = int_HMF._pk(c_z,kmin,kmax,knum)
            #delts = int_HMF.zarr*0.0 + 200.
            #print c_m
            #dn_dlnm = dn_dlogM(np.array([c_m,c_m*1.01]),c_z,int_HMF.cc.rhoc0om,200,int_kh,int_pk,'comoving')
            #print dn_dlogM(np.array([c_m,c_m*1.01]),int_HMF.zarr,int_HMF.cc.rhoc0om,delts,int_HMF.kh,int_HMF.pk,'comoving')
            #print dn_dlnm

            #print int_HMF.dn_dM(np.outer(np.array([1e14*1.01,1e14*1.05]),np.ones(len(int_HMF.zarr))),200.)
            #print int_HMF.M200[0:2,0]
            #m1 = int_HMF.M200[0,0]
            #m2 = int_HMF.M200[1,0]
            #print m1,m2,c_m
            #print int_HMF.dn_dM(np.outer(np.array([m1*1.01,c_m*1.01]),np.ones(len(int_HMF.zarr))),200.)
            #print int_HMF.dn_dM(int_HMF.M200[0:2,:],200.)
            #print int_HMF.dn_dM(np.outer(np.array([c_m*1.01,1e14*1.01]),np.ones(len(int_HMF.zarr))),200.)
            #blahs = dn_dlnm/np.array([c_m,c_m])
            #print blahs 
        return ans

    def lnlike(self,theta,parlist):

        param_vals = alter_fparams(self.fparams,parlist,theta)
        for key in self.fix_params:
            if key not in list(param_vals.keys()): param_vals[key] = self.fix_params[key]

        int_cc = ClusterCosmology(param_vals,self.constDict,clTTFixFile=self.clttfile) # internal HMF call
        int_HMF = Halo_MF(int_cc,self.mgrid,self.zgrid) # internal HMF call
        self.s8 = int_HMF.cc.s8
        if np.nan_to_num(self.s8)<0.1 or np.nan_to_num(self.s8)>10. or not(np.isfinite(self.s8)):
            self.s8 = 0.

        #dndm_int = int_HMF.inter_dndmLogm(200.) # delta = 200
        dndm_int = int_HMF.inter_mf_logM(200.) # delta = 200
        cluster_prop = np.array([self.clst_z,self.clst_zerr,10**self.clst_m,self.clst_merr])

        Ntot = self.Ntot_survey(int_HMF,self.fsky)
        print("Ntot comparion, and catalog")
        print(self.Ntot_survey_TEST(int_HMF,self.fsky), Ntot, len(self.clst_z))

        Nind = 0
        for i in range(len(self.clst_z)):
            N_per = self.Prob_per_cluster(int_HMF,cluster_prop[:,i],dndm_int)
            Nind = Nind + np.log(N_per)

        print("-NTOT, Nind, Total, As")
        print(-Ntot, Nind, -Ntot + Nind, theta)
        return -Ntot + Nind

    def lnprob(self,theta, parlist):
        lnlike = self.lnlike(theta, parlist)
        return lnlike,np.nan_to_num(self.s8)
