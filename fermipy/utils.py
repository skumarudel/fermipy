# Licensed under a 3-clause BSD style license - see LICENSE.rst
from __future__ import absolute_import, division, print_function
import os
import re
import copy
from collections import OrderedDict
import xml.etree.cElementTree as et
import yaml
import numpy as np
import scipy.optimize
from scipy.interpolate import UnivariateSpline
from scipy.optimize import brentq
import scipy.special as special
from astropy.extern import six


def init_matplotlib_backend(backend=None):
    """This function initializes the matplotlib backend.  When no
    DISPLAY is available the backend is automatically set to 'Agg'.

    Parameters
    ----------
    backend : str
       matplotlib backend name.
    """

    import matplotlib
    
    try:
        os.environ['DISPLAY']
    except KeyError:
        matplotlib.use('Agg')
    else:
        if backend is not None:
            matplotlib.use(backend)


def unicode_representer(dumper, uni):
    node = yaml.ScalarNode(tag=u'tag:yaml.org,2002:str', value=uni)
    return node


yaml.add_representer(six.text_type, unicode_representer)


def load_yaml(infile, **kwargs):
    return yaml.load(open(infile), **kwargs)


def write_yaml(o, outfile, **kwargs):
    yaml.dump(tolist(o), open(outfile, 'w'), **kwargs)


def load_npy(infile):
    return np.load(infile).flat[0]


def load_data(infile, workdir=None):
    """Load python data structure from either a YAML or numpy file. """
    infile = resolve_path(infile, workdir=workdir)
    infile, ext = os.path.splitext(infile)

    if os.path.isfile(infile + '.npy'):
        infile += '.npy'
    elif os.path.isfile(infile + '.yaml'):
        infile += '.yaml'
    else:
        raise Exception('Input file does not exist.')

    ext = os.path.splitext(infile)[1]

    if ext == '.npy':
        return infile, load_npy(infile)
    elif ext == '.yaml':
        return infile, load_yaml(infile)
    else:
        raise Exception('Unrecognized extension.')


def resolve_path(path, workdir=None):
    if os.path.isabs(path):
        return path
    elif workdir is None:
        return os.path.abspath(path)
    else:
        return os.path.join(workdir, path)


def resolve_file_path(path, **kwargs):
    dirs = kwargs.get('search_dirs', [])

    if os.path.isabs(os.path.expandvars(path)) and \
            os.path.isfile(os.path.expandvars(path)):
        return path

    for d in dirs:
        if not os.path.isdir(os.path.expandvars(d)):
            continue
        p = os.path.join(d, path)
        if os.path.isfile(os.path.expandvars(p)):
            return p

    raise Exception('Failed to resolve file path: %s' % path)


def collect_dirs(path, max_depth=1, followlinks=True):
    """Recursively find directories under the given path."""

    if not os.path.isdir(path):
        return []

    o = [path]

    if max_depth == 0:
        return o

    for subdir in os.listdir(path):

        subdir = os.path.join(path, subdir)

        if not os.path.isdir(subdir):
            continue

        o += [subdir]

        if os.path.islink(subdir) and not followlinks:
            continue

        if max_depth > 0:
            o += collect_dirs(subdir, max_depth=max_depth - 1)

    return list(set(o))


def match_regex_list(patterns, string):
    """Perform a regex match of a string against a list of patterns.
    Returns true if the string matches at least one pattern in the
    list."""

    for p in patterns:

        if re.findall(p, string):
            return True

    return False


def join_strings(strings, sep='_'):
    if strings is None:
        return ''
    else:
        if not isinstance(strings, list):
            strings = [strings]
        return sep.join([s for s in strings if s])


def format_filename(outdir, basename, prefix=None, extension=None):
    filename = join_strings(prefix)
    filename = join_strings([filename, basename])

    if extension is not None:

        if extension.startswith('.'):
            filename += extension
        else:
            filename += '.' + extension

    return os.path.join(outdir, filename)


def strip_suffix(filename, suffix):
    for s in suffix:
        filename = re.sub(r'\.%s$' % s, '', filename)

    return filename


RA_NGP = np.radians(192.8594812065348)
DEC_NGP = np.radians(27.12825118085622)
L_CP = np.radians(122.9319185680026)


def gal2eq(l, b):
    L_0 = L_CP - np.pi / 2.
    RA_0 = RA_NGP + np.pi / 2.

    l = np.array(l, ndmin=1)
    b = np.array(b, ndmin=1)

    l, b = np.radians(l), np.radians(b)

    sind = np.sin(b) * np.sin(DEC_NGP) + np.cos(b) * np.cos(DEC_NGP) * np.sin(
        l - L_0)

    dec = np.arcsin(sind)

    cosa = np.cos(l - L_0) * np.cos(b) / np.cos(dec)
    sina = (np.cos(b) * np.sin(DEC_NGP) * np.sin(l - L_0) - np.sin(b) * np.cos(
        DEC_NGP)) / np.cos(dec)

    dec = np.degrees(dec)

    cosa[cosa < -1.0] = -1.0
    cosa[cosa > 1.0] = 1.0
    ra = np.arccos(cosa)
    ra[np.where(sina < 0.)] = -ra[np.where(sina < 0.)]

    ra = np.degrees(ra + RA_0)

    ra = np.mod(ra, 360.)
    dec = np.mod(dec + 90., 180.) - 90.

    return ra, dec


