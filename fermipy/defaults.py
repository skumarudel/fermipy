# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import absolute_import, division, print_function
import copy
from collections import OrderedDict
import numpy as np


def make_default_dict(d):

    o = {}
    for k, v in d.items():
        o[k] = copy.deepcopy(v[0])

    return o

DIFF_FLUX_UNIT = ':math:`\mathrm{cm}^{-2}~\mathrm{s}^{-1}~\mathrm{MeV}^{-1}`'
FLUX_UNIT = ':math:`\mathrm{cm}^{-2}~\mathrm{s}^{-1}`'
ENERGY_FLUX_UNIT = ':math:`\mathrm{MeV}~\mathrm{cm}^{-2}~\mathrm{s}^{-1}`'

# Options for defining input data files
data = {
    'evfile': (None, 'Path to FT1 file or list of FT1 files.', str),
    'scfile': (None, 'Path to FT2 (spacecraft) file.', str),
    'ltcube': (None, 'Path to livetime cube.  If none a livetime cube will be generated with ``gtmktime``.', str),
    'cacheft1': (True, 'Cache FT1 files when performing binned analysis.  If false then only the counts cube is retained.', bool),
}

# Options for data selection.
selection = {
    'emin': (None, 'Minimum Energy (MeV)', float),
    'emax': (None, 'Maximum Energy (MeV)', float),
    'logemin': (None, 'Minimum Energy (log10(MeV))', float),
    'logemax': (None, 'Maximum Energy (log10(MeV))', float),
    'tmin': (None, 'Minimum time (MET).', int),
    'tmax': (None, 'Maximum time (MET).', int),
    'zmax': (None, 'Maximum zenith angle.', float),
    'evclass': (None, 'Event class selection.', int),
    'evtype': (None, 'Event type selection.', int),
    'convtype': (None, 'Conversion type selection.', int),
    'phasemin': (None, 'Minimum pulsar phase', float),
    'phasemax': (None, 'Maximum pulsar phase', float),
    'target': (None, 'Choose an object on which to center the ROI.  '
                     'This option takes precendence over ra/dec or glon/glat.', str),
    'ra': (None, '', float),
    'dec': (None, '', float),
    'glat': (None, '', float),
    'glon': (None, '', float),
    'radius': (None, 'Radius of data selection.  If none this will be automatically set from the ROI size.', float),
    'filter': (None, 'Filter string for ``gtmktime`` selection.', str),
    'roicut': ('no', '', str)
}

# Options for ROI model.
model = {
    'src_radius':
        (None,
         'Radius of circular selection cut for inclusion of catalog sources in the model.  Includes sources within a circle of this radius '
         'centered on the ROI.  If this parameter is none then no selection is applied.  This selection '
         'will be ORed with the ``src_roiwidth`` selection.',
         float),
    'src_roiwidth':
        (None,
         'Width of square selection cut for inclusion of catalog sources in the model.  Includes sources within a square region with '
         'side ``src_roiwidth`` centered on the ROI.  If this parameter is '
         'none then no selection is applied.  This selection will be ORed with the ``src_radius`` selection.', float),
    'src_radius_roi':
        (None,
         'Half-width of ``src_roiwidth`` selection.  This parameter can be used in '
         'lieu of ``src_roiwidth``.',
         float),
    'isodiff': (None, 'Set the isotropic template.', list),
    'galdiff': (None, 'Set the galactic IEM mapcube.', list),
    'limbdiff': (None, '', list),
    'diffuse': (None, '', list),
    'sources': (None, '', list),
    'extdir': (None, 'Set a directory that will be searched for extended source FITS templates.  Template files in this directory '
               'will take precendence over catalog source templates with the same name.', str),
    'catalogs': (None, '', list),
    'merge_sources' :
        (True, 'Merge properties of sources that appear in multiple '
         'source catalogs.  If merge_sources=false then subsequent sources with '
         'the same name will be ignored.', bool),
    'assoc_xmatch_columns' :
        (['3FGL_Name'],'Choose a set of association columns on which to '
         'cross-match catalogs.',list),
    'extract_diffuse': (
        False, 'Extract a copy of all mapcube components centered on the ROI.',
        bool)
}

# Options for configuring likelihood analysis
gtlike = {
    'irfs': (None, 'Set the IRF string.', str),
    'edisp': (True, 'Enable the correction for energy dispersion.', bool),
    'edisp_disable': (None,
                      'Provide a list of sources for which the edisp '
                      'correction should be disabled.',
                      list),
#    'likelihood': ('binned', '', str),
    'minbinsz': (0.05, 'Set the minimum bin size used for resampling diffuse maps.', float),
    'rfactor': (2, '', int),
    'convolve': (True, '', bool),
    'resample': (True, '', bool),
    'srcmap': (None, '', str),
    'bexpmap': (None, '', str),
    'wmap': (None, 'Likelihood weights map.', str),
    'llscan_npts': (20,'Number of evaluation points to use when performing a likelihood scan.',int),
    'src_expscale': (None, 'Dictionary of exposure corrections for individual sources keyed to source name.  The exposure '
                     'for a given source will be scaled by this value.  A value of 1.0 corresponds to the nominal exposure.', dict),
    'expscale': (None, 'Exposure correction that is applied to all sources in the analysis component.  '
                 'This correction is superseded by `src_expscale` if it is defined for a source.', float),
}

