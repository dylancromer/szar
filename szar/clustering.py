from __future__ import print_function
from __future__ import absolute_import
from __future__ import division
from future import standard_library
standard_library.install_aliases()
from builtins import object
import numpy as np
#from orphics.cosmology import Cosmology
from szar.counts import ClusterCosmology,Halo_MF
from szar.szproperties import SZ_Cluster_Model
from . import tinker as tinker
from configparser import SafeConfigParser
from orphics.io import dict_from_section,list_from_config
import pickle as pickle
from scipy.interpolate import interp1d
from scipy.interpolate import UnivariateSpline
#from scipy.integrate import simps

class Clustering(object):
    def __init__(self,iniFile,expName,gridName,version,ClusterCosmology):
        Config = SafeConfigParser()
        Config.optionxform=str
        Config.read(iniFile)

        self.cluster_cosm = ClusterCosmology

        #constants from configuration
        bigDataDir = Config.get('general','bigDataDirectory')
        self.clttfile = Config.get('general','clttfile')
        self.constDict = dict_from_section(Config,'constants')
        self.clusterDict = dict_from_section(Config,'cluster_params')

        #Experimental parameters
        beam = list_from_config(Config,expName,'beams')
        noise = list_from_config(Config,expName,'noises')
        freq = list_from_config(Config,expName,'freqs')
        lknee = list_from_config(Config,expName,'lknee')[0]
        alpha = list_from_config(Config,expName,'alpha')[0]
        self.fsky = Config.getfloat(expName,'fsky')

        #load SZ grid file
        self.mgrid,self.zgrid,siggrid = pickle.load(open(bigDataDir+"szgrid_"+expName+"_"+gridName+ "_v" + version+".pkl",'rb'))

        #self.cluster_cosm = ClusterCosmology(self.fparams,self.constDict,clTTFixFile=self.clttfile)
        self.SZProp = SZ_Cluster_Model(self.cluster_cosm,self.clusterDict,rms_noises = noise,fwhms=beam,freqs=freq,lknee=lknee,alpha=alpha)
        self.HMF = Halo_MF(self.cluster_cosm,self.mgrid,self.zgrid)
        self.HMF.sigN = siggrid.copy()
        #self.dndm_SZ = self.HMF.dn_dmz_SZ(self.SZProp)

    def dvol_dz_fine(self, zs):
        ang_diam_dist = self.HMF.cc.results.angular_diameter_distance(zarr)
        dvol_dz = ang_diam_dist**2 * (1 + zs)**2

        for i in range (zarr.size):
            dV_dz[i] /= (self.HMF.cc.results.h_of_z(zarr[i]))

        dvol_dz *= (self.HMF.cc.H0/100)**3
        return dvol_dz


    def ntilde(self):
        dndm_SZ = self.HMF.dn_dmz_SZ(self.SZProp)
        ans = np.trapz(dndm_SZ,dx=np.diff(self.HMF.M200,axis=0),axis=0)
        return ans


    def ntilde_interpol(self,zarr_int):
        ntil = self.ntilde()
        z_arr = self.HMF.zarr
        f_int = interp1d(z_arr, np.log(ntil),kind='cubic')
        ans = np.exp(f_int(zarr_int))

        return ans


    def b_eff_z(self):
        '''
        effective linear bias wieghted by number density
        '''
        nbar = self.ntilde()

        z_arr = self.HMF.zarr
        dndm_SZ = self.HMF.dn_dmz_SZ(self.SZProp)

        R = tinker.radius_from_mass(self.HMF.M200,self.cluster_cosm.rhoc0om)
        sig = np.sqrt(tinker.sigma_sq_integral(R, self.HMF.pk, self.HMF.kh))

        blin = tinker.tinker_bias(sig,200.)
        beff = np.trapz(dndm_SZ*blin, dx=np.diff(self.HMF.M200, axis=0), axis=0)/nbar

        try:
            a_bias = self.cluster_cosm.paramDict['abias']
        except KeyError:
            print("Using implicit a_bias value")
            a_bias = 1.

        return a_bias * beff


    def non_linear_scale(self,z,M200):

        zdiff = np.abs(self.HMF.zarr - z)
        use_z = np.where(zdiff == np.min(zdiff))[0]

        R = tinker.radius_from_mass(M200,self.cluster_cosm.rhoc0om)

        sig = np.sqrt(tinker.sigma_sq_integral(R, self.HMF.pk[use_z,:], self.HMF.kh))

        print(sig.shape)
        print(self.HMF.kh.shape)
        sig1 = sig[0,:]
        print(sig1)
        sigdiff = np.abs(sig1 - 1.)
        use_sig = np.where(sigdiff == np.min(sigdiff))[0]
        print(use_sig)
        return 1./(R[use_sig]), sig1[use_sig],self.HMF.zarr[use_z]


    def Norm_Sfunc(self):
        nbar = self.ntilde()
        ans = self.HMF.dVdz*nbar**2*np.diff(self.HMF.zarr_edges)
        return ans


    def fine_sfunc(self, nsubsamples):
        zs = self.HMF.zarr
        zgridedges = self.HMF.zarr_edges

        fine_zgrid = np.empty((zs.size, nsubsamples))
        for i in range(zs.size):
            fine_zgrid[i,:] = np.linspace(zgridedges[i], zgridedges[i+1], nsubsamples)

        fine_zgrid = fine_zgrid[1:-1]

        ntils = self.ntilde_interpol(fine_zgrid)
        dvdz = np.array([self.dvol_dz_fine(zs) for zs in fine_zgrid])

        dz = fine_zgrid[0,1] - fine_zgrid[0,0]

        assert np.allclose(dz * np.ones(tuple(np.subtract(fine_zgrid.shape, (0,1)))),  np.diff(fine_zgrid,axis=1), rtol=1e-3)

        integral = np.trapz(dvdz * ntils**2, dx=dz)
        return integral


    def v0(self, nsubsamples):
        zs = self.HMF.zarr
        zgridedges = self.HMF.zarr_edges

        fine_zgrid = np.empty((zs.size, nsubsamples))
        for i in range(zs.size):
            fine_zgrid[i,:] = np.linspace(zgridedges[i], zgridedges[i+1], nsubsamples)

        fine_zgrid = fine_zgrid[1:-1]
        dvdz = np.array([self.dvol_dz_fine(zs) for zs in fine_zgrid])
        dz = fine_zgrid[0,1] - fine_zgrid[0,0]

        assert np.allclose(dz * np.ones(tuple(np.subtract(fine_zgrid.shape, (0,1)))),  np.diff(fine_zgrid,axis=1), rtol=1e-3)

        integral = np.trapz(dvdz, dx=dz)
        integral *= 4 * np.pi * self.fsky
        return integral


    def ps_tilde(self,mu):
        beff_arr = self.b_eff_z()[..., np.newaxis]
        mu_arr = mu[..., np.newaxis]
        logGrowth = self.cluster_cosm.fgrowth(self.HMF.zarr)

        prefac = (beff_arr.T + logGrowth*mu_arr**2)**2
        prefac = prefac[..., np.newaxis]

        pklin = self.HMF.pk
        pklin = pklin.T
        pklin = pklin[..., np.newaxis]

        ans = np.multiply(prefac,pklin.T).T
        return ans


    def ps_tilde_interpol(self, zarr_int, mu):
        ps_tils = self.ps_tilde(mu)
        zs = self.HMF.zarr
        ks = self.HMF.kh

        n = zs.size
        k = 4 # 5th degree spline
        s = 20.*(n - np.sqrt(2*n))* 1.3 # smoothing factor

        ps_interp = interp1d(zs, ps_tils, axis=1, kind='cubic')
        return ps_interp(zarr_int)


    def ps_bar(self, mu):
        z_arr = self.HMF.zarr
        nbar = self.ntilde()

        prefac =  self.HMF.dVdz*nbar**2*np.diff(z_arr)[2]/self.Norm_Sfunc()
        prefac = prefac[..., np.newaxis]

        ans = np.multiply(prefac, self.ps_tilde(mu).T).T
        return ans


    def fine_ps_bar(self, mu, nsubsamples=100):
        zs = self.HMF.zarr
        ks = self.HMF.kh
        zgridedges = self.HMF.zarr_edges

        values = np.empty((ks.size, zs.size, mu.size))

        fine_zgrid = np.empty((zs.size, nsubsamples))
        for i in range(zs.size):
            fine_zgrid[i,:] = np.linspace(zgridedges[i], zgridedges[i+1], nsubsamples)

        fine_zgrid = fine_zgrid[1:-1]
        ntils = self.ntilde_interpol(fine_zgrid)
        dvdz = np.array([self.dvol_dz_fine(zs) for zs in fine_zgrid])
        prefac = dvdz * ntils**2
        prefac = prefac[..., np.newaxis]
        ps_tils = self.ps_tilde_interpol(fine_zgrid, mu)

        integrand = prefac * ps_tils
        dz = fine_zgrid[0,1] - fine_zgrid[0,0]

        assert np.allclose(dz * np.ones(tuple(np.subtract(fine_zgrid.shape, (0,1)))),  np.diff(fine_zgrid,axis=1), rtol=1e-3)

        integral = np.trapz(integrand, dx=dz, axis=2)
        s_norm = self.fine_sfunc(nsubsamples)[..., np.newaxis]
        values = integral/s_norm
        return values


    def V_eff(self,mu,nsubsamples=100):
        V0 = self.v0( nsubsamples)
        V0 = np.reshape(V0, (V0.size,1))

        nbar = self.ntilde()[1:-1]
        nbar = np.reshape(nbar, (nbar.size,1))

        ps = self.fine_ps_bar(mu, nsubsamples)
        npfact = np.multiply(nbar, ps)
        frac = npfact/(1. + npfact)

        ans = np.multiply(frac**2,V0)
        return ans