def eq2gal(ra, dec):
    L_0 = L_CP - np.pi / 2.
    RA_0 = RA_NGP + np.pi / 2.
    DEC_0 = np.pi / 2. - DEC_NGP

    ra = np.array(ra, ndmin=1)
    dec = np.array(dec, ndmin=1)

    ra, dec = np.radians(ra), np.radians(dec)

    np.sinb = np.sin(dec) * np.cos(DEC_0) - np.cos(dec) * np.sin(
        ra - RA_0) * np.sin(DEC_0)

    b = np.arcsin(np.sinb)

    cosl = np.cos(dec) * np.cos(ra - RA_0) / np.cos(b)
    sinl = (np.sin(dec) * np.sin(DEC_0) + np.cos(dec) * np.sin(
        ra - RA_0) * np.cos(DEC_0)) / np.cos(b)

    b = np.degrees(b)

    cosl[cosl < -1.0] = -1.0
    cosl[cosl > 1.0] = 1.0
    l = np.arccos(cosl)
    l[np.where(sinl < 0.)] = - l[np.where(sinl < 0.)]

    l = np.degrees(l + L_0)

    l = np.mod(l, 360.)
    b = np.mod(b + 90., 180.) - 90.

    return l, b


def xyz_to_lonlat(*args):
    if len(args) == 1:
        x, y, z = args[0][0], args[0][1], args[0][2]
    else:
        x, y, z = args[0], args[1], args[2]

    lat = np.pi / 2. - np.arctan2(np.sqrt(x ** 2 + y ** 2), z)
    lon = np.arctan2(y, x)
    return lon, lat


def lonlat_to_xyz(lon, lat):
    phi = lon
    theta = np.pi / 2. - lat
    return np.array([np.sin(theta) * np.cos(phi),
                     np.sin(theta) * np.sin(phi),
                     np.cos(theta)])


def project(lon0, lat0, lon1, lat1):
    """This function performs a stereographic projection on the unit
    vector (lon1,lat1) with the pole defined at the reference unit
    vector (lon0,lat0)."""

    costh = np.cos(np.pi / 2. - lat0)
    cosphi = np.cos(lon0)

    sinth = np.sin(np.pi / 2. - lat0)
    sinphi = np.sin(lon0)

    xyz = lonlat_to_xyz(lon1, lat1)
    x1 = xyz[0]
    y1 = xyz[1]
    z1 = xyz[2]

    x1p = x1 * costh * cosphi + y1 * costh * sinphi - z1 * sinth
    y1p = -x1 * sinphi + y1 * cosphi
    z1p = x1 * sinth * cosphi + y1 * sinth * sinphi + z1 * costh

    r = np.arctan2(np.sqrt(x1p ** 2 + y1p ** 2), z1p)
    phi = np.arctan2(y1p, x1p)

    return r * np.cos(phi), r * np.sin(phi)


def scale_parameter(p):
    if isstr(p):
        p = float(p)

    if p > 0:
        scale = 10 ** -np.round(np.log10(1. / p))
        return p / scale, scale
    else:
        return p, 1.0


def update_bounds(val, bounds):
    return min(val, bounds[0]), max(val, bounds[1])


def apply_minmax_selection(val, val_minmax):
    if val_minmax is None:
        return True

    if val_minmax[0] is None:
        min_cut = True
    elif np.isfinite(val) and val >= val_minmax[0]:
        min_cut = True
    else:
        min_cut = False

    if val_minmax[1] is None:
        max_cut = True
    elif np.isfinite(val) and val <= val_minmax[1]:
        max_cut = True
    else:
        max_cut = False

    return (min_cut and max_cut)


def create_source_name(skydir):
    hms = skydir.icrs.ra.hms
    dms = skydir.icrs.dec.dms
    return 'PS J%02.f%04.1f%+03.f%02.f' % (hms.h,
                                           hms.m + hms.s / 60.,
                                           dms.d,
                                           np.abs(dms.m + dms.s / 60.))


def create_model_name(src):
    """Generate a name for a source object given its spatial/spectral
    properties.

    Parameters
    ----------
    src : `~fermipy.roi_model.Source`
          A source object.

    Returns
    -------
    name : str
           A source name.
    """
    o = ''
    spatial_type = src['SpatialModel'].lower()
    o += spatial_type

    if spatial_type == 'gaussian':
        o += '_s%04.2f' % src['SpatialWidth']

    if src['SpectrumType'] == 'PowerLaw':
        o += '_powerlaw_%04.2f' % float(src.spectral_pars['Index']['value'])
    else:
        o += '_%s' % (src['SpectrumType'].lower())

    return o


