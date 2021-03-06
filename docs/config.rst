.. _config:

Configuration
=============

This page describes the configuration management scheme used within
the fermiPy package and the documents the configuration parameters
that can be set in the configuration file.


##################################
Class Configuration
##################################

Classes in the fermiPy package follow a common convention for
configuring the runtime behavior of a class instance.  Internally
every class instance has a dictionary that defines its configuration
state.  Elements of the configuration dictionary can be scalars (str,
int ,float) or dictionaries defining nested blocks of the
configuration.

The class configuration dictionary is initialized at the time of
object creation by passing a dictionary or a path to YAML
configuration file to the class constructor.  Keyword arguments can be
optionally passed to the constructor to override configuration
parameters in the input dictionary.  For instance in the following
example the *config* dictionary defines values for the parameters
*emin* and *emax*.  By passing a dictionary for the *selection*
keyword argument, the value of emax in the keyword argument (10000)
overrides the value of this parameter in the input dictionary.

.. code-block:: python
   
   config = { 
   'selection' : { 'emin' : 100, 
                   'emax' : 1000 }   
   }

   gta = GTAnalysis(config,selection={'emax' : 10000})
   
The first argument can also be the path to a YAML configuration file
rather than a dictionary:

.. code-block:: python
   
   gta = GTAnalysis('config.yaml',selection={'emax' : 10000})


##################################
Configuration File
##################################

fermiPy uses YAML files to read and write its configuration in a
persistent format.  The configuration file has a hierarchical
organization that groups parameters into dictionaries that are keyed
to a section name (*data*, *binnig*, etc.).  

.. code-block:: yaml
   :caption: Sample Configuration

   data:
     evfile : ft1.lst
     scfile : ft2.fits
     ltfile : ltcube.fits
     
   binning:
     roiwidth   : 10.0    
     binsz      : 0.1 
     binsperdec : 8   

   selection :
     emin : 100
     emax : 316227.76
     zmax    : 90
     evclass : 128
     evtype  : 3
     tmin    : 239557414
     tmax    : 428903014
     filter  : null
     target : 'mkn421'
     
   gtlike:
     edisp : True
     irfs : 'P8R2_SOURCE_V6'
     edisp_disable : ['isodiff','galdiff']

   model:
     src_roiwidth : 15.0
     galdiff  : '$FERMI_DIFFUSE_DIR/gll_iem_v06.fits'
     isodiff  : 'iso_P8R2_SOURCE_V6_v06.txt'
     catalogs : ['3FGL']
                          
The configuration file mirrors the layout of the configuration
dictionary.  Most of the available configuration parameters are
optional and if not set explicitly in the configuration file will be
set to a default value.  The parameters that can be set in each
section are described below.
     
binning
-------

Options in the *binning* section control the spatial and spectral binning of the data.

.. code-block:: yaml
   :caption: Sample *binning* Configuration
                
   binning:

     # Binning
     roiwidth   : 10.0
     npix       : null
     binsz      : 0.1 # spatial bin size in deg
     binsperdec : 8   # nb energy bins per decade
     projtype   : WCS

.. csv-table:: *binning* Options
   :header:    Option, Default, Description
   :file: config/binning.csv
   :delim: tab
   :widths: 10,10,80

.. _config_components:

components
----------

The *components* section can be used to define analysis configurations
for a sequence of independent subselections of the data.  Each
subselection will have its own binned likelihood instance that will be
combined in a global likelihood likelihood function for the whole ROI
(implemented with the SummedLikelihood class in pyLikelihood).  This
section is optional and when this section is empty (the default)
fermiPy will construct a single likelihood with the parameters of the
root analysis configuration.

The component section can be defined as either a list or dictionary of
dictionary elements where each element sets analysis parameters for a
different subcomponent of the analysis.  Dictionary elements have the
same hierarchy of parameters as the root analysis configuration.
Parameters not defined in a given element will default to the values
set in the root analysis configuration.

The following example illustrates how to define a Front/Back analysis
with the a list of dictionaries.  In this case files associated to
each component will be named according to their order in the list
(e.g. file_00.fits, file_01.fits, etc.).

