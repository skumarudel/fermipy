
import os
import re
import sys
import copy
import glob
import shutil
import yaml
import numpy as np
import tempfile
import logging

from scipy.interpolate import UnivariateSpline

import matplotlib

try:             os.environ['DISPLAY']
except KeyError: matplotlib.use('Agg')

#matplotlib.interactive(False)
#matplotlib.use('Agg')

import matplotlib.pyplot as plt

import pyLikelihood as pyLike

import astropy.io.fits as pyfits
from astropy import wcs

import fermipy
import fermipy.defaults as defaults
from fermipy.residmap import ResidMapGenerator
from fermipy.utils import AnalysisBase, mkdir, merge_dict, tolist, create_wcs
from fermipy.utils import make_coadd_map, valToBinBounded, valToEdge, write_fits_image
from fermipy.utils import make_psf_mapcube, make_cgauss_mapcube
from fermipy.roi_model import ROIModel, Source
from fermipy.logger import Logger, StreamLogger
from fermipy.logger import logLevel as ll
from fermipy.plotting import ROIPlotter, SEDPlotter, ExtensionPlotter, make_counts_spectrum_plot
from fermipy.config import ConfigManager
from fermipy.irfs import LTCube, PSFModel

# pylikelihood


import GtApp
import FluxDensity
from BinnedAnalysis import BinnedObs
from LikelihoodState import LikelihoodState
from gtutils import BinnedAnalysis, SummedLikelihood
import BinnedAnalysis as ba
#from UpperLimits import UpperLimits


    

norm_parameters = {
    'ConstantValue' : ['Value'],
    'PowerLaw' : ['Prefactor'],
    'PowerLaw2' : ['Integral'],
    'BrokenPowerLaw' : ['Prefactor'],    
    'LogParabola' : ['norm'],
    'PLSuperExpCutoff' : ['Prefactor'],
    'ExpCutoff' : ['Prefactor'],
    'FileFunction' : ['Normalization'],
    }

shape_parameters = {
    'ConstantValue' : [],
    'PowerLaw' : ['Index'],
    'PowerLaw2' : ['Index'],
    'BrokenPowerLaw' : ['Index1','Index2'],    
    'LogParabola' : ['alpha','beta'],    
    'PLSuperExpCutoff' : ['Index1','Cutoff'],
    'ExpCutoff' : ['Index1','Cutoff'],
    'FileFunction' : [],
    }

index_parameters = {
    'ConstantValue' : [],
    'PowerLaw' : ['Index'],
    'PowerLaw2' : ['Index'],
    'BrokenPowerLaw' : ['Index1','Index2'],    
    'LogParabola' : ['alpha','beta'],    
    'PLSuperExpCutoff' : ['Index1','Index2'],
    'ExpCutoff' : ['Index1'],
    'FileFunction' : [],
    }


def get_upper_limit(dlogLike,yval,interpolate=False):

    from scipy.optimize import brentq
    
    if interpolate:    
        s = UnivariateSpline(yval,dlogLike,k=2,s=0)
        sd = s.derivative()
        if np.sign(sd(yval[0])) == -1:
            y0 = yval[0]
        else:
            y0 = brentq(sd,yval[0],yval[-1])
            
        lnlmax = s(y0)
        yval = np.linspace(yval[0],yval[-1],100)
        dlnl = s(yval)-lnlmax
        imax = np.argmax(dlnl)
    else:
        imax = np.argmax(dlogLike)
        y0 = yval[imax]
        lnlmax = dlogLike[imax]
        dlnl = dlogLike-lnlmax

            
    ts = -2*dlnl[0]    
    ul95 = np.interp(cl_to_dlnl(0.95),-dlnl[imax:],yval[imax:])
    err_hi = np.interp(0.5,-dlnl[imax:],yval[imax:]) - yval[imax]
    err_lo = np.nan

    if dlnl[0] < -0.5:
        err_lo = yval[imax] - np.interp(0.5,-dlnl[:imax][::-1],
                                        yval[:imax][::-1]) 
    
#    import matplotlib.pyplot as plt
#    plt.figure()
#    plt.plot(yval,dlnl,marker='o',linestyle='None')
#    plt.plot(np.linspace(0,0.1,1000),s(np.linspace(0,0.1,1000))-lnlmax)
#    plt.plot(np.linspace(0,0.1,1000),s1(np.linspace(0,0.1,1000))-lnlmax)
#    plt.gca().set_ylim(-30,1)
#    plt.gca().grid(True)    
#    plt.gca().axvline(ul95)
#    plt.gca().axvline(y0+err_hi)
#    plt.gca().axhline(-cl_to_dlnl(0.95))
#    plt.show()

    return y0, ul95, err_lo, err_hi, ts
    

def cl_to_dlnl(cl):
    import scipy.special as spfn    
    alpha = 1.0-cl    
    return 0.5*np.power(np.sqrt(2.)*spfn.erfinv(1-2*alpha),2.)    

def run_gtapp(appname,logger,kw):

    logger.info('Running %s'%appname)
#    logger.debug('\n' + yaml.dump(kw))
    filter_dict(kw,None)
    gtapp=GtApp.GtApp(appname)

    for k,v in kw.items(): gtapp[k] = v
    logger.info(gtapp.command())
    stdin, stdout = gtapp.runWithOutput(print_command=False)

    for line in stdout:
        logger.info(line.strip())

    # Capture return code?

def filter_dict(d,val):
    for k, v in d.items():
        if v == val: del d[k]
        
def gtlike_spectrum_to_dict(spectrum):
    """ Convert a pyLikelihood object to a python 
        dictionary which can be easily saved to a file. """
    parameters=pyLike.ParameterVector()
    spectrum.getParams(parameters)
    d = dict(spectrum_type = spectrum.genericName())
    for p in parameters:

        pname = p.getName()
        pval = p.getTrueValue()
        perr = abs(p.error()*p.getScale()) if p.isFree() else np.nan        
        d[pname]= np.array([pval,perr])
        
        if d['spectrum_type'] == 'FileFunction': 
            ff=pyLike.FileFunction_cast(spectrum)
            d['file']=ff.filename()
    return d

   
    

class GTAnalysis(AnalysisBase):
    """High-level analysis interface that internally manages a set of
    analysis component objects.  Most of the functionality of the
    fermiPy package is provided through the methods of this class.
    The class constructor accepts a dictionary that defines the
    configuration for the analysis.  Keyword arguments provided as
    **kwargs can be used to override parameter values in the
    configuration dictionary."""

    defaults = {'logging'    : defaults.logging,
                'fileio'     : defaults.fileio,
                'optimizer'  : defaults.optimizer,
                'binning'    : defaults.binning,
                'selection'  : defaults.selection,
                'model'      : defaults.model,
                'data'       : defaults.data,
                'gtlike'     : defaults.gtlike,
                'mc'         : defaults.mc,
                'residmap'   : defaults.residmap,
                'sed'        : defaults.sed,
                'extension'  : defaults.extension,
                'roiopt'     : defaults.roiopt,
                'run'        : defaults.run,
                'plotting'   : defaults.plotting,
                'components' : (None,'')}

    def __init__(self,config,**kwargs):

        if not isinstance(config,dict):
            config = ConfigManager.create(config)

        super(GTAnalysis,self).__init__(config,**kwargs)

        # Setup directories
        self._rootdir = os.getcwd()
                        
        # Destination directory for output data products
        if self.config['fileio']['outdir'] is not None:
            self._savedir = os.path.join(self._rootdir,
                                         self.config['fileio']['outdir'])
            mkdir(self._savedir)
        else:
            raise Exception('Save directory not defined.')

        # put pfiles into savedir
        os.environ['PFILES']= \
            self._savedir+';'+os.environ['PFILES'].split(';')[-1]

        if self.config['fileio']['logfile'] is None:
            self._config['fileio']['logfile'] = os.path.join(self._savedir,'fermipy')
            
        self.logger = Logger.get(self.__class__.__name__,self.config['fileio']['logfile'],
                                 ll(self.config['logging']['verbosity']))

        self.logger.info('\n' + '-'*80 + '\n' + "This is fermipy version {}.".
                         format(fermipy.__version__))
        self.print_config(self.logger)
        
        # Working directory (can be the same as savedir)