def cov_to_correlation(cov):
    err = np.sqrt(np.diag(cov))
    corr = np.array(cov)
    corr *= np.outer(1 / err, 1 / err)
    return corr


def twosided_cl_to_dlnl(cl):
    """Compute the delta-loglikehood value that corresponds to a
    two-sided interval of the given confidence level.

    Parameters
    ----------
    cl : float
        Confidence level.
    
    Returns
    -------
    dlnl : float    
        Delta-loglikelihood value with respect to the maximum of the
        likelihood function.
    """
    return 0.5 * np.power( np.sqrt(2.) * special.erfinv(cl), 2)


def twosided_dlnl_to_cl(dlnl):
    """Compute the confidence level that corresponds to a two-sided
    interval with a given change in the loglikelihood value.

    Parameters
    ----------
    dlnl : float
        Delta-loglikelihood value with respect to the maximum of the
        likelihood function.
    
    Returns
    -------
    cl : float
        Confidence level.
    """
    return special.erf( dlnl**0.5 )


def onesided_cl_to_dlnl(cl):
    """Compute the delta-loglikehood values that corresponds to an
    upper limit of the given confidence level.

    Parameters
    ----------
    cl : float
        Confidence level.
    
    Returns
    -------
    dlnl : float
        Delta-loglikelihood value with respect to the maximum of the
        likelihood function.
    """
    alpha = 1.0 - cl
    return 0.5 * np.power(np.sqrt(2.) * special.erfinv(1 - 2 * alpha), 2.)


def onesided_dlnl_to_cl(dlnl):
    """Compute the confidence level that corresponds to an upper limit
    with a given change in the loglikelihood value.

    Parameters
    ----------
    dlnl : float
        Delta-loglikelihood value with respect to the maximum of the
        likelihood function.
    
    Returns
    -------
    cl : float
        Confidence level.
    """
    alpha = (1.0 - special.erf(dlnl**0.5))/2.0
    return 1.0-alpha


def interpolate_function_min(x, y):
    sp = scipy.interpolate.splrep(x, y, k=2, s=0)

    def fn(t):
        return scipy.interpolate.splev(t, sp, der=1)

    if np.sign(fn(x[0])) == np.sign(fn(x[-1])):

        if np.sign(fn(x[0])) == -1:
            return x[-1]
        else:
            return x[0]

    x0 = scipy.optimize.brentq(fn,
                               x[0], x[-1],
                               xtol=1e-10 * np.median(x))

    return x0


def find_function_root(fn, x0, xb, delta=0.0):
    """Find the root of a function: f(x)+delta in the interval encompassed
    by x0 and xb.

    Parameters
    ----------

    fn : function
       Python function.

    x0 : float
       Fixed bound for the root search.  This will either be used as
       the lower or upper bound depending on the relative value of xb.

    xb : float
       Upper or lower bound for the root search.  If a root is not
       found in the interval [x0,xb]/[xb,x0] this value will be
       increased/decreased until a change in sign is found.

    """

    if x0 == xb:
        return np.nan

    for i in range(10):
        if np.sign(fn(xb) + delta) != np.sign(fn(x0) + delta):
            break

        if xb < x0:
            xb *= 0.5
        else:
            xb *= 2.0

    # Failed to find a root
    if np.sign(fn(xb) + delta) == np.sign(fn(x0) + delta):
        return np.nan

    if x0 == 0:
        xtol = 1e-10 * xb
    else:
        xtol = 1e-10 * (xb + x0)

    return brentq(lambda t: fn(t) + delta, x0, xb, xtol=xtol)