# Options for binning.
binning = {
    'projtype': ('WCS', 'Projection mode (WCS or HPX).', str),
    'proj': ('AIT', 'Spatial projection for WCS mode.', str),
    'coordsys': ('CEL', 'Coordinate system of the spatial projection (CEL or GAL).', str),
    'npix':
        (None,
         'Number of pixels.  If none then this will be set from ``roiwidth`` '
         'and ``binsz``.', int),
    'roiwidth': (10.0,
                 'Width of the ROI in degrees.  The number of pixels in each spatial dimension will be set from ``roiwidth`` / ``binsz`` (rounded up).',
                 float),
    'binsz': (0.1, 'Spatial bin size in degrees.', float),
    'binsperdec': (8, 'Number of energy bins per decade.', float),
    'enumbins': (
        None,
        'Number of energy bins.  If none this will be inferred from energy '
        'range and ``binsperdec`` parameter.', int),
    'hpx_ordering_scheme': ('RING', 'HEALPix Ordering Scheme', str),
    'hpx_order': (10, 'Order of the map (int between 0 and 12, included)', int),
    'hpx_ebin': (True, 'Include energy binning', bool)
}

# Options related to I/O and output file bookkeeping
fileio = {
    'outdir': (None, 'Path of the output directory.  If none this will default to the directory containing the configuration file.', str),
    'scratchdir': ('/scratch', 'Path to the scratch directory.  If ``usescratch`` is True then a temporary working directory '
                   'will be created under this directory.', str),
    'workdir': (None, 'Path to the working directory.', str),
    'logfile': (None, 'Path to log file.  If None then log will be written to fermipy.log.', str),
    'savefits': (True, 'Save intermediate FITS files.', bool),
    'workdir_regex' : (['\.fits$|\.fit$|\.xml$|\.npy$'],
                       'Stage files to the working directory that match at least one of the regular expressions in this list.  '
                       'This option only takes effect when ``usescratch`` is True.', list),
    'outdir_regex' : (['\.fits$|\.fit$|\.xml$|\.npy$|\.png$|\.pdf$|\.yaml$'],
                      'Stage files to the output directory that match at least one of the regular expressions in this list.  '
                      'This option only takes effect when ``usescratch`` is True.', list),
    'usescratch': (
        False, 'Run analysis in a temporary working directory under ``scratchdir``.', bool),
}

logging = {
    'chatter': (3, 'Set the chatter parameter of the STs.', int),
    'verbosity': (3, '', int)
}

# Options related to likelihood optimizer
optimizer = {
    'optimizer':
        ('MINUIT', 'Set the optimization algorithm to use when maximizing the '
                   'likelihood function.', str),
    'tol': (1E-3, 'Set the optimizer tolerance.', float),
    'max_iter': (100, 'Maximum number of iterations for the Newtons method fitter.', int),
    'init_lambda': (1E-4, 'Initial value of damping parameter for step size calculation '
                    'when using the NEWTON fitter.  A value of zero disables damping.', float),
    'retries': (3, 'Set the number of times to retry the fit when the fit quality is less than ``min_fit_quality``.', int),
    'min_fit_quality': (2, 'Set the minimum fit quality.', int),
    'verbosity': (0, '', int)
}

fit_output = {
    'edm' : (None, 'Estimated distance to maximum of log-likelihood function.',float,'float'),
    'fit_status' : (None, 'Optimizer return code (0 = ok).',int,'int'),
    'fit_quality' : (None, 'Fit quality parameter for MINUIT and NEWMINUIT optimizers (3 - Full accurate covariance matrix, '
                     '2 - Full matrix, but forced positive-definite (i.e. not accurate), '
                     '1 - Diagonal approximation only, not accurate, '
                     '0 - Error matrix not calculated at all)',int,'int'),
    'covariance' : (None, 'Covariance matrix between free parameters of the fit.',np.ndarray, '`~numpy.ndarray`'),
    'correlation' : (None, 'Correlation matrix between free parameters of the fit.',np.ndarray, '`~numpy.ndarray`'),
    'dloglike' : (None, 'Improvement in log-likehood value.',float,'float'),
    'loglike' : (None, 'Post-fit log-likehood value.',float,'float'),
    'values' : (None, 'Vector of best-fit parameter values (unscaled).',np.ndarray, '`~numpy.ndarray`'),
    'errors' : (None, 'Vector of parameter errors (unscaled).',np.ndarray, '`~numpy.ndarray`'),
    'config' : (None, 'Copy of input configuration to this method.',dict,'dict'),
}