.. code-block:: yaml

   # Component section for Front/Back analysis with list style
   components:
     - { selection : { evtype : 1 } } # Front
     - { selection : { evtype : 2 } } # Back

This example illustrates how to define the components as a dictionary
of dictionaries.  In this case the files of a component will be
appended with its corresponding key (e.g. file_front.fits,
file_back.fits).

.. code-block:: yaml

   # Component section for Front/Back analysis with dictionary style
   components:
     front : { selection : { evtype : 1 } } # Front
     back  : { selection : { evtype : 2 } } # Back

.. _config_data:
     
data
----

The *data* section defines the input data files for the analysis (FT1,
FT2, and livetime cube).  ``evfile`` and ``scfile`` can either be 
individual files or group of files.  The optional ``ltcube`` option can
be used to choose a pre-generated livetime cube.  If ``ltcube`` is
null a livetime cube will be generated at runtime with ``gtltcube``.  

.. code-block:: yaml
   :caption: Sample *data* Configuration

   data :
     evfile : ft1.lst
     scfile : ft2.fits 
     ltcube : null

.. csv-table:: *data* Options
   :header:    Option, Default, Description
   :file: config/data.csv
   :delim: tab
   :widths: 10,10,80

extension
---------

The options in *extension* control the default behavior of the
`~fermipy.gtanalysis.GTAnalysis.extension` method.  For more information
about using this method see the :ref:`extension` page.

.. csv-table:: *extension* Options
   :header:    Option, Default, Description
   :file: config/extension.csv
   :delim: tab
   :widths: 10,10,80
            
fileio
------

The *fileio* section collects options related to file bookkeeping.
The ``outdir`` option sets the root directory of the analysis instance
where all output files will be written.  If ``outdir`` is null then the
output directory will be automatically set to the directory in which
the configuration file is located.  Enabling the ``usescratch`` option
will stage all output data files to a temporary scratch directory
created under ``scratchdir``.

.. code-block:: yaml                
   :caption: Sample *fileio* Configuration
           
   fileio:
      outdir : null
      logfile : null
      usescratch : False
      scratchdir  : '/scratch'

.. csv-table:: *fileio* Options
   :header:    Option, Default, Description
   :file: config/fileio.csv
   :delim: tab
   :widths: 10,10,80


.. _config_gtlike:
            
gtlike
------

Options in the *gtlike* section control the setup of the likelihood
analysis include the IRF name (``irfs``).

.. csv-table:: *gtlike* Options
   :header:    Option, Default, Description
   :file: config/gtlike.csv
   :delim: tab
   :widths: 10,10,80


.. _config_model:

model
-----

The *model* section collects options that control the inclusion of
point-source and diffuse components in the model.  ``galdiff`` and
``isodiff`` set the templates for the Galactic IEM and isotropic
diffuse respectively.  ``catalogs`` defines a list of catalogs that
will be merged to form a master analysis catalog from which sources
will be drawn.  Valid entries in this list can be FITS files or XML
model files.  ``sources`` can be used to insert additional
point-source or extended components beyond those defined in the master
catalog.  ``src_radius`` and ``src_roiwidth`` set the maximum distance
from the ROI center at which sources in the master catalog will be
included in the ROI model.

.. code-block:: yaml
   :caption: Sample *model* Configuration
                
   model :
   
     # Diffuse components
     galdiff  : '$FERMI_DIR/refdata/fermi/galdiffuse/gll_iem_v06.fits'
     isodiff  : '$FERMI_DIR/refdata/fermi/galdiffuse/iso_P8R2_SOURCE_V6_v06.txt'

     # List of catalogs to be used in the model.
     catalogs : 
       - '3FGL'
       - 'extra_sources.xml'

     sources :
       - { 'name' : 'SourceA', 'ra' : 60.0, 'dec' : 30.0, 'SpectrumType' : PowerLaw }
       - { 'name' : 'SourceB', 'ra' : 58.0, 'dec' : 35.0, 'SpectrumType' : PowerLaw }

     # Include catalog sources within this distance from the ROI center
     src_radius  : null

     # Include catalog sources within a box of width roisrc.
     src_roiwidth : 15.0