def get_parameter_limits(xval, loglike, ul_confidence=0.95, tol=1E-3):
    """Compute upper/lower limits, peak position, and 1-sigma errors
    from a 1-D likelihood function.  This function uses the
    delta-loglikelihood method to evaluate parameter limits by
    searching for the point at which the change in the log-likelihood
    value with respect to the maximum equals a specific value.  A
    parabolic spline fit to the log-likelihood values is used to
    improve the accuracy of the calculation.

    Parameters
    ----------

    xval : `~numpy.ndarray`
       Array of parameter values.

    loglike : `~numpy.ndarray`
       Array of log-likelihood values.

    ul_confidence : float
       Confidence level to use for limit calculation.

    tol : float
       Tolerance parameter for spline.

    """

    deltalnl = onesided_cl_to_dlnl(ul_confidence)

    spline = UnivariateSpline(xval, loglike, k=2, s=tol)
    # m = np.abs(loglike[1:] - loglike[:-1]) > delta_tol
    # xval = np.concatenate((xval[:1],xval[1:][m]))
    # loglike = np.concatenate((loglike[:1],loglike[1:][m]))
    # spline = InterpolatedUnivariateSpline(xval, loglike, k=2)

    sd = spline.derivative()

    imax = np.argmax(loglike)
    ilo = max(imax - 2, 0)
    ihi = min(imax + 2, len(xval) - 1)

    # Find the peak
    x0 = xval[imax]

    # Refine the peak position
    if np.sign(sd(xval[ilo])) != np.sign(sd(xval[ihi])):
        x0 = find_function_root(sd, xval[ilo], xval[ihi])

    lnlmax = float(spline(x0))

    fn = lambda t: spline(t) - lnlmax
    ul = find_function_root(fn, x0, xval[-1], deltalnl)
    ll = find_function_root(fn, x0, xval[0], deltalnl)
    err_lo = np.abs(x0 - find_function_root(fn, x0, xval[0], 0.5))
    err_hi = np.abs(x0 - find_function_root(fn, x0, xval[-1], 0.5))

    if np.isfinite(err_lo):
        err = 0.5 * (err_lo + err_hi)
    else:
        err = err_hi

    o = {'x0': x0, 'ul': ul, 'll': ll,
         'err_lo': err_lo, 'err_hi': err_hi, 'err': err,
         'lnlmax': lnlmax}
    return o


def poly_to_parabola(coeff):
    sigma = np.sqrt(1. / np.abs(2.0 * coeff[0]))
    x0 = -coeff[1] / (2 * coeff[0])
    y0 = (1. - (coeff[1] ** 2 - 4 * coeff[0] * coeff[2])) / (4 * coeff[0])

    return x0, sigma, y0


def parabola(xy, amplitude, x0, y0, sx, sy, theta):
    """Evaluate a 2D parabola given by:
    
    f(x,y) = f_0 - (1/2) * \delta^T * R * \Sigma * R^T * \delta

    where

    \delta = [(x - x_0), (y - y_0)]

    and R is the matrix for a 2D rotation by angle \theta and \Sigma
    is the covariance matrix:

    \Sigma = [[1/\sigma_x^2, 0           ],
              [0           , 1/\sigma_y^2]] 

    Parameters
    ----------
    xy : tuple    
       Tuple containing x and y arrays for the values at which the
       parabola will be evaluated.

    amplitude : float
       Constant offset value.
    
    x0 : float
       Centroid in x coordinate.

    y0 : float
       Centroid in y coordinate.
       
    sx : float
       Standard deviation along first axis (x-axis when theta=0).

    sy : float
       Standard deviation along second axis (y-axis when theta=0).

    theta : float
       Rotation angle in radians.

    Returns
    -------
    vals : `~numpy.ndarray`    
       Values of the parabola evaluated at the points defined in the
       `xy` input tuple.
    
    """

    x = xy[0]
    y = xy[1]

    cth = np.cos(theta)
    sth = np.sin(theta)
    a = (cth ** 2) / (2 * sx ** 2) + (sth ** 2) / (2 * sy ** 2)
    b = -(np.sin(2 * theta)) / (4 * sx ** 2) + (np.sin(2 * theta)) / (
        4 * sy ** 2)
    c = (sth ** 2) / (2 * sx ** 2) + (cth ** 2) / (2 * sy ** 2)
    vals = amplitude - (a * ((x - x0) ** 2) +
                        2 * b * (x - x0) * (y - y0) +
                        c * ((y - y0) ** 2))

    return vals