# MC options
mc = {
    'seed' : (None, '', int)
}

# ROI Optimization
roiopt = {
    'npred_threshold': (1.0, '', float),
    'npred_frac': (0.95, '', float),
    'shape_ts_threshold':
        (25.0, 'Threshold on source TS used for determining the sources '
         'that will be fit in the third optimization step.', float),
    'max_free_sources' :
        (5, 'Maximum number of sources that will be fit simultaneously in '
         'the first optimization step.', int),
    'skip' :
        (None, 'List of str source names to skip while optimizing.', list)
}

roiopt_output = {
    'loglike0' : (None, 'Pre-optimization log-likelihood value.',float,'float'),
    'loglike1' : (None, 'Post-optimization log-likelihood value.',float,'float'),
    'dloglike' : (None, 'Improvement in log-likehood value.',float,'float'),
    'config' : (None, 'Copy of input configuration to this method.',dict,'dict'),
}

# Residual Maps
residmap = {
    'model': (None, 'Dictionary defining the properties of the test source.  By default the test source will be a PointSource with an Index 2 power-law specturm.', dict),
    'loge_bounds': (None, 'Lower and upper energy bounds in log10(E/MeV).  By default the calculation will be performed over the full analysis energy range.', list),
}

# TS Map
tsmap = {
    'model': (None, 'Dictionary defining the properties of the test source.', dict),
    'multithread': (False, 'Split the TS map calculation across multiple cores.', bool),
    'max_kernel_radius': (3.0, '', float),
    'loge_bounds': (None, 'Lower and upper energy bounds in log10(E/MeV).  By default the calculation will be performed over the full analysis energy range.', list),
}

# TS Cube
tscube = {
    'model': (None, 'Dictionary defining the properties of the test source.  By default the test source will be a PointSource with an Index 2 power-law specturm.', dict),
    'do_sed': (True, 'Compute the energy bin-by-bin fits', bool),
    'nnorm': (10, 'Number of points in the likelihood v. normalization scan', int),
    'norm_sigma': (5.0, 'Number of sigma to use for the scan range ', float),
    'cov_scale_bb': (-1.0, 'Scale factor to apply to global fitting '
                      'cov. matrix in broadband fits. ( < 0 -> no prior ) ', float),
    'cov_scale': (-1.0, 'Scale factor to apply to broadband fitting cov. '
                   'matrix in bin-by-bin fits ( < 0 -> fixed ) ', float),
    'tol': (1E-3, 'Critetia for fit convergence (estimated vertical distance to min < tol )', float),
    'max_iter': (30, 'Maximum number of iterations for the Newtons method fitter.', int),
    'tol_type': (0, 'Absoulte (0) or relative (1) criteria for convergence.', int),
    'remake_test_source': (False, 'If true, recomputes the test source image (otherwise just shifts it)', bool),
    'st_scan_level': (0, 'Level to which to do ST-based fitting (for testing)', int),
    'init_lambda': (0, 'Initial value of damping parameter for newton step size calculation.', float),
}

# Options for Source Finder
sourcefind = {
    'model': (None, 'Set the source model dictionary.  By default the test source will be a PointSource with an Index 2 power-law specturm.', dict),
    'min_separation': (1.0, 'Set the minimum separation in deg for sources added in each iteration.', float),
    'sqrt_ts_threshold': (5.0, 'Set the threshold on sqrt(TS).', float),
    'max_iter': (3, 'Set the number of search iterations.', int),
    'sources_per_iter': (3, '', int),
    'tsmap_fitter': ('tsmap', 'Set the method for generating the TS map.', str)
}

# Options for SED analysis
sed = {
    'bin_index': (2.0, 'Spectral index that will be use when fitting the energy distribution within an energy bin.', float),
    'use_local_index': (False, 'Use a power-law approximation to the shape of the global spectrum in '
                        'each bin.  If this is false then a constant index set to `bin_index` '
                        'will be used.', bool),
    'fix_background': (True, 'Fix background normalization parameters when fitting the '
                       'source flux in each energy bin.  If True background normalizations will be profiled '
                       'with a prior on their value with strength set by ``cov_scale``.', bool),
    'ul_confidence': (0.95, 'Confidence level for upper limit calculation.',
                      float),
    'cov_scale' : (3.0,'Scale factor that sets the strength of the prior on nuisance '
                   'parameters when ``fix_background``=True.  Setting this to None disables the prior.',float)
}