#        if self.config['fileio']['scratchdir'] is not None:
        if self.config['fileio']['usescratch']:
            self._config['fileio']['workdir'] = tempfile.mkdtemp(prefix=os.environ['USER'] + '.',
                                                       dir=self.config['fileio']['scratchdir'])
            self.logger.info('Created working directory: %s'%self.config['fileio']['workdir'])
            self.stage_input()
        else:
            self._config['fileio']['workdir'] = self._savedir
        
        # Setup the ROI definition
        self._roi = ROIModel.create(self.config['selection'],
                                    self.config['model'],
                                    fileio=self.config['fileio'],
                                    logfile=self.config['fileio']['logfile'],
                                    logging=self.config['logging'])
                
        self._like = SummedLikelihood()
        self._components = []
        configs = self.create_component_configs()

        for cfg in configs:
            comp = self._create_component(cfg)
            self._components.append(comp)

        energies = np.zeros(0)
        roiwidths = np.zeros(0)
        binsz = np.zeros(0)
        for c in self.components:
            energies = np.concatenate((energies,c.energies))
            roiwidths = np.insert(roiwidths,0,c.roiwidth)
            binsz = np.insert(binsz,0,c.binsz)
            
        self._ebin_edges = np.sort(np.unique(energies.round(5)))
        self._enumbins = len(self._ebin_edges)-1
        self._roi_model = {
            'roi' : {
                'logLike' : np.nan,
                'Npred'   : 0.0,
                'counts'  : np.zeros(self.enumbins),
                'model_counts'  : np.zeros(self.enumbins),
                'energies'  : np.copy(self.energies),
                'residmap' : {},
                'components' : []
                },
            'sources' : {}
            }
        
        for c in self._components:
            self._roi_model['roi']['components'] += [{'logLike' : np.nan,
                                                      'Npred'   : 0.0,
                                                      'counts'  : np.zeros(c.enumbins),
                                                      'model_counts'  : np.zeros(c.enumbins),
                                                      'energies'  : np.copy(c.energies),
                                                      'residmap' : {}}]
        
        self._roiwidth = max(roiwidths)
        self._binsz = min(binsz)
        self._npix = int(np.round(self._roiwidth/self._binsz))

        self._wcs = create_wcs(self._roi.skydir,
                               coordsys=self.config['binning']['coordsys'],
                               projection=self.config['binning']['proj'],
                               cdelt=self._binsz,crpix=1.0+0.5*(self._npix-1),
                               naxis=3)
        self._wcs.wcs.crpix[2]=1
        self._wcs.wcs.crval[2]=10**self.energies[0]
        self._wcs.wcs.cdelt[2]=10**self.energies[1]-10**self.energies[0]
        self._wcs.wcs.ctype[2]='Energy'

        self._rmg = ResidMapGenerator(self.config['residmap'],self,
                                      fileio=self.config['fileio'],
                                      logging=self.config['logging'])
        
        
    def __del__(self):
        self.stage_output()
        self.cleanup()

    @property
    def roi(self):
        return self._roi
        
    @property
    def like(self):
        """Return the global likelihood object."""
        return self._like

    @property
    def components(self):
        """Return the list of analysis components."""
        return self._components

    @property
    def energies(self):
        return self._ebin_edges

    @property
    def enumbins(self):
        """Return the number of energy bins."""
        return self._enumbins    

    @property
    def npix(self):
        """Return the number of energy bins."""
        return self._npix 

    def _update_roi(self):

        rm = self._roi_model
        
        rm['roi']['model_counts'].fill(0)
        rm['roi']['Npred'] = 0
        for i, c in enumerate(self.components):
            rm['roi']['components'][i]['model_counts'].fill(0)
            rm['roi']['components'][i]['Npred'] = 0

            
        for name in self.like.sourceNames():
            rm['roi']['model_counts'] += rm['sources'][name]['model_counts']
            rm['roi']['Npred'] += np.sum(rm['sources'][name]['model_counts'])

            mc = self.modelCountsSpectrum(name)
            
            for i, c in enumerate(self.components):                
                rm['roi']['components'][i]['model_counts'] += mc[i]
                rm['roi']['components'][i]['Npred'] += np.sum(mc[i])

                
    def add_source(self,name,src_dict,free=False):

        self.logger.info('Adding source ' + name)
        
        if isinstance(src_dict,dict):
            src_dict['name'] = name
            src = self.roi.create_source(src_dict)
        else:
            src = src_dict        
            self.roi.load_source(src)
            
        for c in self.components:
            c.add_source(name,src_dict,free=free)

        self.like.syncSrcParams(name)            
        self.like.model = self.like.components[0].model
            
    def delete_source(self,name,save_template=True):

        self.logger.info('Deleting source ' + name)
        
        for c in self.components:
            c.delete_source(name,save_template=save_template)

        src = self.roi.get_source_by_name(name)        
        self.roi.delete_sources([src])
            
    def create_component_configs(self):
        configs = []

        components = self.config['components']

        common_config = GTBinnedAnalysis.get_config()
        common_config = merge_dict(common_config,self.config)
        
        if components is None:
            cfg = copy.copy(common_config)
            cfg['file_suffix'] = '_00'
            cfg['name'] = '00'      
            configs.append(cfg)
        elif isinstance(components,dict):            
            for i,k in enumerate(sorted(components.keys())):
                cfg = copy.copy(common_config)                
                cfg = merge_dict(cfg,components[k])
                cfg['file_suffix'] = '_' + k
                cfg['name'] = k
                configs.append(cfg)
        elif isinstance(components,list):
            for i,c in enumerate(components):
                cfg = copy.copy(common_config)                
                cfg = merge_dict(cfg,c)
                cfg['file_suffix'] = '_%02i'%i
                cfg['name'] = '%02i'%i
                configs.append(cfg)
        else:
            raise Exception('Invalid type for component block.')

        return configs
                
    def _create_component(self,cfg):
            
        self.logger.info("Creating Analysis Component: " + cfg['name'])

        cfg['fileio']['workdir'] = self.config['fileio']['workdir']
        
        comp = GTBinnedAnalysis(cfg,
                                logging=self.config['logging'])

        return comp

    def stage_output(self):
        """Copy data products to final output directory."""

        extensions = ['.xml','.par','.yaml','.png','.pdf']        
        if self.config['fileio']['savefits']:
            extensions += ['.fits','.fit']
        
        if self.config['fileio']['workdir'] == self._savedir:
            return
        elif os.path.isdir(self.config['fileio']['workdir']):
            self.logger.info('Staging files to %s'%self._savedir)
            for f in os.listdir(self.config['fileio']['workdir']):

                if not os.path.splitext(f)[1] in extensions: continue
                
                self.logger.info('Copying ' + f)
                shutil.copy(os.path.join(self.config['fileio']['workdir'],f),
                            self._savedir)
            
        else:
            self.logger.error('Working directory does not exist.')

    def stage_input(self):
        """Copy data products to intermediate working directory."""

        extensions = ['.fits','.fit']
        
        if self.config['fileio']['workdir'] == self._savedir:
            return
        elif os.path.isdir(self.config['fileio']['workdir']):
            self.logger.info('Staging files to %s'%
                             self.config['fileio']['workdir'])
#            for f in glob.glob(os.path.join(self._savedir,'*')):
            for f in os.listdir(self._savedir):
                if not os.path.splitext(f)[1] in extensions: continue
                self.logger.info('Copying ' + f)
                shutil.copy(os.path.join(self._savedir,f),
                            self.config['fileio']['workdir'])
        else:
            self.logger.error('Working directory does not exist.')
            
    def setup(self,xmlmodel=None):
        """Run pre-processing step for each analysis component.  This
        will run everything except the likelihood optimization: data
        selection (gtselect, gtmktime), counts maps generation
        (gtbin), model generation (gtexpcube2,gtsrcmaps,gtdiffrsp)."""

        # Run data selection step
        rm = self._roi_model
        
        self._like = SummedLikelihood()
        for i, c in enumerate(self._components):

            self.logger.info("Performing setup for Analysis Component: " +
                             c.name)
            c.setup(xmlmodel=xmlmodel)
            self._like.addComponent(c.like)

        for name in self.like.sourceNames():

            src = self._roi.get_source_by_name(name)
            
            src_model = {'sed' : None, 'extension' : None,
                         'assoc' : None, 'class' : None }

            if 'ASSOC1' in src:
                src_model['assoc'] = src['ASSOC1'].strip()

            if 'CLASS1' in src:
                src_model['class'] = src['CLASS1'].strip()
                
            if isinstance(src,Source):
                src_model['RA'] = src['RAJ2000']
                src_model['DEC'] = src['DEJ2000']

            src_model.update(self.get_src_model(name,False))            
            rm['sources'][name] = src_model

        rm['roi']['counts'] = np.zeros(self.enumbins)
        rm['roi']['logLike'] = self.like()
        
        self._ccube_file = os.path.join(self.config['fileio']['workdir'],
                                        'ccube.fits')
        
        counts = []
        for i, c in enumerate(self.components):
            cm = c.countsMap()
            counts += [(cm,c.wcs)]
            rm['roi']['components'][i]['counts'] = np.squeeze(np.apply_over_axes(np.sum,cm,axes=[1,2]))
            rm['roi']['components'][i]['logLike'] = c.like()
            
        shape = (self.enumbins,self.npix,self.npix)
        self._counts = make_coadd_map(counts,self._wcs,shape)
        write_fits_image(self._counts,self._wcs,self._ccube_file)        
        rm['roi']['counts'] += np.squeeze(np.apply_over_axes(np.sum,self._counts,axes=[1,2]))
        self._update_roi()
        
    def cleanup(self):

        if self.config['fileio']['workdir'] == self._savedir: return
        elif os.path.isdir(self.config['fileio']['workdir']):
            self.logger.info('Deleting working directory: ' + self.config['fileio']['workdir'])
            shutil.rmtree(self.config['fileio']['workdir'])
            
    def generate_model(self,model_name=None):
        """Generate model maps for all components.  model_name should
        be a unique identifier for the model.  If model_name is None
        then the model maps will be generated using the current
        parameters of the ROI."""

        for i, c in enumerate(self._components):
            c.generate_model(model_name=model_name)

        # If all model maps have the same spatial/energy binning we
        # could generate a co-added model map here

    def setEnergyRange(self,emin,emax):
        """Set the energy range of the analysis."""
        for c in self.components:
            c.setEnergyRange(emin,emax)
            
    def modelCountsSpectrum(self,name,emin=None,emax=None,summed=False):
        """Return the predicted number of model counts versus energy
        for a given source and energy range.  If summed=True return
        the counts spectrum summed over all components otherwise
        return a list of model spectra."""

        if emin is None: emin = self.energies[0]
        if emax is None: emax = self.energies[-1]
        
        if summed:
            cs = np.zeros(self.enumbins)
            imin = valToBinBounded(self.energies,emin+1E-7)[0]
            imax = valToBinBounded(self.energies,emax-1E-7)[0]+1

            for c in self.components:
                ecenter = 0.5*(c.energies[:-1]+c.energies[1:])
                counts = c.modelCountsSpectrum(name,self.energies[0],
                                               self.energies[-1])

                cs += np.histogram(ecenter,
                                   weights=counts,
                                   bins=self.energies)[0]

            return cs[imin:imax]
        else:        
            cs = []
            for c in self.components: 
                cs += [c.modelCountsSpectrum(name,emin,emax)]            
            return cs

    def get_sources(self,cuts=None,distance=None,square=False):
        """Retrieve list of sources satisfying the given selections."""
        rsrc, srcs = self._roi.get_sources_by_position(self._roi.skydir,
                                                       distance,
                                                       square=square)
        o = []
        if cuts is None: cuts = []        
        for s,r in zip(srcs,rsrc):
            if not s.check_cuts(cuts): continue            
            o.append(s)

        return o
        
    
    def delete_sources(self,cuts=None,distance=None,square=False):
        """Delete sources within the ROI satisfying the given
        selection."""
        
        srcs = self.get_sources(cuts,distance,square)
        self._roi.delete_sources(srcs)    
        for c in self.components:
            c.delete_sources(srcs)
            
    def free_sources(self,free=True,pars=None,cuts=None,
                     distance=None,square=False):
        """Free/Fix sources within the ROI satisfying the given
        selection.

        Parameters
        ----------

        free : bool        
            Choose whether to free (free=True) or fix (free=False)
            source parameters.

        pars : list        
            Set a list of parameters to be freed/fixed for this
            source.  If none then all source parameters will be
            freed/fixed.  If pars='norm' then only normalization
            parameters will be freed.

        distance : float        
            Distance out to which sources should be freed or fixed.
            If none then all sources will be selected.

        square : bool        
            Apply an ROI-like selection on the maximum distance in
            either X or Y in projected cartesian coordinates.        
        
        """
        rsrc, srcs = self._roi.get_sources_by_position(self._roi.skydir,
                                                       distance,square=square)
        
        if cuts is None: cuts = []        
        for s,r in zip(srcs,rsrc):
            if not s.check_cuts(cuts): continue            
            self.free_source(s.name,free=free,pars=pars)

        for s in self._roi._diffuse_srcs:
#            if not s.check_cuts(cuts): continue
            self.free_source(s.name,free=free,pars=pars)
                                        
    def free_sources_by_position(self,free=True,pars=None,
                                 distance=None,square=False):
        """Free/Fix all sources within a certain distance of the given sky
        coordinate.  By default it will use the ROI center.

        Parameters
        ----------

        free : bool        
            Choose whether to free (free=True) or fix (free=False)
            source parameters.

        pars : list        
            Set a list of parameters to be freed/fixed for this
            source.  If none then all source parameters will be
            freed/fixed.  If pars='norm' then only normalization
            parameters will be freed.

        distance : float        
            Distance in degrees out to which sources should be freed
            or fixed.  If none then all sources will be selected.

        square : bool        
            Apply a square (ROI-like) selection on the maximum distance in
            either X or Y in projected cartesian coordinates.        
        """

        self.free_sources(free,pars,cuts=None,distance=distance,square=square)

    def set_edisp_flag(self,name,flag=True):

        src = self._roi.get_source_by_name(name)
        name = src.name
        
        for c in self.components:
            c.like[name].src.set_edisp_flag(flag)        

    def scale_parameter(self,name,par,scale):

        idx = self.like.par_index(name,par)
        self.like[idx].setScale(self.like[idx].getScale()*scale)        
        
    def set_parameter(self,name,par,value,true_value=True,scale=None,
                      bounds=None):
        idx = self.like.par_index(name,par)
        if true_value:
            for p in self.like[idx].pars:            
                p.setTrueValue(value)
        else:
            self.like[idx].setValue(value)

        if scale is not None:
            self.like[idx].setScale(scale)

        if bounds is not None:
            self.like[idx].setBounds(*bounds)
            
    def free_parameter(self,name,par,free=True):
        idx = self.like.par_index(name,par)
        self.like[idx].setFree(free)
        
    def free_source(self,name,free=True,pars=None):
        """Free/Fix parameters of a source.

        Parameters
        ----------

        name : str
            Source name.

        free : bool        
            Choose whether to free (free=True) or fix (free=False)
            source parameters.

        pars : list        
            Set a list of parameters to be freed/fixed for this source.  If
            none then all source parameters will be freed/fixed with the
            exception of those defined in the skip_pars list.
            
        """

        free_pars = self.get_free_params()
        
        # Find the source
        src = self._roi.get_source_by_name(name)
        name = src.name
        
        if pars is None:
            pars = []
            pars += norm_parameters[src['SpectrumType']]
            pars += shape_parameters[src['SpectrumType']]
        elif pars == 'norm':
            pars = []
            pars += norm_parameters[src['SpectrumType']]
        elif pars == 'shape':
            pars = []
            pars += shape_parameters[src['SpectrumType']]
        elif isinstance(pars,list):
            pass
        else:
            raise Exception('Invalid parameter list.')
            
        # Deduce here the names of all parameters from the spectral type
        src_par_names = pyLike.StringVector()
        self.like[name].src.spectrum().getParamNames(src_par_names)

        par_indices = []
        par_names = []
        for p in src_par_names:
            if pars is not None and not p in pars: continue

            idx = self.like.par_index(name,p)
            if free == free_pars[idx]: continue
            
            par_indices.append(idx)
            par_names.append(p)

        if len(par_names) == 0: return
            
        if free:
            self.logger.info('Freeing parameters for %-22s: %s'
                             %(name,par_names))
        else:
            self.logger.info('Fixing parameters for %-22s: %s'
                             %(name,par_names))
            
        for (idx,par_name) in zip(par_indices,par_names):
            self.like[idx].setFree(free)
        self.like.syncSrcParams(name)
                
#        freePars = self.like.freePars(name)
#        if not free:
#            self.like.setFreeFlag(name, freePars, False)
#        else:
#            self.like[idx].setFree(True)

    def zero_source(self,name):

        pass

    def set_norm(self,name,value):
        name = self.get_source_name(name)                
        normPar = self.like.normPar(name)
        normPar.setValue(value)
        self.like.syncSrcParams(name)
        
    def free_norm(self,name,free=True):
        """Free/Fix normalization of a source.

        Parameters
        ----------

        name : str
            Source name.

        free : bool        
            Choose whether to free (free=True) or fix (free=False).
        
        """

        name = self.get_source_name(name)
        
#        if free: self.logger.info('Freeing norm for ' + name)
#        else: self.logger.info('Fixing norm for ' + name)
        
        normPar = self.like.normPar(name).getName()
        self.free_source(name,pars=[normPar],free=free)
        
#        par_index = self.like.par_index(name,normPar)        
#        self.like[par_index].setFree(free)
#        self.like.syncSrcParams(name)

    def free_index(self,name,free=True):
        """Free/Fix index of a source."""
        src = self._roi.get_source_by_name(name)

        self.free_source(src.name,free=free,
                         pars=index_parameters[src['SpectrumType']])
        
    def free_shape(self,name,free=True):
        """Free/Fix shape parameters of a source."""
        src = self._roi.get_source_by_name(name)

        self.free_source(src.name,free=free,
                         pars=shape_parameters[src['SpectrumType']])

    def get_source_name(self,name):
        """Return the name of a source as it is defined in the
        pyLikelihood model object."""
        if not name in self.like.sourceNames():
            name = self._roi.get_source_by_name(name).name
        return name

    def get_free_source_params(self,name):
        name = self.get_source_name(name)
        spectrum = self.like[name].src.spectrum()
        parNames = pyLike.StringVector()
        spectrum.getFreeParamNames(parNames)
        return [str(p) for p in parNames]

    def get_free_params(self):
        free = []
        for p in self.like.params():
            free.append(p.isFree())
        return free

    def set_free_params(self,free):
        for i,t in enumerate(free):
            if t: self.like.thaw(t)
            else: self.like.freeze(t)
    
    def residmap(self,prefix):
        """Generate data/model residual maps using the current model."""

        self.logger.info('Running residual analysis')
        self._rmg.run(prefix)
        
    def optimize(self):
        """Iteratively optimize the ROI model."""

        self.logger.info('Running ROI Optimization')
        
        # preserve free parameters
        free = self.get_free_params()

        # Fix all parameters
        self.free_sources(free=False)

        # Free norms of sources that compose 95% of total counts
        npred_sum = 0
        skip_sources = []
        for k, v in sorted(self._roi_model['sources'].items(),
                           key=lambda t: t[1]['Npred'],reverse=True):

            npred_sum += v['Npred']
            npred_frac = npred_sum/self._roi_model['roi']['Npred']
            self.free_norm(k)
            skip_sources.append(k)

            if npred_frac > 0.95: break

        self.fit()
        self.free_sources(free=False)

        # Step through remaining sources and re-fit normalizations
        for k, v in sorted(self._roi_model['sources'].items(),
                           key=lambda t: t[1]['Npred'],reverse=True):

            if k in skip_sources: continue
            
            if  v['Npred'] < self.config['roiopt']['npred_threshold']:
                self.logger.info('Skipping %s with Npred %10.3f'%(k,v['Npred']))
                continue

            self.logger.info('Fitting %s Npred: %10.3f'%(k,v['Npred']))
            
            self.free_norm(k)
            self.fit()

            v0 = self._roi_model['sources'][k]
            
            self.logger.info('Post-fit Results Npred: %10.3f TS: %10.3f'%(v0['Npred'],v0['ts']))
            
            self.free_norm(k,free=False)        

        # Refit spectral shape parameters for sources with TS > 100
        for k, v in sorted(self._roi_model['sources'].items(),
                           key=lambda t: t[1]['ts'] if np.isfinite(t[1]['ts']) else 0,
                           reverse=True):
            
            if v['ts'] < 100 or not np.isfinite(v['ts']): continue

            self.logger.info('Fitting shape %s TS: %10.3f'%(k,v['ts']))
            
            self.free_source(k)
            self.fit()
            self.free_source(k,free=False)
            
        self.set_free_params(free)

    def run(self):
        """Run extension and sed analysis for the given sources."""

        for s in self.config['run']['sed']:
            self.sed(s)

        for s in self.config['run']['extension']:
            self.extension(s)
        
        
    def extension(self,name):
        """Perform an angular extension test for this source."""
        
        name = self.roi.get_source_by_name(name).name
        
        self.logger.info('Running extension analysis for %s'%name)

        model_name = '%s_ext'%(name.lower().replace(' ','_'))
        null_model_name = '%s_noext'%(name.lower().replace(' ','_'))
        
        saved_state = LikelihoodState(self.like)

        self.free_sources(free=False)
        
        # Compute TS_ext
        logLike0 = self.like()
        self.generate_model_map(model_name=null_model_name,name=name)