def fit_parabola(z, ix, iy, dpix=2, zmin=None):
    """Fit a parabola to a 2D numpy array.  This function will fit a
    parabola with the functional form described in
    `~fermipy.utils.parabola` to a 2D slice of the input array `z`.
    The boundaries of the fit region within z are set with the pixel
    centroid (`ix` and `iy`) and region size (`dpix`).

    Parameters
    ----------
    z : `~numpy.ndarray`
    
    ix : int
       X index of center pixel of fit region in array `z`.
    
    iy : int
       Y index of center pixel of fit region in array `z`.

    dpix : int
       Size of fit region expressed as a pixel offset with respect the
       centroid.  The size of the sub-array will be (dpix*2 + 1) x
       (dpix*2 + 1).
    """

    xmin = max(0, ix - dpix)
    xmax = min(z.shape[0], ix + dpix + 1)

    ymin = max(0, iy - dpix)
    ymax = min(z.shape[1], iy + dpix + 1)

    sx = slice(xmin, xmax)
    sy = slice(ymin, ymax)

    nx = sx.stop - sx.start
    ny = sy.stop - sy.start

    x = np.arange(sx.start, sx.stop)
    y = np.arange(sy.start, sy.stop)

    x = x[:, np.newaxis] * np.ones((nx, ny))
    y = y[np.newaxis, :] * np.ones((nx, ny))

    coeffx = poly_to_parabola(np.polyfit(
        np.arange(sx.start, sx.stop), z[sx, iy], 2))
    coeffy = poly_to_parabola(np.polyfit(
        np.arange(sy.start, sy.stop), z[ix, sy], 2))
    p0 = [coeffx[2], coeffx[0], coeffy[0], coeffx[1], coeffy[1], 0.0]
    m = np.isfinite(z[sx, sy])
    if zmin is not None:
        m = z[sx, sy] > zmin

    o = {'fit_success': True, 'p0': p0}

    def curve_fit_fn(*args):
        return np.ravel(parabola(*args))

    try:
        popt, pcov = scipy.optimize.curve_fit(curve_fit_fn,
                                              (np.ravel(x[m]), np.ravel(y[m])),
                                              np.ravel(z[sx, sy][m]), p0)
    except Exception:
        popt = copy.deepcopy(p0)
        o['fit_success'] = False

    fm = parabola((x[m], y[m]), *popt)
    df = fm - z[sx, sy][m]
    rchi2 = np.sum(df ** 2) / len(fm)

    o['rchi2'] = rchi2
    o['x0'] = popt[1]
    o['y0'] = popt[2]
    o['sigmax'] = popt[3]
    o['sigmay'] = popt[4]
    o['sigma'] = np.sqrt(o['sigmax'] ** 2 + o['sigmay'] ** 2)
    o['z0'] = popt[0]
    o['theta'] = popt[5]
    o['popt'] = popt

    a = max(o['sigmax'], o['sigmay'])
    b = min(o['sigmax'], o['sigmay'])

    o['eccentricity'] = np.sqrt(1 - b ** 2 / a ** 2)
    o['eccentricity2'] = np.sqrt(a ** 2 / b ** 2 - 1)

    return o


def center_to_edge(center):

    if len(center) == 1: 
        delta = np.array(1.0,ndmin=1)
    else: 
        delta = center[1:]-center[:-1]
    
    edges = 0.5*(center[1:]+center[:-1])
    edges = np.insert(edges,0,center[0]-0.5*delta[0])
    edges = np.append(edges,center[-1]+0.5*delta[-1])
    return edges


def edge_to_center(edges):
    return 0.5 * (edges[1:] + edges[:-1])


def edge_to_width(edges):
    return (edges[1:] - edges[:-1])


def val_to_bin(edges, x):
    """Convert axis coordinate to bin index."""
    ibin = np.digitize(np.array(x, ndmin=1), edges) - 1
    return ibin


def val_to_pix(center, x):
    return np.interp(x, center, np.arange(len(center)).astype(float))


def val_to_edge(edges, x):
    """Convert axis coordinate to bin index."""
    edges = np.array(edges)
    w = edges[1:] - edges[:-1]
    w = np.insert(w, 0, w[0])
    ibin = np.digitize(np.array(x, ndmin=1), edges - 0.5 * w) - 1
    ibin[ibin < 0] = 0
    return ibin


def val_to_bin_bounded(edges, x):
    """Convert axis coordinate to bin index."""
    nbins = len(edges) - 1
    ibin = val_to_bin(edges, x)
    ibin[ibin < 0] = 0
    ibin[ibin > nbins - 1] = nbins - 1
    return ibin


def extend_array(edges, binsz, lo, hi):
    """Extend an array to encompass lo and hi values."""

    numlo = int(np.ceil((edges[0] - lo) / binsz))
    numhi = int(np.ceil((hi - edges[-1]) / binsz))

    edges = copy.deepcopy(edges)
    if numlo > 0:
        edges_lo = np.linspace(edges[0] - numlo * binsz, edges[0], numlo + 1)
        edges = np.concatenate((edges_lo[:-1], edges))

    if numhi > 0:
        edges_hi = np.linspace(edges[-1], edges[-1] + numhi * binsz, numhi + 1)
        edges = np.concatenate((edges, edges_hi[1:]))

    return edges


def mkdir(dir):
    if not os.path.exists(dir):
        os.makedirs(dir)
    return dir


def fits_recarray_to_dict(table):
    """Convert a FITS recarray to a python dictionary."""

    cols = {}
    for icol, col in enumerate(table.columns.names):

        col_data = table.data[col]
        if type(col_data[0]) == np.float32:
            cols[col] = np.array(col_data, dtype=float)
        elif type(col_data[0]) == np.float64:
            cols[col] = np.array(col_data, dtype=float)
        elif type(col_data[0]) == str:
            cols[col] = np.array(col_data, dtype=str)
        elif type(col_data[0]) == np.string_:
            cols[col] = np.array(col_data, dtype=str)
        elif type(col_data[0]) == np.int16:
            cols[col] = np.array(col_data, dtype=int)
        elif type(col_data[0]) == np.ndarray:
            cols[col] = np.array(col_data)
        else:
            raise Exception(
                'Unrecognized column type: %s %s' % (col, str(type(col_data))))

    return cols


def unicode_to_str(args):
    o = {}
    for k, v in args.items():
        if isinstance(v, unicode):
            o[k] = str(v)
        else:
            o[k] = v

    return o