# Output for SED analysis
sed_output = OrderedDict((
    ('logemin', (None, 'Lower edges of SED energy bins (log10(E/MeV)).', np.ndarray, '`~numpy.ndarray`')),
    ('logemax', (None, 'Upper edges of SED energy bins (log10(E/MeV)).', np.ndarray, '`~numpy.ndarray`')),
    ('logectr', (None, 'Centers of SED energy bins (log10(E/MeV)).', np.ndarray, '`~numpy.ndarray`')),
    ('emin', (None, 'Lower edges of SED energy bins (MeV).', np.ndarray, '`~numpy.ndarray`')),
    ('emax', (None, 'Upper edges of SED energy bins (MeV).', np.ndarray, '`~numpy.ndarray`')),
    ('ectr', (None, 'Centers of SED energy bins (MeV).', np.ndarray, '`~numpy.ndarray`')),
    ('ref_flux', (None, 'Flux of the reference model in each bin (%s).'%FLUX_UNIT,  np.ndarray, '`~numpy.ndarray`')),
    ('ref_eflux', (None, 'Energy flux of the reference model in each bin (%s).'%ENERGY_FLUX_UNIT,  np.ndarray, '`~numpy.ndarray`')), 
    ('ref_dfde', (None, 'Differential flux of the reference model evaluated at the bin center (%s)'%DIFF_FLUX_UNIT,  np.ndarray, '`~numpy.ndarray`')), 
    ('ref_dfde_emin', (None, 'Differential flux of the reference model evaluated at the lower bin edge (%s)'%DIFF_FLUX_UNIT,  np.ndarray, '`~numpy.ndarray`')), 
    ('ref_dfde_emax', (None, 'Differential flux of the reference model evaluated at the upper bin edge (%s)'%DIFF_FLUX_UNIT,  np.ndarray, '`~numpy.ndarray`')), 
    ('ref_e2dfde', (None, 'E^2 x the differential flux of the reference model evaluated at the bin center (%s)'%ENERGY_FLUX_UNIT,  np.ndarray, '`~numpy.ndarray`')), 
    ('ref_npred', (None, 'Number of predicted counts in the reference model in each bin.',  np.ndarray, '`~numpy.ndarray`')), 
    ('norm', (None, 'Normalization in each bin in units of the reference model.',  np.ndarray, '`~numpy.ndarray`')),     
    ('flux', (None, 'Flux in each bin (%s).'%FLUX_UNIT,np.ndarray, '`~numpy.ndarray`')),
    ('eflux', (None, 'Energy flux in each bin (%s).'%ENERGY_FLUX_UNIT,np.ndarray,'`~numpy.ndarray`')),
    ('dfde', (None, 'Differential flux in each bin (%s).'%DIFF_FLUX_UNIT,np.ndarray,'`~numpy.ndarray`')),
    ('e2dfde', (None, 'E^2 x the differential flux in each bin (%s).'%ENERGY_FLUX_UNIT,np.ndarray,'`~numpy.ndarray`')),
    ('dfde_err', (None, '1-sigma error on dfde evaluated from likelihood curvature.',np.ndarray,'`~numpy.ndarray`')),
    ('dfde_err_lo', (None, 'Lower 1-sigma error on dfde evaluated from the profile likelihood (MINOS errors).',np.ndarray,'`~numpy.ndarray`')),
    ('dfde_err_hi', (None, 'Upper 1-sigma error on dfde evaluated from the profile likelihood (MINOS errors).',np.ndarray,'`~numpy.ndarray`')),
    ('dfde_ul95', (None, '95% CL upper limit on dfde evaluated from the profile likelihood (MINOS errors).',np.ndarray,'`~numpy.ndarray`')),
    ('dfde_ul', (None, 'Upper limit on dfde evaluated from the profile likelihood using a CL = ``ul_confidence``.',np.ndarray,'`~numpy.ndarray`')),
    ('e2dfde_err', (None, '1-sigma error on e2dfde evaluated from likelihood curvature.',np.ndarray,'`~numpy.ndarray`')),
    ('e2dfde_err_lo', (None, 'Lower 1-sigma error on e2dfde evaluated from the profile likelihood (MINOS errors).',np.ndarray,'`~numpy.ndarray`')),
    ('e2dfde_err_hi', (None, 'Upper 1-sigma error on e2dfde evaluated from the profile likelihood (MINOS errors).',np.ndarray,'`~numpy.ndarray`')),
    ('e2dfde_ul95', (None, '95% CL upper limit on e2dfde evaluated from the profile likelihood (MINOS errors).',np.ndarray,'`~numpy.ndarray`')),
    ('e2dfde_ul', (None, 'Upper limit on e2dfde evaluated from the profile likelihood using a CL = ``ul_confidence``.',np.ndarray,'`~numpy.ndarray`')),
    ('ts', (None, 'Test statistic.',np.ndarray,'`~numpy.ndarray`')),
    ('loglike', (None, 'Log-likelihood of model for the best-fit amplitude.',np.ndarray,'`~numpy.ndarray`')),
    ('npred', (None, 'Number of model counts.',np.ndarray,'`~numpy.ndarray`')),
    ('fit_quality', (None, 'Fit quality parameter for MINUIT and NEWMINUIT optimizers (3 - Full accurate covariance matrix, '
                     '2 - Full matrix, but forced positive-definite (i.e. not accurate), '
                     '1 - Diagonal approximation only, not accurate, '
                     '0 - Error matrix not calculated at all).',np.ndarray,'`~numpy.ndarray`')),
    ('fit_status', (None, 'Fit status parameter (0=ok).',np.ndarray,'`~numpy.ndarray`')),
    ('index', (None, 'Spectral index of the power-law model used to fit this bin.',np.ndarray,'`~numpy.ndarray`')),
    ('lnlprofile', (None, 'Likelihood scan for each energy bin.',dict,'dict')),
    ('norm_scan', (None, 'Array of NxM normalization values for the profile likelihood scan in N '
                   'energy bins and M scan points.  A row-wise multiplication with '
                   'any of ``ref`` columns can be used to convert this matrix to the '
                   'respective unit.',
                   np.ndarray,'`~numpy.ndarray`')),
    ('dloglike_scan', (None, 'Array of NxM delta-loglikelihood values for the profile likelihood '
                       'scan in N energy bins and M scan points.',np.ndarray,'`~numpy.ndarray`')),
    ('loglike_scan', (None, 'Array of NxM loglikelihood values for the profile likelihood scan '
                      'in N energy bins and M scan points.',np.ndarray,'`~numpy.ndarray`')),
    ('params', (None, 'Dictionary of best-fit spectral parameters with 1-sigma uncertainties.',dict,'dict')),
    ('param_covariance', (None, 'Covariance matrix for the best-fit spectral parameters of the source.'
                          ,np.ndarray,'`~numpy.ndarray`')),
    ('param_names', (None, 'Array of names for the parameters in the global spectral parameterization of this source.',np.ndarray,'`~numpy.ndarray`')),
    ('param_values', (None, 'Array of parameter values.',np.ndarray,'`~numpy.ndarray`')),
    ('param_errors', (None, 'Array of parameter errors.',np.ndarray,'`~numpy.ndarray`')),
    ('model_flux', (None, 'Dictionary containing the differential flux uncertainty '
                    'band of the best-fit global spectral parameterization for the '
                    'source.',dict,'dict')),
    ('config', (None, 'Copy of input configuration to this method.',dict,'dict')),
))