#        src = self.like.deleteSource(name)
        normPar = self.like.normPar(name).getName()        
        self.scale_parameter(name,normPar,1E-10)
        self.like.syncSrcParams(name)
        
        self.generate_model_map(model_name=model_name+'_bkg')

        
        if self.config['extension']['width'] is not None:
            width = self.config['extension']['width']
        else:
            width = np.logspace(np.log10(self.config['extension']['width_min']),
                                np.log10(self.config['extension']['width_max']),
                                self.config['extension']['width_nstep'])

        ext = {'width' : width,
               'dlogLike' : np.zeros(len(width)),
               'logLike' : np.zeros(len(width)),
               'ext' : 0.0,
               'ext_err_hi' : 0.0,
               'ext_err_lo' : 0.0,
               'ext_ul95' : 0.0,
               'ts_ext' : 0.0,
               'fit' : []}
        
        for i, w in enumerate(width):
            
            # make a copy
            s = copy.deepcopy(self.roi.get_source_by_name(name))
            s.set_name(model_name)
            s.set_spatial_model(self.config['extension']['spatial_model'],w)
            
            self.logger.info('Adding test source with width: %f'%w)
            for k,v in s.spectral_pars.items():
                s._spectral_pars[k]['value'] = str(self.like[name].src.spectrum().getParamValue(k))
                
            self.add_source(model_name,s,free=True)
            self.free_norm(model_name)
            self.like.syncSrcParams(model_name)
            self.fit(update=False)
            
            logLike1 = self.like()

            ext['dlogLike'][i] = logLike0-logLike1
            ext['logLike'][i] = logLike1
            sd = self.get_src_model(model_name)
            ext['fit'].append(sd)
            
            self.generate_model_map(model_name='%s%02i'%(model_name,i),
                                    name=model_name)
            self.delete_source(model_name,
                               save_template=self.config['extension']['save_templates'])

        try:
            ext['ext'], ext['ext_ul95'], ext['ext_err_lo'], ext['ext_err_hi'], ext['ts_ext'] = \
                get_upper_limit(ext['dlogLike'],ext['width'],interpolate=True)
        except Exception, message:
            self.logger.error('Upper limit failed.', exc_info=True)
            
        self.scale_parameter(name,normPar,1E10)
            
        saved_state.restore()

        src_model = self._roi_model['sources'].get(name,{})
        src_model['extension'] = copy.deepcopy(ext)   
        
        return ext
                
    def sed(self,name,profile=True,energies=None,**kwargs):
        """Generate an SED for a source.  This function will fit the
        normalization of a given source in each energy bin.

        Parameters
        ----------

        name : str
            Source name.

        profile : bool        
            Profile the likelihood in each energy bin.

        energies : array        
            Sequence of energies in log10(E/MeV) defining the edges of
            the energy bins.  If this argument is None then the
            analysis energy bins will be used.  The energies in this
            sequence must align with the bin edges of the underyling
            analysis instance.

        bin_index : float        
            Spectral index that will be use when fitting the energy
            distribution within an energy bin.

        use_local_index : bool
            Use a power-law approximation to the shape of the global
            spectrum in each bin.  If this is false then a constant
            index set to `bin_index` will be used.            
            
        """
        
        
        # Find the source
        name = self.roi.get_source_by_name(name).name

        self.logger.info('Computing SED for %s'%name)
        saved_state = LikelihoodState(self.like)

        self.free_sources(free=False)
        
        if energies is None: energies = self.energies
        else: energies = np.array(energies)
        
        nbins = len(energies)-1

        o = {'emin'      : energies[:-1],
             'emax'      : energies[1:],
             'ecenter'   : 0.5*(energies[:-1]+energies[1:]),
             'flux'      : np.zeros(nbins),
             'eflux'     : np.zeros(nbins),
             'dfde'      : np.zeros(nbins),
             'e2dfde'    : np.zeros(nbins),
             'flux_err'  : np.zeros(nbins),
             'eflux_err' : np.zeros(nbins),
             'dfde_err'  : np.zeros(nbins),
             'e2dfde_err' : np.zeros(nbins),
             'dfde_ul95' : np.zeros(nbins)*np.nan,
             'e2dfde_ul95' : np.zeros(nbins)*np.nan,
             'dfde_err_lo' : np.zeros(nbins)*np.nan,
             'e2dfde_err_lo' :  np.zeros(nbins)*np.nan,
             'dfde_err_hi' : np.zeros(nbins)*np.nan,
             'e2dfde_err_hi' :  np.zeros(nbins)*np.nan,
             'index' : np.zeros(nbins),
             'Npred' : np.zeros(nbins),
             'ts' : np.zeros(nbins),
             'fit_quality' : np.zeros(nbins),
             'lnlprofile' : []
             }

        max_index = 5.0
        min_flux = 1E-30
        
        # Precompute fluxes in each bin from global fit
        gf_bin_flux = []
        gf_bin_index = []
        for i, (emin,emax) in enumerate(zip(energies[:-1],energies[1:])):

            delta = 1E-5
            f = self.like[name].flux(10**emin, 10**emax)
            f0 = self.like[name].flux(10**emin*(1-delta), 10**emin*(1+delta))
            f1 = self.like[name].flux(10**emax*(1-delta), 10**emax*(1+delta))

            if f0 > min_flux:
                g = 1-np.log10(f0/f1)/np.log10(10**emin/10**emax)
                gf_bin_index += [g]
                gf_bin_flux += [f]
            else:
                gf_bin_index += [max_index]
                gf_bin_flux += [min_flux]
                
        bin_index = kwargs.get('bin_index',self.config['sed']['bin_index'])
        use_local_index = kwargs.get('use_local_index',self.config['sed']['use_local_index'])
        
        source = self.components[0].like.logLike.getSource(name)
        old_spectrum=source.spectrum()
        self.like.setSpectrum(name,'PowerLaw')
        self.free_parameter(name,'Index',False)
        self.set_parameter(name,'Prefactor',1.0,scale=1E-13,true_value=False,
                           bounds=[1E-10,1E10])
                
        for i, (emin,emax) in enumerate(zip(energies[:-1],energies[1:])):
#            saved_state.restore()

            ecenter = 0.5*(emin+emax)
            deltae = 10**emax - 10**emin
            self.set_parameter(name,'Scale',10**ecenter,scale=1.0)
            
            if use_local_index:
                o['index'][i] = -min(gf_bin_index[i],max_index)
            else:
                o['index'][i] = -bin_index
                
            self.set_parameter(name,'Index',o['index'][i],scale=1.0)
            
            normVal = self.like.normPar(name).getValue()
            flux_ratio = gf_bin_flux[i]/self.like[name].flux(10**emin, 10**emax)
            newVal = max(normVal*flux_ratio,1E-10)
            self.set_norm(name,newVal)
            
            self.like.syncSrcParams(name)
            self.free_norm(name)
            self.logger.info('Fitting %s SED from %.0f MeV to %.0f MeV' %
                             (name,10**emin,10**emax))
            self.setEnergyRange(emin,emax)            
            o['fit_quality'][i] = self.fit(update=False)

            prefactor=self.like[self.like.par_index(name, 'Prefactor')] 
            
            flux = self.like[name].flux(10**emin, 10**emax)
            flux_err = self.like.fluxError(name,10**emin, 10**emax)
            eflux = self.like[name].energyFlux(10**emin, 10**emax)
            eflux_err = self.like.energyFluxError(name,10**emin, 10**emax)
            dfde = prefactor.getTrueValue()
            dfde_err = dfde_err = dfde*flux_err/flux
            
            o['flux'][i] = flux
            o['eflux'][i] = eflux
            o['dfde'][i] = dfde
            o['e2dfde'][i] = dfde*10**(2*ecenter)
            o['flux_err'][i] = flux_err
            o['eflux_err'][i] = eflux_err
            o['dfde_err'][i] = dfde_err
            o['e2dfde_err'][i] = dfde_err*10**(2*ecenter)

            cs = self.modelCountsSpectrum(name,emin,emax,summed=True)
            o['Npred'][i] = np.sum(cs)            
            o['ts'][i] = max(self.like.Ts(name,reoptimize=False),0.0)
            if profile:

                lnlp = self.profile_norm(name,emin=emin,emax=emax,savestate=False)                
                o['lnlprofile'] += [lnlp]
                dfde, dfde_ul95, dfde_err_lo, dfde_err_hi, dlnl0 = get_upper_limit(lnlp['dlogLike'],lnlp['dfde'])
                                
                o['dfde_ul95'][i] = dfde_ul95
                o['e2dfde_ul95'][i] = dfde_ul95*10**(2*ecenter)
                o['dfde_err_hi'][i] = dfde_err_hi
                o['e2dfde_err_hi'][i] = dfde_err_hi*10**(2*ecenter)                
                o['dfde_err_lo'][i] = dfde_err_lo
                o['e2dfde_err_lo'][i] = dfde_err_lo*10**(2*ecenter)
                
#        self.setEnergyRange(energies[0],energies[-1])
        self.setEnergyRange(self.energies[0],self.energies[-1])
        self.like.setSpectrum(name,old_spectrum)
        saved_state.restore()        
        src_model = self._roi_model['sources'].get(name,{})
        src_model['sed'] = copy.deepcopy(o)        
        return o

    def profile_norm(self,name, emin=None,emax=None, reoptimize=False,xvals=None,npts=50,
                     savestate=True):
        """
        Profile the normalization of a source.
        """
        
        # Find the source
        name = self._roi.get_source_by_name(name).name

        par = self.like.normPar(name)
        parName = self.like.normPar(name).getName()
        idx = self.like.par_index(name,parName)
        bounds = self.like.model[idx].getBounds()
        emin = min(self.energies) if emin is None else emin
        emax = max(self.energies) if emax is None else emax

        cs = self.modelCountsSpectrum(name,emin,emax,summed=True)
        npred = np.sum(cs)
        
        if xvals is None:

            err = par.error()
            val = par.getValue()

            if npred < 10:
                val *= 1./min(1.0,npred)
                xvals = val*10**np.linspace(-2.0,2.0,2*npts+1)
                xvals = np.insert(xvals,0,0.0)
            else:
                xvals = np.linspace(0,1,1+npts)
                xvals = np.concatenate((-1.0*xvals[1:][::-1],xvals))
                xvals = val*10**xvals

        return self.profile(name,parName,emin=emin,emax=emax,reoptimize=reoptimize,xvals=xvals,
                            savestate=savestate)
    
    def profile(self, name, parName, emin=None,emax=None, reoptimize=False,xvals=None,npts=None,
                savestate=True):
        """ Profile the likelihood for the given source and parameter.  
        """
        
        # Find the source
        name = self._roi.get_source_by_name(name).name

        par = self.like.normPar(name)
        parName = self.like.normPar(name).getName()
        idx = self.like.par_index(name,parName)
        scale = float(self.like.model[idx].getScale())
        bounds = self.like.model[idx].getBounds()

        emin = min(self.energies) if emin is None else emin
        emax = max(self.energies) if emax is None else emax

        ecenter = 0.5*(emin+emax)
        deltae = 10**emax - 10**emin
        npred = np.sum(self.modelCountsSpectrum(name,emin,emax,summed=True))

        if savestate:
            saved_state = LikelihoodState(self.like)

        self.setEnergyRange(emin,emax)
        logLike0 = self.like()

        if xvals is None:

            err = par.error()
            val = par.getValue()
            if err <= 0 or val <= 3*err:                
                xvals = 10**np.linspace(-2.0,2.0,51)
                if val < xvals[0]: xvals = np.insert(xvals,val,0)
            else:
                xvals = np.linspace(0,1,25)
                xvals = np.concatenate((-1.0*xvals[1:][::-1],xvals))
                xvals = val*10**xvals

        self.like[idx].setBounds(xvals[0],xvals[-1])

        o = {'xvals'    : xvals,
             'Npred'    : np.zeros(len(xvals)),
             'dfde'     : np.zeros(len(xvals)),
             'flux'     : np.zeros(len(xvals)),
             'eflux'    : np.zeros(len(xvals)),
             'dlogLike' : np.zeros(len(xvals)),
             'logLike' : np.zeros(len(xvals))
             }

        for i, x in enumerate(xvals):
            
            self.like[idx] = x
            self.like.syncSrcParams(name)

            if self.like.logLike.getNumFreeParams() > 1 and reoptimize:
                # Only reoptimize if not all frozen                
                self.like.freeze(idx)
                self.like.optimize(0, **kwargs)
                self.like.thaw(idx)
                
            logLike1 = self.like()

            flux = self.like[name].flux(10**emin, 10**emax)
            eflux = self.like[name].energyFlux(10**emin, 10**emax)
            prefactor=self.like[idx]
            
            o['dlogLike'][i] = logLike0 - logLike1
            o['logLike'][i] = logLike1
            o['dfde'][i] = prefactor.getTrueValue()
            o['flux'][i] = flux
            o['eflux'][i] = eflux

            cs = self.modelCountsSpectrum(name,emin,emax,summed=True)
            o['Npred'][i] += np.sum(cs)
            