def isstr(s):
    """String instance testing method that works under both Python 2.X
    and 3.X.  Returns true if the input is a string."""

    try:
        return isinstance(s, basestring)
    except NameError:
        return isinstance(s, str)


def xmlpath_to_path(path):
    if path is None:
        return path

    return re.sub(r'\$\(([a-zA-Z\_]+)\)', r'$\1', path)


def path_to_xmlpath(path):
    if path is None:
        return path

    return re.sub(r'\$([a-zA-Z\_]+)', r'$(\1)', path)


def create_xml_element(root, name, attrib):
    el = et.SubElement(root, name)
    for k, v in attrib.iteritems():

        if isinstance(v, bool):
            el.set(k, str(int(v)))
        elif isstr(v):
            el.set(k, v)
        elif np.isfinite(v):
            el.set(k, str(v))

    return el


def load_xml_elements(root, path):
    o = {}
    for p in root.findall(path):

        if 'name' in p.attrib:
            o[p.attrib['name']] = copy.deepcopy(p.attrib)
        else:
            o.update(p.attrib)
    return o


def prettify_xml(elem):
    """Return a pretty-printed XML string for the Element.
    """
    from xml.dom import minidom
    import xml.etree.cElementTree as et

    rough_string = et.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")


def arg_to_list(arg):
    if arg is None:
        return []
    elif isinstance(arg, list):
        return arg
    else:
        return [arg]


def update_keys(input_dict, key_map):
    o = {}
    for k, v in input_dict.items():

        if k in key_map.keys():
            k = key_map[k]

        if isinstance(v, dict):
            o[k] = update_keys(v, key_map)
        else:
            o[k] = v

    return o


def create_dict(d0, **kwargs):
    o = copy.deepcopy(d0)
    o = merge_dict(o,kwargs,add_new_keys=True)
    return o


def merge_dict(d0, d1, add_new_keys=False, append_arrays=False):
    """Recursively merge the contents of python dictionary d0 with
    the contents of another python dictionary, d1.

    Parameters
    ----------
    d0 : dict
       The input dictionary.

    d1 : dict
       Dictionary to be merged with the input dictionary.

    add_new_keys : str
       Do not skip keys that only exist in d1.

    append_arrays : bool
       If an element is a numpy array set the value of that element by
       concatenating the two arrays.
    """

    if d1 is None:
        return d0
    elif d0 is None:
        return d1
    elif d0 is None and d1 is None:
        return {}

    od = {}

    for k, v in d0.items():

        t0 = None
        t1 = None

        if k in d0:
            t0 = type(d0[k])
        if k in d1:
            t1 = type(d1[k])

        if k not in d1:
            od[k] = copy.deepcopy(d0[k])
        elif isinstance(v, dict) and isinstance(d1[k], dict):
            od[k] = merge_dict(d0[k], d1[k], add_new_keys, append_arrays)
        elif isinstance(v, list) and isstr(d1[k]):
            od[k] = d1[k].split(',')
        elif isinstance(v, dict) and d1[k] is None:
            od[k] = copy.deepcopy(d0[k])
        elif isinstance(v, np.ndarray) and append_arrays:
            od[k] = np.concatenate((v, d1[k]))
        elif (d0[k] is not None and d1[k] is not None) and t0 != t1:

            if t0 == dict or t0 == list:
                raise Exception('Conflicting types in dictionary merge for '
                                'key %s %s %s' % (k, t0, t1))
            od[k] = t0(d1[k])
        else:
            od[k] = copy.copy(d1[k])

    if add_new_keys:
        for k, v in d1.items():
            if k not in d0:
                od[k] = copy.deepcopy(d1[k])

    return od


def tolist(x):
    """ convenience function that takes in a
        nested structure of lists and dictionaries
        and converts everything to its base objects.
        This is useful for dupming a file to yaml.

        (a) numpy arrays into python lists

            >>> type(tolist(np.asarray(123))) == int
            True
            >>> tolist(np.asarray([1,2,3])) == [1,2,3]
            True

        (b) numpy strings into python strings.

            >>> tolist([np.asarray('cat')])==['cat']
            True

        (c) an ordered dict to a dict

            >>> ordered=OrderedDict(a=1, b=2)
            >>> type(tolist(ordered)) == dict
            True

        (d) converts unicode to regular strings

            >>> type(u'a') == str
            False
            >>> type(tolist(u'a')) == str
            True

        (e) converts numbers & bools in strings to real represntation,
            (i.e. '123' -> 123)

            >>> type(tolist(np.asarray('123'))) == int
            True
            >>> type(tolist('123')) == int
            True
            >>> tolist('False') == False
            True
    """
    if isinstance(x, list):
        return map(tolist, x)
    elif isinstance(x, dict):
        return dict((tolist(k), tolist(v)) for k, v in x.items())
    elif isinstance(x, np.ndarray) or isinstance(x, np.number):
        # note, call tolist again to convert strings of numbers to numbers
        return tolist(x.tolist())
    elif isinstance(x, OrderedDict):
        return dict(x)
    elif isinstance(x, np.bool_):
        return bool(x)
    elif isinstance(x, basestring) or isinstance(x, np.str):
        x = str(x)  # convert unicode & numpy strings
        try:
            return int(x)
        except:
            try:
                return float(x)
            except:
                if x == 'True':
                    return True
                elif x == 'False':
                    return False
                else:
                    return x
    else:
        return x