# Options for extension analysis
extension = {
    'spatial_model': ('RadialGaussian', 'Spatial model use for extension test.', str),
    'width': (None, 'Parameter vector for scan over spatial extent.  If none then the parameter '
              'vector will be set from ``width_min``, ``width_max``, and ``width_nstep``.', list),
    'width_min': (0.01, 'Minimum value in degrees for the likelihood scan over spatial extent.', float),
    'width_max': (1.0, 'Maximum value in degrees for the likelihood scan over spatial extent.', float),
    'width_nstep': (21, 'Number of steps for the spatial likelihood scan.', int),
    'fix_background': (False, 'Fix any background parameters that are currently free in the model when '
                       'performing the likelihood scan over extension.', bool),
    'update': (False, 'Update the source model with the best-fit spatial extension.', bool),
    'save_model_map': (False, 'Save model counts cubes for the best-fit model of extension.', bool),
    'sqrt_ts_threshold': (None, 'Threshold on sqrt(TS_ext) that will be applied when ``update`` is True.  If None then no'
                          'threshold is applied.', float),
    'psf_scale_fn': (None, 'Tuple of vectors (logE,f) defining an energy-dependent PSF scaling function '
                     'that will be applied when building spatial models for the source of interest.  '
                     'The tuple (logE,f) defines the fractional corrections f at the sequence of energies '
                     'logE = log10(E/MeV) where f=0 means no correction.  The correction function f(E) is evaluated '
                     'by linearly interpolating the fractional correction factors f in log(E).  The '
                     'corrected PSF is given by P\'(x;E) = P(x/(1+f(E));E) where x is the angular separation.',
                     tuple),
}

extension_output = OrderedDict((
    ('width', (None, 'Vector of width values.',np.ndarray,'`~numpy.ndarray`')),
    ('dloglike', (None, 'Sequence of delta-log-likelihood values for each point in the profile likelihood scan.',np.ndarray,'`~numpy.ndarray`')),
    ('loglike', (None, 'Sequence of likelihood values for each point in the scan over the spatial extension.',np.ndarray,'`~numpy.ndarray`')),
    ('loglike_ptsrc', (np.nan,'Model log-Likelihood value of the best-fit point-source model.',float,'float')),
    ('loglike_ext', (np.nan,'Model log-Likelihood value of the best-fit extended source model.',float,'float')),
    ('loglike_base', (np.nan,'Model log-Likelihood value of the baseline model.',float,'float')),
    ('ext', (np.nan, 'Best-fit extension in degrees.',float,'float')),
    ('ext_err_hi', (np.nan, 'Upper (1 sigma) error on the best-fit extension in degrees.',float,'float')),
    ('ext_err_lo', (np.nan,'Lower (1 sigma) error on the best-fit extension in degrees.',float,'float')),
    ('ext_err', (np.nan,'Symmetric (1 sigma) error on the best-fit extension in degrees.',float,'float')),
    ('ext_ul95', (np.nan,'95% CL upper limit on the spatial extension in degrees.',float,'float')),
    ('ts_ext', (np.nan,'Test statistic for the extension hypothesis.',float,'float')),
    ('source_fit', ({},'Dictionary with parameters of the best-fit extended source model.',dict,'dict')),
    ('config', ({},'Copy of the input configuration to this method.',dict,'dict')),
))