#        if len(self.like.model.srcs) == 1 and fluxes[0] == 0:
#            # Likelihood is undefined with one source and no flux, hack it..
#            dlogLike[0] = dlogLike[1]

        # Restore model parameters to original values
        if savestate:
            saved_state.restore()
        self.like[idx].setBounds(*bounds)
        
        return o
    
    def initOptimizer(self):
        pass        

    def create_optObject(self):
        """ Make MINUIT or NewMinuit type optimizer object """

        optimizer = self.config['optimizer']['optimizer']
        if optimizer.upper() == 'MINUIT':
            optObject = pyLike.Minuit(self.like.logLike)
        elif optimizer.upper == 'NEWMINUIT':
            optObject = pyLike.NewMinuit(self.like.logLike)
        else:
            optFactory = pyLike.OptimizerFactory_instance()
            optObject = optFactory.create(optimizer, self.like.logLike)
        return optObject

    def _run_fit(self,**kwargs):

        try:
            self.like.fit(**kwargs)            
        except Exception, message:
            self.logger.error('Likelihood optimization failed.', exc_info=True)

        if isinstance(self.like.optObject,pyLike.Minuit) or \
                isinstance(self.like.optObject,pyLike.NewMinuit):
            quality = self.like.optObject.getQuality()
        else:
            quality = 3

        return quality

    def fit(self,update=True,**kwargs):
        """Run likelihood optimization.

        

        """
        
        if not self.like.logLike.getNumFreeParams(): 
            self.logger.info("Skipping fit.  No free parameters.")
            return

        verbosity = kwargs.get('verbosity',
                               self.config['optimizer']['verbosity'])
        covar = kwargs.get('covar',True)
        tol = kwargs.get('tol',self.config['optimizer']['tol'])

        saved_state = LikelihoodState(self.like)
        kw = dict(optObject = self.create_optObject(),
                  covar=covar,verbosity=verbosity,tol=tol)
#                  optimizer='DRMNFB')

        quality=0
        niter = 0; max_niter = self.config['optimizer']['retries']
        while niter < max_niter:
            self.logger.info("Fit iteration: %i"%niter)
            niter += 1
            quality = self._run_fit(**kw)
            if quality > 2: break
            
#        except Exception, message:
#            print self.like.optObject.getQuality()
#            self.logger.error('Likelihood optimization failed.', exc_info=True)
#            saved_state.restore()
#            return quality

        logLike = self.like()
            
        if quality < self.config['optimizer']['min_fit_quality']:
            self.logger.error("Failed to converge with %s"%self.like.optimizer)
            saved_state.restore()
            return quality

        if update:
            for name in self.like.sourceNames():
                freePars = self.get_free_source_params(name)                
                if len(freePars) == 0: continue

                sd = self.get_src_model(name)
                self._roi_model['sources'][name] = merge_dict(self._roi_model['sources'][name],sd,
                                                              add_new_keys=True)

            self._roi_model['roi']['logLike'] = logLike
            self._roi_model['roi']['fit_quality'] = quality

            for i,c in enumerate(self.components):
                self._roi_model['roi']['components'][i]['logLike'] = c.like()

            # Update roi model counts
            self._update_roi()
                
        self.logger.info("Fit returned successfully.")
        self.logger.info("Fit Quality: %i LogLike: %12.3f"%(quality,logLike))
        return quality
        
    def fitDRM(self):
        
        kw = dict(optObject = None, #pyLike.Minuit(self.like.logLike),
                  covar=True,#tol=1E-4
                  optimizer='DRMNFB')
        
#        self.MIN.tol = float(self.likelihoodConf['mintol'])
        
        try:
            self.like.fit(**kw)
        except Exception, message:
            print message
            print "Failed to converge with DRMNFB"

        kw = dict(optObject = pyLike.Minuit(self.like.logLike),
                  covar=True)

        self.like.fit(**kw)
        
    def load_xml(self,xmlfile):
        """Load model definition from XML."""

        for c in self.components:
            c.load_xml(xmlfile)        

    def write_xml(self,xmlfile,save_model_map=True):
        """Save current model definition as XML file.

        Parameters
        ----------

        xmlfile : str
            Name of the output XML file.

        save_model_map : bool
            Save the current counts model as a FITS file.
        """

        model_name = os.path.splitext(xmlfile)[0]

        # Write a common XML file?
        
        for i, c in enumerate(self._components):
            c.write_xml(xmlfile)

        if not save_model_map: return []            
        return self.generate_model_map(model_name)

    def generate_model_map(self,model_name,name=None):
        
        counts = []
        for i, c in enumerate(self._components):

            cm = c.generate_model_map(model_name,name)
            counts += [(cm,c.wcs)]

        outfile = os.path.join(self.config['fileio']['workdir'],
                               'mcube_%s.fits'%(model_name))

        shape = (self.enumbins,self.npix,self.npix)
        model_counts = make_coadd_map(counts,self._wcs,shape)
        write_fits_image(model_counts,self._wcs,outfile)        
        return [(model_counts,self._wcs)] + counts

    def load_roi(self,infile):

        self.load_xml(infile)

        infile, ext = os.path.splitext(infile)
        infile += '.npy'
        
        if not os.path.isfile(infile):
            infile = os.path.join(self.config['fileio']['workdir'],
                                  os.path.basename(infile))
        
        data = np.load(infile)
        self._roi_model = np.array(data,ndmin=1)[0]
    
    def write_roi(self,outfile=None,make_residuals=False,save_model_map=True,
                  update_sources=False):
        """Write current model to a file.  This function will write an
        XML model file and an ROI dictionary in both YAML and npy
        formats.

        Parameters
        ----------

        outfile : str        
            Name of the output file.  The extension of this string
            will be stripped when generating the XML, YAML and
            Numpy filenames.

        make_residuals : bool
            Run residual analysis.
            
        save_model_map : bool
            Save the current counts model as a FITS file.

        update_sources : bool

        """
        # extract the results in a convenient format

        if outfile is None:
            outfile = os.path.join(self._savedir,'results')
            prefix=''
        else:
            outfile, ext = os.path.splitext(outfile)
            prefix = outfile
            if not os.path.isabs(outfile):            
                outfile = os.path.join(self._savedir,outfile)
            
        mcube_maps = self.write_xml(prefix,save_model_map=save_model_map)
        
        if make_residuals:
            self.residmap(prefix)
        else:
            self._roi_model['roi']['residmap'] = {}

        o = self.get_roi_model(update_sources=update_sources)
        o['config'] = copy.deepcopy(self.config)
        
        self.logger.info('Writing %s...'%(outfile + '.yaml'))
        yaml.dump(tolist(o),open(outfile + '.yaml','w'))

        self.logger.info('Writing %s...'%(outfile + '.npy'))
        np.save(outfile + '.npy',o)

        self.make_plots(mcube_maps,prefix)

    def make_sed_plots(self,prefix):

        for k,v in self._roi_model['sources'].items():

            if not 'sed' in v: continue
            if v['sed'] is None: continue

            name = k.lower().replace(' ','_')
            
            p = SEDPlotter(v)
            plt.figure()
            p.plot()            
            plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                     '%s_%s_sed.png'%(prefix,name)))


    def make_extension_plots(self,prefix,erange=None):

        for k,v in self._roi_model['sources'].items():

            if not 'extension' in v: continue
            if v['extension'] is None: continue

            self._plot_extension(prefix,v,erange=erange)
            
    def _plot_extension(self,prefix,v,erange=None):

        if erange is None:
            erange = (self.energies[0],self.energies[-1])
        
        name = v['name'].lower().replace(' ','_')

        esuffix = '_%.3f_%.3f'%(erange[0],erange[1])        
            
        p = ExtensionPlotter(v,self.roi,'',self.config['fileio']['workdir'],
                             erange=erange)
 
        fig = plt.figure()
        p.plot(0)
        plt.gca().set_xlim(-2,2)
        ROIPlotter.setup_projection_axis(0,erange=erange)
        plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                 '%s_%s_extension_xproj%s.png'%(prefix,name,esuffix)))
        plt.close(fig)
        
        fig = plt.figure()
        p.plot(1)
        plt.gca().set_xlim(-2,2)
        ROIPlotter.setup_projection_axis(1,erange=erange)
        plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                 '%s_%s_extension_yproj%s.png'%(prefix,name,esuffix)))
        plt.close(fig)
        
        for i, c in enumerate(self.components):

            suffix = '_%02i'%i

            p = ExtensionPlotter(v,self.roi,suffix,
                                 self.config['fileio']['workdir'],erange=erange)
            
            fig = plt.figure()
            p.plot(0)
            ROIPlotter.setup_projection_axis(0,erange=erange)
            plt.gca().set_xlim(-2,2)
            plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                     '%s_%s_extension_xproj%s%s.png'%(prefix,name,esuffix,suffix)))
            plt.close(fig)
            
            fig = plt.figure()
            p.plot(1)
            plt.gca().set_xlim(-2,2)
            ROIPlotter.setup_projection_axis(1,erange=erange)
            plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                     '%s_%s_extension_yproj%s%s.png'%(prefix,name,esuffix,suffix)))
            plt.close(fig)
            
        
    def make_roi_plots(self,mcube_maps,prefix,erange=None):

        if erange is None:
            erange = (self.energies[0],self.energies[-1])
        esuffix = '_%.3f_%.3f'%(erange[0],erange[1])  

        if len(mcube_maps):

            fig = plt.figure()        
            p = ROIPlotter(mcube_maps[0][0],mcube_maps[0][1],
                           self.roi,erange=erange)
            p.plot(cb_label='Counts',zscale='pow',gamma=1./3.)
            plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                     '%s_model_map%s.png'%(prefix,esuffix)))
            plt.close(fig)


        figx = plt.figure('xproj')
        figy = plt.figure('yproj')

        colors = ['k','b','g','r']
        data_style = {'marker' : 's', 'linestyle' : 'None'}

        for i, c in enumerate(self.components):

            fig = plt.figure()        
            p = ROIPlotter(mcube_maps[i+1][0],mcube_maps[i+1][1],self.roi,
                           erange=erange)
            p.plot(cb_label='Counts',zscale='pow',gamma=1./3.)
            plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                     '%s_model_map%s_%02i.png'%(prefix,esuffix,i)))
            plt.close(fig)
            
            plt.figure(figx.number)
            p = ROIPlotter.create_from_fits(c._ccube_file,self.roi,
                                            erange=erange)
            p.plot_projection(0,color=colors[i%4],label='Component %i'%i,
                              **data_style)
            p.plot_projection(0,data=mcube_maps[i+1][0].T,
                              color=colors[i%4],noerror=True)
            
            
            plt.figure(figy.number)
            p.plot_projection(1,color=colors[i%4],label='Component %i'%i,
                              **data_style)
            p.plot_projection(1,data=mcube_maps[i+1][0].T,
                              color=colors[i%4],noerror=True)
            
            
        plt.figure(figx.number)
        ROIPlotter.setup_projection_axis(0,erange=erange)
        figx.savefig(os.path.join(self.config['fileio']['outdir'],
                                  '%s_counts_map_comp_xproj%s.png'%(prefix,esuffix)))

        plt.figure(figy.number)
        ROIPlotter.setup_projection_axis(1,erange=erange)
        figy.savefig(os.path.join(self.config['fileio']['outdir'],
                                  '%s_counts_map_comp_yproj%s.png'%(prefix,esuffix)))
        plt.close(figx)
        plt.close(figy)
            
        fig = plt.figure()        
        p = ROIPlotter.create_from_fits(self._ccube_file,self.roi,erange=erange)
        p.plot(cb_label='Counts',zscale='sqrt')
        plt.savefig(os.path.join(self.config['fileio']['outdir'],
                              '%s_counts_map%s.png'%(prefix,esuffix)))
        plt.close(fig)

        fig = plt.figure()
        p.plot_projection(0,label='Data',color='k',**data_style)
        p.plot_projection(0,data=mcube_maps[0][0].T,label='Model',noerror=True)
        plt.gca().set_ylabel('Counts')
        plt.gca().set_xlabel('LON Offset [deg]')
        plt.gca().legend(frameon=False)