def create_hpx_disk_region_string(skyDir, coordsys, radius, inclusive=0):
    """
    """
    # Make an all-sky region
    if radius >= 90.:
        return None

    if coordsys == "GAL":
        xref = skyDir.galactic.l.deg
        yref = skyDir.galactic.b.deg
    elif coordsys == "CEL":
        xref = skyDir.ra.deg
        yref = skyDir.dec.deg
    else:
        raise Exception("Unrecognized coordinate system %s" % coordsys)

    if inclusive:
        val = "DISK_INC(%.3f,%.3f,%.3f,%i)" % (xref, yref, radius, inclusive)
    else:
        val = "DISK(%.3f,%.3f,%.3f)" % (xref, yref, radius)
    return val


def convolve2d_disk(fn, r, sig, nstep=200):
    """Evaluate the convolution f'(r) = f(r) * g(r) where f(r) is
    azimuthally symmetric function in two dimensions and g is a
    step function given by:

    g(r) = H(1-r/s)

    Parameters
    ----------

    fn : function
      Input function that takes a single radial coordinate parameter.

    r :  `~numpy.ndarray`
      Array of points at which the convolution is to be evaluated.

    sig : float
      Radius parameter of the step function.

    nstep : int
      Number of sampling point for numeric integration.
    """

    r = np.array(r, ndmin=1)
    sig = np.array(sig, ndmin=1)

    rmin = r - sig
    rmax = r + sig
    rmin[rmin < 0] = 0
    delta = (rmax - rmin) / nstep

    redge = rmin[:, np.newaxis] + \
            delta[:, np.newaxis] * np.linspace(0, nstep, nstep + 1)[np.newaxis, :]
    rp = 0.5 * (redge[:, 1:] + redge[:, :-1])
    dr = redge[:, 1:] - redge[:, :-1]
    fnv = fn(rp)

    r = r.reshape(r.shape + (1,))
    saxis = 1

    cphi = -np.ones(dr.shape)
    m = ((rp + r) / sig < 1) | (r == 0)

    rrp = r * rp
    sx = r ** 2 + rp ** 2 - sig ** 2
    cphi[~m] = sx[~m] / (2 * rrp[~m])
    dphi = 2 * np.arccos(cphi)
    v = rp * fnv * dphi * dr / (np.pi * sig * sig)
    s = np.sum(v, axis=saxis)

    return s


def convolve2d_gauss(fn, r, sig, nstep=200):
    """Evaluate the convolution f'(r) = f(r) * g(r) where f(r) is
    azimuthally symmetric function in two dimensions and g is a
    gaussian given by:

    g(r) = 1/(2*pi*s^2) Exp[-r^2/(2*s^2)]

    Parameters
    ----------

    fn : function
      Input function that takes a single radial coordinate parameter.

    r :  `~numpy.ndarray`
      Array of points at which the convolution is to be evaluated.

    sig : float
      Width parameter of the gaussian.

    nstep : int
      Number of sampling point for numeric integration.

    """
    r = np.array(r, ndmin=1)
    sig = np.array(sig, ndmin=1)

    rmin = r - 10 * sig
    rmax = r + 10 * sig
    rmin[rmin < 0] = 0
    delta = (rmax - rmin) / nstep

    redge = (rmin[:, np.newaxis] +
             delta[:, np.newaxis] *
             np.linspace(0, nstep, nstep + 1)[np.newaxis, :])

    rp = 0.5 * (redge[:, 1:] + redge[:, :-1])
    dr = redge[:, 1:] - redge[:, :-1]
    fnv = fn(rp)

    r = r.reshape(r.shape + (1,))
    saxis = 1

    sig2 = sig * sig
    x = r * rp / (sig2)

    if 'je_fn' not in convolve2d_gauss.__dict__:
        t = 10 ** np.linspace(-8, 8, 1000)
        t = np.insert(t, 0, [0])
        je = special.ive(0, t)
        convolve2d_gauss.je_fn = UnivariateSpline(t, je, k=2, s=0)

    je = convolve2d_gauss.je_fn(x.flat).reshape(x.shape)
    #    je2 = special.ive(0,x)
    v = (rp * fnv / (sig2) * je * np.exp(x - (r * r + rp * rp) /
                                         (2 * sig2)) * dr)
    s = np.sum(v, axis=saxis)

    return s