.. csv-table:: *model* Options
   :header:    Option, Default, Description
   :file: config/model.csv
   :delim: tab
   :widths: 10,10,80
            
.. _config_optimizer:
            
optimizer
---------

.. csv-table:: *optimizer* Options
   :header:    Option, Default, Description
   :file: config/optimizer.csv
   :delim: tab
   :widths: 10,10,80

.. _config_plotting:
            
plotting
--------

.. csv-table:: *plotting* Options
   :header:    Option, Default, Description
   :file: config/plotting.csv
   :delim: tab
   :widths: 10,10,80

.. _config_residmap:
            
residmap
--------

The options in *residmap* control the default behavior of the
`~fermipy.gtanalysis.GTAnalysis.residmap` method.  For more
information about using this method see the :ref:`detection` page.

.. csv-table:: *residmap* Options
   :header:    Option, Default, Description
   :file: config/residmap.csv
   :delim: tab
   :widths: 10,10,80

.. _config_roiopt:

roiopt
------

The options in *roiopt* control the default behavior of the
`~fermipy.gtanalysis.GTAnalysis.optimize` method.  For more
information about using this method see the :ref:`fitting` page.

.. csv-table:: *roiopt* Options
   :header:    Option, Default, Description
   :file: config/roiopt.csv
   :delim: tab
   :widths: 10,10,80
            
.. _config_sed:
            
sed
---

The options in *sed* control the default behavior of the
`~fermipy.gtanalysis.GTAnalysis.sed` method.  For more information
about using this method see the :ref:`sed` page.

.. csv-table:: *sed* Options
   :header:    Option, Default, Description
   :file: config/sed.csv
   :delim: tab
   :widths: 10,10,80

.. _config_selection:

selection
---------

The *selection* section collects parameters related to the data
selection and target definition.  The majority of the parameters in
this section are arguments to *gtselect* and *gtmktime*.  The ROI
center can be set with the *target* parameter by providing the name of
a source defined in one of the input catalogs (defined in the *model*
section).  Alternatively the ROI center can be defined by giving
explicit sky coordinates with *ra* and *dec* or *glon* and *glat*.

.. code-block:: yaml

   selection:

     # gtselect parameters
     emin    : 100
     emax    : 100000
     zmax    : 90
     evclass : 128
     evtype  : 3
     tmin    : 239557414
     tmax    : 428903014 

     # gtmktime parameters
     filter : 'DATA_QUAL>0 && LAT_CONFIG==1'
     roicut : 'no'

     # Set the ROI center to the coordinates of this source
     target : 'mkn421'

.. csv-table:: *selection* Options
   :header:    Option, Default, Description
   :file: config/selection.csv
   :delim: tab
   :widths: 10,10,80
            
sourcefind
----------

The options in *sourcefind* control the default behavior of the
`~fermipy.gtanalysis.GTAnalysis.find_sources` method.  For more information
about using this method see the :ref:`detection` page.

.. csv-table:: *sourcefind* Options
   :header:    Option, Default, Description
   :file: config/sourcefind.csv
   :delim: tab
   :widths: 10,10,80
            
tsmap
-----

The options in *tsmap* control the default behavior of the
`~fermipy.gtanalysis.GTAnalysis.tsmap` method.  For more information
about using this method see the :ref:`detection` page.

.. csv-table:: *tsmap* Options
   :header:    Option, Default, Description
   :file: config/tsmap.csv
   :delim: tab
   :widths: 10,10,80
            
tscube
------

The options in *tscube* control the default behavior of the
`~fermipy.gtanalysis.GTAnalysis.tscube` method.  For more information
about using this method see the :ref:`detection` page.

.. csv-table:: *tscube* Options
   :header:    Option, Default, Description
   :file: config/tscube.csv
   :delim: tab
   :widths: 10,10,80
            

            