#        plt.gca().set_yscale('log')
        plt.savefig(os.path.join(self.config['fileio']['outdir'],
                              '%s_counts_map_xproj%s.png'%(prefix,esuffix)))
        plt.close(fig)
        
        fig = plt.figure()
        p.plot_projection(1,label='Data',color='k',**data_style)
        p.plot_projection(1,data=mcube_maps[0][0].T,label='Model',noerror=True)
        plt.gca().set_ylabel('Counts')
        plt.gca().set_xlabel('LAT Offset [deg]')
        plt.gca().legend(frameon=False)
#        plt.gca().set_yscale('log')
        plt.savefig(os.path.join(self.config['fileio']['outdir'],
                              '%s_counts_map_yproj%s.png'%(prefix,esuffix)))
        
        plt.close(fig)
        
        
    def make_plots(self,mcube_maps,prefix):

        erange = [None] + self.config['plotting']['erange']

        for x in erange:
            self.make_roi_plots(mcube_maps,prefix,erange=x)
            self.make_extension_plots(prefix,erange=x)

        for k, v in self._roi_model['roi']['residmap'].items():

            fig = plt.figure()
            p = ROIPlotter(self._rmg._maps[k]['sigma'],
                           self._rmg._maps[k]['wcs'],self.roi)
            p.plot(vmin=-5,vmax=5,levels=[-5,-3,3,5],
                   cb_label='Significance [$\sigma$]')
            plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                     '%s_residmap_%s.png'%(prefix,k)))
            plt.close(fig)

            fig = plt.figure()
            p = ROIPlotter(self._rmg._maps[k]['data'],
                           self._rmg._maps[k]['wcs'],self.roi)
            p.plot(cb_label='Smoothed Counts',zscale='pow',gamma=1./3.)
            plt.savefig(os.path.join(self.config['fileio']['outdir'],
                                     '%s_scmap_%s.png'%(prefix,k)))
            plt.close(fig)
            
        self.make_sed_plots(prefix)
            
        imfile = os.path.join(self.config['fileio']['outdir'],
                              '%s_counts_spectrum.png'%(prefix))

        make_counts_spectrum_plot(self._roi_model,self.energies,imfile)
        
    def tsmap(self):
        """Loop over ROI, place a test source at each position, and
        evaluated the TS for that source."""

        saved_state = LikelihoodState(self.like)
        
        # Get the ROI geometry

        # Loop over pixels
        w = create_wcs(self._roi.skydir,cdelt=self._binsz,crpix=50.5)

        hdu_image = pyfits.PrimaryHDU(np.zeros((100,100)),
                                      header=w.to_header())
#        for i in range(100):
#            for j in range(100):
#                print w.wcs_pix2world(i,j,0)

        self.free_sources(free=False)

        radec = w.wcs_pix2world(50,50,0)

        
        loglike0 = self.like()
        for i in range(45,55):
            for j in range(45,55):
                radec = w.wcs_pix2world(i,j,0)
                print 'Fitting source at ', radec
            
                self.add_source('testsource',radec)

                self.like.freeze(self.like.par_index('testsource','Index'))
                self.like.thaw(self.like.par_index('testsource','Prefactor'))
            
#            self.free_source('testsource',free=False)
#            self.free_norm('testsource')


                
                self.fit(update=False)
                loglike1 = self.like()

                print loglike0-loglike1
                self.delete_source('testsource')

                hdu_image.data[i,j] = max(loglike0-loglike1,0)
                
        #kw = {'bexpmap'}

        saved_state.restore() 
        
        hdulist = pyfits.HDUList([hdu_image])
        hdulist.writeto('test.fits',clobber=True)
        
    def bowtie(self,fd,energies=None):
        """Generate a bowtie function for the given source.  This will
        create a band as a function of energy by propagating the
        errors on the global fit parameters.  Note that this band only
        reflects the uncertainty for parameters that were left free in
        the fit."""
        
        if energies is None:
            emin = self.energies[0]
            emax = self.energies[-1]        
            energies = np.linspace(emin,emax,50)
        
        
        dfde = [fd.value(10**x) for x in energies]
        dfde_err = [fd.error(10**x) for x in energies]

        dfde = np.array(dfde)
        dfde_err = np.array(dfde_err)
        fhi = dfde*(1.0 + dfde_err/dfde)
        flo = dfde/(1.0 + dfde_err/dfde)

        return {'ecenter' : energies, 'dfde' : dfde,
                'dfde_lo' : flo, 'dfde_hi' : fhi }
        
    def get_roi_model(self,update_sources=False):
        """Populate a dictionary with the current parameters of the
        ROI model as extracted from the pylikelihood object."""

        # Should we skip extracting fit results for sources that
        # weren't free in the last fit?

        # Determine what sources had at least one free parameter?

        if update_sources:
        
            gf = {}        
            for name in self.like.sourceNames():
                gf[name] = self.get_src_model(name)

            self._roi_model['sources'] = merge_dict(self._roi_model['sources'],
                                                    gf,add_new_keys=True) 

        return copy.deepcopy(self._roi_model)        

    def get_src_model(self,name,paramsonly=False):
        """Compose a dictionary for the given source."""

        self.logger.info('Generating source dict for ' + name)
        
        name = self.get_source_name(name)        
        source = self.like[name].src
        spectrum = source.spectrum()

        src_dict = { 'name' : name,
                     'flux' : np.ones(2)*np.nan,
                     'flux100' : np.ones(2)*np.nan,
                     'flux1000' : np.ones(2)*np.nan,
                     'flux10000' : np.ones(2)*np.nan,
                     'dfde100' : np.ones(2)*np.nan,
                     'dfde1000' : np.ones(2)*np.nan,
                     'dfde10000' : np.ones(2)*np.nan,
                     'flux_ul95' : np.nan,
                     'flux100_ul95' : np.nan,
                     'flux1000_ul95' : np.nan,
                     'flux10000_ul95' : np.nan,
                     'ts' : np.nan
                     }

        src_dict['params'] = gtlike_spectrum_to_dict(spectrum)

        # Get NPred
        src_dict['Npred'] = self.like.NpredValue(name)
        
        # Get Counts Spectrum
        src_dict['model_counts'] = self.modelCountsSpectrum(name,summed=True)

        # Get the Model Fluxes
        try:
            src_dict['flux'][0] = self.like.flux(name,10**self.energies[0], 10**self.energies[-1])
            src_dict['flux100'][0] = self.like.flux(name,100., 10**5.5)
            src_dict['flux1000'][0] = self.like.flux(name,1000., 10**5.5)
            src_dict['flux10000'][0] = self.like.flux(name,10000., 10**5.5)
            src_dict['dfde100'][0] = self.like[name].spectrum()(pyLike.dArg(100.))
            src_dict['dfde1000'][0] = self.like[name].spectrum()(pyLike.dArg(1000.))
            src_dict['dfde10000'][0] = self.like[name].spectrum()(pyLike.dArg(10000.))
        except Exception, ex:
            self.logger.error('Failed to update source parameters.', exc_info=True)
            
        # Only try to compute TS, errors, and ULs if the source was free in the fit
        if not self.get_free_source_params(name) or paramsonly:
            return src_dict

        try:
            src_dict['flux'][1] = self.like.fluxError(name,10**self.energies[0], 10**self.energies[-1])
            src_dict['flux100'][1] = self.like.fluxError(name,100., 10**5.5)
            src_dict['flux1000'][1] = self.like.fluxError(name,1000., 10**5.5)
            src_dict['flux10000'][1] = self.like.fluxError(name,10000., 10**5.5)
        except Exception, ex:
            pass
#            self.logger.error('Failed to update source parameters.', exc_info=True)

        lnlp = self.profile_norm(name,savestate=True)
        flux, flux_ul95, flux_err_lo, flux_err_hi, dlnl0 = get_upper_limit(lnlp['dlogLike'],
                                                                           lnlp['flux'])

        src_dict['flux_ul95'] = flux_ul95
        src_dict['flux100_ul95'] = src_dict['flux100'][0]*(flux_ul95/src_dict['flux'][0])
        src_dict['flux1000_ul95'] = src_dict['flux1000'][0]*(flux_ul95/src_dict['flux'][0])
        src_dict['flux10000_ul95'] = src_dict['flux10000'][0]*(flux_ul95/src_dict['flux'][0])
        
        # Extract covariance matrix
        fd = None            
        try:
            fd = FluxDensity.FluxDensity(self.like,name)
            src_dict['covar'] = fd.covar
        except RuntimeError, ex:
            pass
#                 if ex.message == 'Covariance matrix has not been computed.':
#                      pass
#                 elif 
#                      raise ex

        # Extract bowtie   
        if fd and len(src_dict['covar']) and src_dict['covar'].ndim >= 1:
            src_dict['model_flux'] = self.bowtie(fd)            
            src_dict['dfde100'][1] = fd.error(100.)
            src_dict['dfde1000'][1] = fd.error(1000.)
            src_dict['dfde10000'][1] = fd.error(10000.)

        src_dict['ts'] = self.like.Ts2(name,reoptimize=False)
        
        return src_dict
    