def make_pixel_offset(npix, xpix=0.0, ypix=0.0):
    """Make a 2D array with the distance of each pixel from a
    reference direction in pixel coordinates.  Pixel coordinates are
    defined such that (0,0) is located at the center of the coordinate
    grid."""

    dx = np.abs(np.linspace(0, npix - 1, npix) - (npix - 1) / 2. - xpix)
    dy = np.abs(np.linspace(0, npix - 1, npix) - (npix - 1) / 2. - ypix)
    dxy = np.zeros((npix, npix))
    dxy += np.sqrt(dx[np.newaxis, :] ** 2 + dy[:, np.newaxis] ** 2)

    return dxy


def make_gaussian_kernel(sigma, npix=501, cdelt=0.01, xpix=0.0, ypix=0.0):
    """Make kernel for a 2D gaussian.

    Parameters
    ----------

    sigma : float
      68% containment radius in degrees.
    """

    sigma /= 1.5095921854516636
    sigma /= cdelt

    fn = lambda t, s: 1. / (2 * np.pi * s ** 2) * np.exp(
        -t ** 2 / (s ** 2 * 2.0))
    dxy = make_pixel_offset(npix, xpix, ypix)
    k = fn(dxy, sigma)
    k /= (np.sum(k) * np.radians(cdelt) ** 2)

    return k


def make_disk_kernel(sigma, npix=501, cdelt=0.01, xpix=0.0, ypix=0.0):
    """Make kernel for a 2D disk.

    Parameters
    ----------

    sigma : float
      Disk radius in deg.
    """

    sigma /= cdelt
    fn = lambda t, s: 0.5 * (np.sign(s - t) + 1.0)

    dxy = make_pixel_offset(npix, xpix, ypix)
    k = fn(dxy, sigma)
    k /= (np.sum(k) * np.radians(cdelt) ** 2)

    return k


def make_cdisk_kernel(psf, sigma, npix, cdelt, xpix, ypix, psf_scale_fn=None,
                      normalize=False):
    """Make a kernel for a PSF-convolved 2D disk.

    Parameters
    ----------

    psf : `~fermipy.irfs.PSFModel`

    sigma : float
      68% containment radius in degrees.
    """

    dtheta = psf.dtheta
    egy = psf.energies

    x = make_pixel_offset(npix, xpix, ypix)
    x *= cdelt

    k = np.zeros((len(egy), npix, npix))
    for i in range(len(egy)):        
        fn = lambda t: psf.eval(i, t, scale_fn=psf_scale_fn)
        psfc = convolve2d_disk(fn, dtheta, sigma)
        k[i] = np.interp(np.ravel(x), dtheta, psfc).reshape(x.shape)

    if normalize:
        k /= (np.sum(k, axis=0)[np.newaxis, ...] * np.radians(cdelt) ** 2)

    return k


def make_cgauss_kernel(psf, sigma, npix, cdelt, xpix, ypix, psf_scale_fn=None,
                       normalize=False):
    """Make a kernel for a PSF-convolved 2D gaussian.

    Parameters
    ----------

    psf : `~fermipy.irfs.PSFModel`

    sigma : float
      68% containment radius in degrees.
    """

    sigma /= 1.5095921854516636

    dtheta = psf.dtheta
    egy = psf.energies

    x = make_pixel_offset(npix, xpix, ypix)
    x *= cdelt

    k = np.zeros((len(egy), npix, npix))
    for i in range(len(egy)):
        fn = lambda t: psf.eval(i, t, scale_fn=psf_scale_fn)
        psfc = convolve2d_gauss(fn, dtheta, sigma)
        k[i] = np.interp(np.ravel(x), dtheta, psfc).reshape(x.shape)

    if normalize:
        k /= (np.sum(k, axis=0)[np.newaxis, ...] * np.radians(cdelt) ** 2)

    return k


def make_psf_kernel(psf, npix, cdelt, xpix, ypix, psf_scale_fn=None, normalize=False):
    """
    Generate a kernel for a point-source.

    Parameters
    ----------

    psf : `~fermipy.irfs.PSFModel`

    npix : int
        Number of pixels in X and Y dimensions.

    cdelt : float
        Pixel size in degrees.

    """

    egy = psf.energies
    x = make_pixel_offset(npix, xpix, ypix)
    x *= cdelt

    k = np.zeros((len(egy), npix, npix))
    for i in range(len(egy)):
        k[i] = psf.eval(i, x, scale_fn=psf_scale_fn)

    if normalize:
        k /= (np.sum(k, axis=0)[np.newaxis, ...] * np.radians(cdelt) ** 2)

    return k


def rebin_map(k, nebin, npix, rebin):
    if rebin > 1:
        k = np.sum(k.reshape((nebin, npix * rebin, npix, rebin)), axis=3)
        k = k.swapaxes(1, 2)
        k = np.sum(k.reshape(nebin, npix, npix, rebin), axis=3)
        k = k.swapaxes(1, 2)

    k /= rebin ** 2

    return k