# Options for localization analysis
localize = {
    'nstep': (5, 'Number of steps along each spatial dimension in the refined likelihood scan.', int),
    'dtheta_max': (0.3, 'Half-width of the search region in degrees used for the first pass of the localization search.', float),
    'fix_background': (True, 'Fix background parameters when fitting the '
                       'source flux in each energy bin.', bool),
    'update': (False, 'Update the source model with the best-fit position.', bool)
}

# Output for localization analysis
localize_output  = OrderedDict((
    ('ra', (np.nan,'Right ascension of best-fit position in deg.',float,'float')),
    ('dec', (np.nan,'Declination of best-fit position in deg.',float,'float')),
    ('glon', (np.nan,'Galactic Longitude of best-fit position in deg.',float,'float')),
    ('glat', (np.nan,'Galactic Latitude of best-fit position in deg.',float,'float')),
    ('offset', (np.nan,'Angular offset in deg between the old and new (localized) source positions.',float,'float')),
    ('sigma', (np.nan,'1-sigma positional uncertainty in deg.',float,'float')),
    ('r68', (np.nan,'68% positional uncertainty in deg.',float,'float')),
    ('r95', (np.nan,'95% positional uncertainty in deg.',float,'float')),
    ('r99', (np.nan,'99% positional uncertainty in deg.',float,'float')),
    ('sigmax', (np.nan,'1-sigma uncertainty in deg in longitude.',float,'float')),
    ('sigmay', (np.nan,'1-sigma uncertainty in deg in latitude.',float,'float')),
    ('sigma_semimajor', (np.nan,'1-sigma uncertainty in deg along major axis of uncertainty ellipse.',float,'float')),
    ('sigma_semiminor', (np.nan,'1-sigma uncertainty in deg along minor axis of uncertainty ellipse.',float,'float')),
    ('xpix', (np.nan,'Longitude pixel coordinate of best-fit position.',float,'float')),
    ('ypix', (np.nan,'Latitude pixel coordinate of best-fit position.',float,'float')),
    ('theta', (np.nan,'Position angle of uncertainty ellipse.',float,'float')),
    ('eccentricity', (np.nan,'Eccentricity of uncertainty ellipse defined as sqrt(1-b**2/a**2).',float,'float')),
    ('eccentricity2', (np.nan,'Eccentricity of uncertainty ellipse defined as sqrt(a**2/b**2-1).',float,'float')),    
    ('config', (None, 'Copy of the input parameters to this method.',dict,'dict')),
))

# Options for plotting
plotting = {
    'loge_bounds': (None, '', list),
    'catalogs': (None, '', list),
    'graticule_radii': (None, 'Define a list of radii at which circular graticules will be drawn.', list),
    'format': ('png', '', str),
    'cmap': ('ds9_b', 'Set the colormap for 2D plots.', str),
    'label_ts_threshold':
        (0., 'TS threshold for labeling sources in sky maps.  If None then no sources will be labeled.', float),    
}