class GTBinnedAnalysis(AnalysisBase):

    defaults = dict(selection=defaults.selection,
                    binning=defaults.binning,
                    gtlike=defaults.gtlike,
                    data=defaults.data,
                    model=defaults.model,
                    logging=defaults.logging,
                    fileio=defaults.fileio,
                    name=('00',''),
                    file_suffix=('',''))

    def __init__(self,config,**kwargs):
        super(GTBinnedAnalysis,self).__init__(config,**kwargs)

        self.logger = Logger.get(self.__class__.__name__,
                                 self.config['fileio']['logfile'],
                                 ll(self.config['logging']['verbosity']))

        self._roi = ROIModel.create(self.config['selection'],
                                    self.config['model'],
                                    fileio=self.config['fileio'],
                                    logfile=self.config['fileio']['logfile'],
                                    logging=self.config['logging'])
                
        workdir = self.config['fileio']['workdir']
        self._name = self.config['name']
        
        from os.path import join

        self._ft1_file=join(workdir,
                            'ft1%s.fits'%self.config['file_suffix'])
        self._ft1_filtered_file=join(workdir,
                                     'ft1_filtered%s.fits'%self.config['file_suffix'])        
        self._ltcube=join(workdir,
                          'ltcube%s.fits'%self.config['file_suffix'])
        self._ccube_file=join(workdir,
                             'ccube%s.fits'%self.config['file_suffix'])
        self._mcube_file=join(workdir,
                              'mcube%s.fits'%self.config['file_suffix'])
        self._srcmap_file=join(workdir,
                               'srcmap%s.fits'%self.config['file_suffix'])
        self._bexpmap_file=join(workdir,
                                'bexpmap%s.fits'%self.config['file_suffix'])
        self._bexpmap_roi_file=join(workdir,
                                      'bexpmap_roi%s.fits'%self.config['file_suffix'])        
        self._srcmdl_file=join(workdir,
                               'srcmdl%s.xml'%self.config['file_suffix'])

        self._enumbins = np.round(self.config['binning']['binsperdec']*
                                 np.log10(self.config['selection']['emax']/
                                          self.config['selection']['emin']))
        self._enumbins = int(self._enumbins)
        self._ebin_edges = np.linspace(np.log10(self.config['selection']['emin']),
                                       np.log10(self.config['selection']['emax']),
                                       self._enumbins+1)
        self._ebin_center = 0.5*(self._ebin_edges[1:] + self._ebin_edges[:-1])
        
        if self.config['binning']['npix'] is None:
            self._npix = int(np.round(self.config['binning']['roiwidth']/
                                      self.config['binning']['binsz']))
        else:
            self._npix = self.config['binning']['npix']

        if self.config['selection']['radius'] is None:
            self._config['selection']['radius'] = float(np.sqrt(2.)*0.5*self.npix*
                                                        self.config['binning']['binsz']+0.5)
            self.logger.info('Automatically setting selection radius to %s deg'%
                             self.config['selection']['radius'])

        if self.config['binning']['coordsys'] == 'CEL':
            self._xref=float(self.roi.skydir.ra.deg)
            self._yref=float(self.roi.skydir.dec.deg)
        elif self.config['binning']['coordsys'] == 'GAL':
            self._xref=float(self.roi.skydir.galactic.l.deg)
            self._yref=float(self.roi.skydir.galactic.b.deg)
        else:
            raise Exception('Unrecognized coord system: ' +
                            self.config['binning']['coordsys'])
            
        self._like = None

        self._wcs = create_wcs(self.roi.skydir,
                               coordsys=self.config['binning']['coordsys'],
                               projection=self.config['binning']['proj'],
                               cdelt=self.binsz,crpix=1.0+0.5*(self._npix-1),
                               naxis=3)
        self._wcs.wcs.crpix[2]=1
        self._wcs.wcs.crval[2]=10**self.energies[0]
        self._wcs.wcs.cdelt[2]=10**self.energies[1]-10**self.energies[0]
        self._wcs.wcs.ctype[2]='Energy'
        
        self.print_config(self.logger,loglevel=logging.DEBUG)
            
    @property
    def roi(self):
        return self._roi

    @property
    def like(self):
        return self._like

    @property
    def name(self):
        return self._name

    @property
    def energies(self):
        return self._ebin_edges

    @property
    def enumbins(self):
        return len(self._ebin_edges)-1

    @property
    def npix(self):
        return self._npix

    @property
    def binsz(self):
        return self.config['binning']['binsz']
    
    @property
    def roiwidth(self):
        return self._npix*self.config['binning']['binsz']

    @property
    def wcs(self):
        return self._wcs

    def add_source(self,name,src_dict,free=False):
        """Add a new source to the model with the properties defined
        in the input dictionary."""

        if isinstance(src_dict,dict):
            src_dict['name'] = name
            src = self.roi.create_source(src_dict)
        else:
            src = src_dict
            self.roi.load_source(src)

        self.make_template(src,self.config['file_suffix'])
            
        if src['SpatialType'] == 'PointSource':        
            #pylike_src = pyLike.PointSource(0, 0,
#            pylike_src = pyLike.PointSource(src.skydir.ra.deg,src.skydir.dec.deg,
#                                            self.like.logLike.observation())

            pylike_src = pyLike.PointSource(self.like.logLike.observation())
            pylike_src.setDir(src.skydir.ra.deg,src.skydir.dec.deg,False,False)
        elif src['SpatialType'] == 'SpatialMap':        
            sm = pyLike.SpatialMap(src['Spatial_Filename'])
            pylike_src = pyLike.DiffuseSource(sm,self.like.logLike.observation(),False)
        elif src['SpatialType'] == 'MapCubeFunction':
            mcf = pyLike.MapCubeFunction2(src['Spatial_Filename'])
            pylike_src = pyLike.DiffuseSource(mcf,self.like.logLike.observation(),False)
        else:
            raise Exception('Unrecognized spatial type: %s'%src['SpatialType'])

        pl = pyLike.SourceFactory_funcFactory().create(src['SpectrumType'])

        for k,v in src.spectral_pars.items():
            par = pl.getParam(k)
            par.setValue(float(v['value']))
            par.setBounds(float(v['min']),float(v['max']))
            par.setScale(float(v['scale']))
            par.setFree(False)
            pl.setParam(par)
            
        pylike_src.setSpectrum(pl)
        pylike_src.setName(src.name)

        # Initialize source as free/fixed
        pylike_src.spectrum().normPar().setFree(free)
        self.like.addSource(pylike_src)
        self.like.syncSrcParams(name)

    def delete_source(self,name,save_template=True):

        self.logger.info('Deleting source ' + name)
        
        self.like.deleteSource(name)
        self.like.logLike.eraseSourceMap(name)
        src = self.roi.get_source_by_name(name)

        if not save_template and os.path.isfile(src['Spatial_Filename']):
            os.remove(src['Spatial_Filename'])
        
        self.roi.delete_sources([src])
        
    def delete_sources(self,srcs):
        for s in srcs:
            if self.like: self.like.deleteSource(s.name)
        self._roi.delete_sources(srcs)

    def set_edisp_flag(self,name,flag=True):
        src = self._roi.get_source_by_name(name)
        name = src.name        
        self.like[name].src.set_edisp_flag(flag)         
        
    def setEnergyRange(self,emin,emax):
        imin = int(valToEdge(self.energies,emin)[0])
        imax = int(valToEdge(self.energies,emax)[0])

        if imin-imax == 0:
            imin = len(self.energies)-1
            imax = len(self.energies)-1
        
        self.like.selectEbounds(int(imin),int(imax))

    def countsMap(self):
        """Return 3-D counts map as a numpy array."""
        z = self.like.logLike.countsMap().data()
        z = np.array(z).reshape(self.enumbins,self.npix,self.npix)
        return z

    def expMap(self):
        """Return the exposure map."""
        pass
    
    def modelCountsMap(self,name=None):
        """Return the model counts map for a single source or for the
        sum of all sources in the ROI."""
        
        v = pyLike.FloatVector(self.npix**2*self.enumbins)

        self.like.logLike.buildFixedModelWts()
        if not self.like.logLike.fixedModelUpdated():
            self.like.logLike.buildFixedModelWts(True)
            
        if name is None:
            self.like.logLike.computeModelMap(v)
        elif name == 'all':            
            for name in self.like.sourceNames():
                model = self.like.logLike.sourceMap(name)
                self.like.logLike.updateModelMap(v,model)
        elif isinstance(name,list):
            for n in name:
                model = self.like.logLike.sourceMap(n)
                self.like.logLike.updateModelMap(v,model)
        else:
            model = self.like.logLike.sourceMap(name)
            self.like.logLike.updateModelMap(v,model)
            
        z = np.array(v).reshape(self.enumbins,self.npix,self.npix)
        return z
        
    def modelCountsSpectrum(self,name,emin,emax):

        cs = np.array(self.like.logLike.modelCountsSpectrum(name))
        imin = valToEdge(self.energies,emin)[0]
        imax = valToEdge(self.energies,emax)[0]        
        if imax <= imin: raise Exception('Invalid energy range.')        
        return cs[imin:imax]
        
    def setup(self,xmlmodel=None):
        """Run pre-processing step."""

        # Write ROI XML
        self.roi.write_xml(self._srcmdl_file)
        roi_center = self.roi.skydir
        
        # Run gtselect and gtmktime
        kw_gtselect = dict(infile=self.config['data']['evfile'],
                           outfile=self._ft1_file,
                           ra=roi_center.ra.deg, dec=roi_center.dec.deg,
                           rad=self.config['selection']['radius'],
                           convtype=self.config['selection']['convtype'],
                           evtype=self.config['selection']['evtype'],
                           evclass=self.config['selection']['evclass'],
                           tmin=self.config['selection']['tmin'],
                           tmax=self.config['selection']['tmax'],
                           emin=self.config['selection']['emin'],
                           emax=self.config['selection']['emax'],
                           zmax=self.config['selection']['zmax'],
                           chatter=self.config['logging']['chatter'])

        kw_gtmktime = dict(evfile=self._ft1_file,
                           outfile=self._ft1_filtered_file,
                           scfile=self.config['data']['scfile'],
                           roicut=self.config['selection']['roicut'],
                           filter=self.config['selection']['filter'])

        if not os.path.isfile(self._ft1_file):
            run_gtapp('gtselect',self.logger,kw_gtselect)
            run_gtapp('gtmktime',self.logger,kw_gtmktime)
            os.system('mv %s %s'%(self._ft1_filtered_file,self._ft1_file))
        else:
            self.logger.info('Skipping gtselect')
            
        # Run gtltcube
        kw = dict(evfile=self._ft1_file,
                  scfile=self.config['data']['scfile'],
                  outfile=self._ltcube,
                  zmax=self.config['selection']['zmax'])
        
        if self.config['data']['ltcube'] is not None:
            self._ltcube = os.path.expandvars(self.config['data']['ltcube'])
        elif not os.path.isfile(self._ltcube):             
            run_gtapp('gtltcube',self.logger,kw)
        else:
            self.logger.info('Skipping gtltcube')


            
        self._ltc = LTCube.create(self._ltcube)

        self.logger.info('Creating PSF model')
        self._psf = PSFModel(self.roi.skydir,self._ltc,
                             self.config['gtlike']['irfs'],
                             self.config['selection']['evtype'],
                             np.linspace(1.0,6.0,81))
        
        # Run gtbin
        kw = dict(algorithm='ccube',
                  nxpix=self.npix, nypix=self.npix,
                  binsz=self.config['binning']['binsz'],
                  evfile=self._ft1_file,
                  outfile=self._ccube_file,
                  scfile=self.config['data']['scfile'],
                  xref=self._xref,
                  yref=self._yref,
                  axisrot=0,
                  proj=self.config['binning']['proj'],
                  ebinalg='LOG',
                  emin=self.config['selection']['emin'],
                  emax=self.config['selection']['emax'],
                  enumbins=self._enumbins,
                  coordsys=self.config['binning']['coordsys'],
                  chatter=self.config['logging']['chatter'])
        
        if not os.path.isfile(self._ccube_file):
            run_gtapp('gtbin',self.logger,kw)            
        else:
            self.logger.info('Skipping gtbin')

        evtype = self.config['selection']['evtype']
            
        if self.config['gtlike']['irfs'] == 'CALDB':
            cmap = self._ccube_file
        else:
            cmap = 'none'
            
        # Run gtexpcube2
        kw = dict(infile=self._ltcube,cmap=cmap,
                  ebinalg='LOG',
                  emin=self.config['selection']['emin'],
                  emax=self.config['selection']['emax'],
                  enumbins=self._enumbins,
                  outfile=self._bexpmap_file, proj='CAR',
                  nxpix=360, nypix=180, binsz=1,
                  xref=0.0,yref=0.0,
                  evtype=evtype,
                  irfs=self.config['gtlike']['irfs'],
                  coordsys=self.config['binning']['coordsys'],
                  chatter=self.config['logging']['chatter'])

        if not os.path.isfile(self._bexpmap_file):
            run_gtapp('gtexpcube2',self.logger,kw)              
        else:
            self.logger.info('Skipping gtexpcube')

        
        kw = dict(infile=self._ltcube,cmap='none',
                  ebinalg='LOG',
                  emin=self.config['selection']['emin'],
                  emax=self.config['selection']['emax'],
                  enumbins=self._enumbins,
                  outfile=self._bexpmap_roi_file, proj='CAR',
                  nxpix=self.npix, nypix=self.npix,
                  binsz=self.config['binning']['binsz'],
                  xref=self._xref,yref=self._yref,
                  evtype=self.config['selection']['evtype'],
                  irfs=self.config['gtlike']['irfs'],
                  coordsys=self.config['binning']['coordsys'],
                  chatter=self.config['logging']['chatter'])

        if not os.path.isfile(self._bexpmap_roi_file):
            run_gtapp('gtexpcube2',self.logger,kw)              
        else:
            self.logger.info('Skipping local gtexpcube')
        
        # Run gtsrcmaps
        kw = dict(scfile=self.config['data']['scfile'],
                  expcube=self._ltcube,
                  cmap=self._ccube_file,
                  srcmdl=self._srcmdl_file,
                  bexpmap=self._bexpmap_file,
                  outfile=self._srcmap_file,
                  irfs=self.config['gtlike']['irfs'],
                  evtype=evtype,
                  rfactor=self.config['gtlike']['rfactor'],
#                   resample=self.config['resample'],
                  minbinsz=self.config['gtlike']['minbinsz'],
                  chatter=self.config['logging']['chatter'],
                  emapbnds='no' ) 

        if not os.path.isfile(self._srcmap_file):
            if self.config['gtlike']['srcmap'] and self.config['gtlike']['bexpmap']:
                self.make_scaled_srcmap()
            else:
                run_gtapp('gtsrcmaps',self.logger,kw)
        else:
            self.logger.info('Skipping gtsrcmaps')

        # Create BinnedObs
        self.logger.info('Creating BinnedObs')
        kw = dict(srcMaps=self._srcmap_file,expCube=self._ltcube,
                  binnedExpMap=self._bexpmap_file,
                  irfs=self.config['gtlike']['irfs'])
        self.logger.info(kw)
        
        self._obs=ba.BinnedObs(**kw)

        # Create BinnedAnalysis
        self.logger.info('Creating BinnedAnalysis')
        self._like = BinnedAnalysis(binnedData=self._obs,
                                    srcModel=self._srcmdl_file,
                                    optimizer='MINUIT',
                                    convolve=self.config['gtlike']['convolve'],
                                    resample=self.config['gtlike']['resample'],
                                    minbinsz=self.config['gtlike']['minbinsz'],
                                    resamp_fact=self.config['gtlike']['rfactor'])

#        print self.like.logLike.use_single_fixed_map()
#        self.like.logLike.set_use_single_fixed_map(False)
#        print self.like.logLike.use_single_fixed_map()
        
        if self.config['gtlike']['edisp']:
            self.logger.info('Enabling energy dispersion')
            self.like.logLike.set_edisp_flag(True)

        for s in self.config['gtlike']['edisp_disable']: 
            self.logger.info('Disabling energy dispersion for %s'%s)
            self.set_edisp_flag(s,False)
                       
        self.logger.info('Finished setup')

    def make_scaled_srcmap(self):
        """Make an exposure cube with the same binning as the counts map."""

        self.logger.info('Computing scaled source map.')
        
        bexp0 = pyfits.open(self._bexpmap_roi_file)
        bexp1 = pyfits.open(self.config['gtlike']['bexpmap'])
        srcmap = pyfits.open(self.config['gtlike']['srcmap'])

        if bexp0[0].data.shape != bexp1[0].data.shape:
            raise Exception('Wrong shape for input exposure map file.')
        
        bexp_ratio = bexp0[0].data/bexp1[0].data
        
        self.logger.info('Min/Med/Max exposure correction: %f %f %f'%(np.min(bexp_ratio),
                                                                      np.median(bexp_ratio),
                                                                      np.max(bexp_ratio)))
        
        for hdu in srcmap[1:]:

            if hdu.name == 'GTI': continue
            if hdu.name == 'EBOUNDS': continue
            hdu.data *= bexp_ratio
        
        srcmap.writeto(self._srcmap_file,clobber=True)

        
    def generate_model_map(self,model_name=None,name=None):
        """Generate a counts model map from the in-memory source map
        data structures."""
        
        if model_name is None: suffix = self.config['file_suffix']
        else:
            suffix = '_%s%s'%(model_name,self.config['file_suffix'])

        self.logger.info('Generating model map for component %s'%self.name)
            
        outfile = os.path.join(self.config['fileio']['workdir'],'mcube%s.fits'%(suffix))        
        h = pyfits.open(self._ccube_file)        
        counts = self.modelCountsMap(name)
        write_fits_image(counts,self.wcs,outfile)

        return counts

    def make_template(self,src,suffix):

        if src['SpatialModel'] == 'PointSource' or src['SpatialModel'] == 'Gaussian':
            pass
        elif src['SpatialModel'] == 'PSFSource':            
            template_file = os.path.join(self.config['fileio']['workdir'],
                                         '%s_template_psf%s.fits'%(src.name,suffix))
            make_psf_mapcube(src.skydir,self._psf,template_file,npix=self.npix,
                             cdelt=self.config['binning']['binsz'],rebin=4)
            src['Spatial_Filename'] = template_file
        elif src['SpatialModel'] == 'CGaussianSource':            
            template_file = os.path.join(self.config['fileio']['workdir'],
                                         '%s_template_cgauss_%05.3f%s.fits'%(src.name,src['SpatialWidth'],
                                                                             suffix))  
            make_cgauss_mapcube(src.skydir,self._psf,src['SpatialWidth'],template_file,
                                npix=self.npix,
                                cdelt=self.config['binning']['binsz'],rebin=4)
            src['Spatial_Filename'] = template_file

        elif src['SpatialModel'] == 'GaussianSource':
            template_file = os.path.join(self.config['fileio']['workdir'],
                                         '%s_template_gauss_%05.3f%s.fits'%(src.name,src['SpatialWidth'],
                                                                            suffix))
            make_gaussian_spatial_map(src.skydir,src['SpatialWidth'],template_file,npix=500)
            src['Spatial_Filename'] = template_file
        elif src['SpatialModel'] == 'DiskSource':
            template_file = os.path.join(self.config['fileio']['workdir'],
                                         '%s_template_disk_%05.3f%s.fits'%(src.name,src['SpatialWidth'],
                                                                           suffix))
            make_disk_spatial_map(src.skydir,src['SpatialWidth'],template_file,npix=500)
            src['Spatial_Filename'] = template_file
        else:
            raise Exception('Unrecognized SpatialModel: ' + src['SpatialModel'] +
                            '\n Valid models: PointSource, GaussianSource, DiskSource, PSFSource ')
    
    def generate_model(self,model_name=None,outfile=None):
        """Generate a counts model map from an XML model file using
        gtmodel.

        Parameters
        ----------

        model_name : str
        
            Name of the model.  If no name is given it will use 
            the baseline model.

        outfile : str

            Override the name of the output model file.
            
        """

        if model_name is not None:
            model_name = os.path.splitext(model_name)[0]
        
        if model_name is None or model_name == '': srcmdl = self._srcmdl_file
        else: srcmdl = self.get_model_path(model_name)

        if not os.path.isfile(srcmdl):
            raise Exception("Model file does not exist: %s"%srcmdl)

        if model_name is None: suffix = self.config['file_suffix']
        else:
            suffix = '_%s%s'%(model_name,self.config['file_suffix'])
        
        outfile = os.path.join(self.config['fileio']['workdir'],'mcube%s.fits'%(suffix))
        
        # May consider generating a custom source model file
        if not os.path.isfile(outfile):

            kw = dict(srcmaps = self._srcmap_file,
                      srcmdl  = srcmdl,
                      bexpmap = self._bexpmap_file,
                      outfile = outfile,
                      expcube = self._ltcube,
                      irfs    = self.config['gtlike']['irfs'],
                      evtype  = self.config['selection']['evtype'],
                      edisp   = bool(self.config['gtlike']['edisp']),
                      outtype = 'ccube',
                      chatter = self.config['logging']['chatter'])
            
            run_gtapp('gtmodel',self.logger,kw)       
        else:
            self.logger.info('Skipping gtmodel')
            

    def load_xml(self,xmlfile):

        xmlfile = self.get_model_path(xmlfile)
        self.logger.info('Loading %s'%xmlfile)
        self.like.logLike.reReadXml(xmlfile)
#        
#        self._like = BinnedAnalysis(binnedData=self._obs,
#                                    srcModel=xmlfile,
#                                    optimizer='MINUIT')
            
    def write_xml(self,xmlfile):
        """Write the XML model for this analysis component."""
        
        xmlfile = self.get_model_path(xmlfile)            
        self.logger.info('Writing %s...'%xmlfile)
        self.like.writeXml(xmlfile)

    def get_model_path(self,name):
        """Infer the path to the XML model name."""
        
        name, ext = os.path.splitext(name)
        if not ext: ext = '.xml'
        xmlfile = name + self.config['file_suffix'] + ext

        if not os.path.isabs(xmlfile): 
            xmlfile = os.path.join(self.config['fileio']['workdir'],xmlfile)
            
#        if os.path.commonprefix([self.config['fileio']['workdir'],xmlfile]) \
#                != self.config['fileio']['workdir']:        
#            xmlfile = os.path.join(self.config['fileio']['workdir'],xmlfile)

        return xmlfile


    def tscube(self,xmlfile):

        xmlfile = self.get_model_path(xmlfile)
        
        outfile = os.path.join(self.config['fileio']['workdir'],
                               'tscube%s.fits'%(self.config['file_suffix']))
        
        kw = dict(cmap=self._ccube_file,
                  expcube=self._ltcube,
                  bexpmap =  self._bexpmap_file,
                  irfs    = self.config['gtlike']['irfs'],
                  evtype  = self.config['selection']['evtype'],
                  srcmdl  = xmlfile,
                  nxpix=self.npix, nypix=self.npix,
                  binsz=self.config['binning']['binsz'],
                  xref=float(self.roi.skydir.ra.deg),
                  yref=float(self.roi.skydir.dec.deg),
                  proj=self.config['binning']['proj'],
                  stlevel = 0,
                  coordsys=self.config['binning']['coordsys'],
                  outfile=outfile)
        
        run_gtapp('gttscube',self.logger,kw) 