# Source dictionary
source_output = OrderedDict((
    ('name', (None,'Name of the source.',str,'str')),
    ('Source_Name', (None,'Name of the source.',str,'str')),
    ('SpatialModel', (None,'Spatial model.',str,'str')),
    ('SpatialWidth', (None,'Spatial size parameter.',float,'float')),
    ('SpatialType', (None,'Spatial type string.  This corresponds to the type attribute of the spatialModel component in the XML model.',str,'str')),
    ('SourceType', (None,'Source type string (PointSource or DiffuseSource).',str,'str')),
    ('SpectrumType', (None,'Spectrum type string.  This corresponds to the type attribute of the spectrum component in the XML model (e.g. PowerLaw, LogParabola, etc.).',str,'str')),
    ('Spatial_Filename', (None,'Path to spatial template associated to this source.',str,'str')),
    ('Spectrum_Filename' , (None,'Path to file associated to the spectral model of this source.',str,'str')),
    ('ra', (np.nan,'Right ascension of the source in deg.',float,'float')),
    ('dec', (np.nan,'Declination of the source in deg.',float,'float')),
    ('glon', (np.nan,'Galactic Longitude of the source in deg.',float,'float')),
    ('glat', (np.nan,'Galactic Latitude of the source in deg.',float,'float')),
    ('offset_ra', (np.nan,'Angular offset from ROI center along RA.',float,'float')),
    ('offset_dec', (np.nan,'Angular offset from ROI center along DEC',float,'float')),
    ('offset_glon', (np.nan,'Angular offset from ROI center along GLON.',float,'float')),
    ('offset_glat', (np.nan,'Angular offset from ROI center along GLAT.',float,'float')),
    ('offset_roi_edge', (np.nan,'Distance from the edge of the ROI in deg.  Negative (positive) values '
                         'indicate locations inside (outside) the ROI.',float,'float')),
    ('offset', (np.nan,'Angular offset from ROI center.',float,'float')),
    ('pos_sigma', (np.nan,'1-sigma uncertainty (deg) on the source position.',float,'float')),
    ('pos_sigma_semimajor', (np.nan,'1-sigma uncertainty (deg) on the source position along major axis.',float,'float')),
    ('pos_sigma_semiminor', (np.nan,'1-sigma uncertainty (deg) on the source position along minor axis.',float,'float')),
    ('pos_angle', (np.nan,'Position angle (deg) of the positional uncertainty ellipse.',float,'float')),
    ('pos_r68', (np.nan,'68% uncertainty (deg) on the source position.',float,'float')),
    ('pos_r95', (np.nan,'95% uncertainty (deg) on the source position.',float,'float')),
    ('pos_r99', (np.nan,'99% uncertainty (deg) on the source position.',float,'float')),    
    ('ts', (np.nan,'Source test statistic.',float,'float')),
    ('loglike', (np.nan,'Log-likelihood of the model evaluated at the best-fit normalization of the source.',float,'float')),
    ('ts', (np.nan,'Source test statistic.',float,'float')),
    ('dloglike_scan', (np.array([np.nan]), 'Delta Log-likelihood values for likelihood scan of source normalization.',np.ndarray, '`~numpy.ndarray`')),
    ('eflux_scan', (np.array([np.nan]), 'Energy flux values for likelihood scan of source normalization.',np.ndarray, '`~numpy.ndarray`')),
    ('flux_scan', (np.array([np.nan]), 'Flux values for likelihood scan of source normalization.',np.ndarray, '`~numpy.ndarray`')),
    ('npred', (np.nan,'Number of predicted counts from this source integrated over the analysis energy range.',float,'float')),
    ('params', (None,'Dictionary of spectral parameters.',dict,'dict')),
    ('correlation', ({},'Dictionary of correlation coefficients.',dict,'dict')),    
    ('model_counts', (None,'Vector of predicted counts for this source in each analysis energy bin.',np.ndarray, '`~numpy.ndarray`')),
    ('sed', (None,'Output of SED analysis.  See :ref:`sed` for more information.',dict,'dict')),
    ('extension', (None,'Output of extension analysis.  See :ref:`extension` for more information.',dict,'dict')),
    ('localize', (None,'Output of localization analysis.  See :ref:`localization` for more information.',dict,'dict')),
    ('pivot_energy', (np.nan,'Decorrelation energy in MeV.',float,'float')),
    ('flux', (np.array([np.nan,np.nan]), 'Photon flux and uncertainty (%s) integrated over analysis energy range'%FLUX_UNIT,
             np.ndarray, '`~numpy.ndarray`')),
    ('flux100', (np.array([np.nan,np.nan]), 'Photon flux and uncertainty (%s) integrated from 100 MeV to 316 GeV.'%FLUX_UNIT,
                np.ndarray, '`~numpy.ndarray`')),
    ('flux1000', (np.array([np.nan,np.nan]), 'Photon flux and uncertainty (%s) integrated from 1 GeV to 316 GeV.'%FLUX_UNIT,
                 np.ndarray, '`~numpy.ndarray`')),
    ('flux10000', (np.array([np.nan,np.nan]), 'Photon flux and uncertainty (%s) integrated from 10 GeV to 316 GeV.'%FLUX_UNIT,
                  np.ndarray, '`~numpy.ndarray`')),
    ('flux_ul95', (np.nan, '95%' + ' CL upper limit on the photon flux (%s) integrated over analysis energy range'%FLUX_UNIT,
             float, 'float')),
    ('flux100_ul95', (np.nan, '95%' + ' CL upper limit on the photon flux (%s) integrated from 100 MeV to 316 GeV.'%FLUX_UNIT,
                float, 'float')),
    ('flux1000_ul95', (np.nan, '95%' + ' CL upper limit on the photon flux (%s) integrated from 1 GeV to 316 GeV.'%FLUX_UNIT,
                 float, 'float')),
    ('flux10000_ul95', (np.nan, '95%' + ' CL upper limit on the photon flux (%s) integrated from 10 GeV to 316 GeV.'%FLUX_UNIT,
                  float, 'float')),
    ('eflux', (np.array([np.nan,np.nan]), 'Energy flux and uncertainty (%s) integrated over analysis energy range'%ENERGY_FLUX_UNIT,
             np.ndarray, '`~numpy.ndarray`')),
    ('eflux100', (np.array([np.nan,np.nan]), 'Energy flux and uncertainty (%s) integrated from 100 MeV to 316 GeV.'%ENERGY_FLUX_UNIT,
                np.ndarray, '`~numpy.ndarray`')),
    ('eflux1000', (np.array([np.nan,np.nan]), 'Energy flux and uncertainty (%s) integrated from 1 GeV to 316 GeV.'%ENERGY_FLUX_UNIT,
                 np.ndarray, '`~numpy.ndarray`')),
    ('eflux10000', (np.array([np.nan,np.nan]), 'Energy flux and uncertainty (%s) integrated from 10 GeV to 316 GeV.'%ENERGY_FLUX_UNIT,
                  np.ndarray, '`~numpy.ndarray`')),
    ('eflux_ul95', (np.nan, '95%' + ' CL upper limit on the energy flux (%s) integrated over analysis energy range'%ENERGY_FLUX_UNIT,
             float, 'float')),
    ('eflux100_ul95', (np.nan, '95%' + ' CL upper limit on the energy flux (%s) integrated from 100 MeV to 316 GeV.'%ENERGY_FLUX_UNIT,
                float, 'float')),
    ('eflux1000_ul95', (np.nan, '95%' + ' CL upper limit on the energy flux (%s) integrated from 1 GeV to 316 GeV.'%ENERGY_FLUX_UNIT,
                 float, 'float')),
    ('eflux10000_ul95', (np.nan, '95%' + ' CL upper limit on the energy flux (%s) integrated from 10 GeV to 316 GeV.'%ENERGY_FLUX_UNIT,
                  float, 'float')),    
    ('dfde', (np.array([np.nan,np.nan]), 'Differential photon flux and uncertainty (%s) evaluated at the pivot energy.'%DIFF_FLUX_UNIT,
             np.ndarray, '`~numpy.ndarray`')),
    ('dfde100', (np.array([np.nan,np.nan]), 'Differential photon flux and uncertainty (%s) evaluated at 100 MeV.'%DIFF_FLUX_UNIT,
                np.ndarray, '`~numpy.ndarray`')),
    ('dfde1000', (np.array([np.nan,np.nan]), 'Differential photon flux and uncertainty (%s) evaluated at 1 GeV.'%DIFF_FLUX_UNIT,
                 np.ndarray, '`~numpy.ndarray`')),
    ('dfde10000', (np.array([np.nan,np.nan]), 'Differential photon flux and uncertainty (%s) evaluated at 10 GeV.'%DIFF_FLUX_UNIT,
                  np.ndarray, '`~numpy.ndarray`')),
    ('dfde_index', (np.array([np.nan,np.nan]), 'Logarithmic slope of the differential photon spectrum evaluated at the pivot energy.',
             np.ndarray, '`~numpy.ndarray`')),
    ('dfde100_index', (np.array([np.nan,np.nan]), 'Logarithmic slope of the differential photon spectrum evaluated at 100 MeV.',
                np.ndarray, '`~numpy.ndarray`')),
    ('dfde1000_index', (np.array([np.nan,np.nan]), 'Logarithmic slope of the differential photon spectrum evaluated evaluated at 1 GeV.',
                 np.ndarray, '`~numpy.ndarray`')),
    ('dfde10000_index', (np.array([np.nan,np.nan]), 'Logarithmic slope of the differential photon spectrum evaluated at 10 GeV.',
                  np.ndarray, '`~numpy.ndarray`')),    
    ('e2dfde', (np.array([np.nan,np.nan]), 'E^2 times the differential photon flux and uncertainty (%s) evaluated at the pivot energy.'%ENERGY_FLUX_UNIT,
             np.ndarray, '`~numpy.ndarray`')),
    ('e2dfde100', (np.array([np.nan,np.nan]), 'E^2 times the differential photon flux and uncertainty (%s) evaluated at 100 MeV.'%ENERGY_FLUX_UNIT,
                np.ndarray, '`~numpy.ndarray`')),
    ('e2dfde1000', (np.array([np.nan,np.nan]), 'E^2 times the differential photon flux and uncertainty (%s) evaluated at 1 GeV.'%ENERGY_FLUX_UNIT,
                 np.ndarray, '`~numpy.ndarray`')),
    ('e2dfde10000', (np.array([np.nan,np.nan]), 'E^2 times the differential photon flux and uncertainty (%s) evaluated at 10 GeV.'%ENERGY_FLUX_UNIT,
                  np.ndarray, '`~numpy.ndarray`')),  
))

# Top-level dictionary for output file
file_output = OrderedDict((
    ('roi', (None, 'A dictionary containing information about the ROI as a whole.',dict,'dict')),
    ('sources', (None, 'A dictionary containing information for individual sources in the model (diffuse and point-like).  Each element of this dictionary maps to a single source in the ROI model.',dict,'dict')),
    ('config', (None, 'The configuration dictionary of the :py:class:`~fermipy.gtanalysis.GTAnalysis` instance.',dict,'dict')),
    ('version', (None, 'The version of the fermiPy package that was used to run the analysis.  This is automatically generated from the git release tag.',str,'str'))
))
