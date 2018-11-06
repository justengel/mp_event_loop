"""
setup.py - Setup file to distribute the library

See Also:
    https://github.com/pypa/sampleproject
    https://packaging.python.org/en/latest/distributing.html
    https://pythonhosted.org/an_example_pypi_project/setuptools.html
"""
import os
import glob
from setuptools import setup


def read(fname):
    """Read in a file"""
    with open(os.path.join(os.path.dirname(__file__), fname), 'r') as file:
        return file.read()


# ========== Requirements ==========
def check_options(line, options):
    if line.startswith('--'):
        opt, value = line.split(' ', 1)
        opt = opt.strip()
        value = value.strip()
        try:
            options[opt].append(value)
        except KeyError:
            options[opt] = [value]
        return True


def parse_requirements(filename, options=None):
    """load requirements from a pip requirements file """
    if options is None:
        options = {}
    lineiter = (line.strip() for line in open(filename))
    return [line for line in lineiter if line and not line.startswith('#') and not check_options(line, options)]


requirements = parse_requirements('requirements.txt')
# ========== END Requirements ==========


if __name__ == "__main__":
    # Variables
    name = 'mp_event_loop'
    version = '1.5.2'
    description = 'Library for long running multiprocessing event loops.'
    url = 'https://github.com/justengel/mp_event_loop'
    author = 'Justin Engel'
    author_email = 'jtengel08@gmail.com'
    keywords = 'multiprocessing event loop event loop process async await'
    packages = ["mp_event_loop"]

    # Extensions
    extensions = []
    # module1 = Extension('libname',
    #                     # define_macros=[('MAJOR_VERSION', '1')],
    #                     # extra_compile_args=['-std=c99'],
    #                     sources=['file.c', 'dir/file.c'],
    #                     include_dirs=['./dir'])
    # extensions.append(module1)

    setup(name=name,
          version=version,
          description=description,
          long_description=read('README.md'),
          keywords=keywords,
          url=url,
          download_url=''.join((url, '/archive/v', version, '.tar.gz')),

          author=author,
          author_email=author_email,

          license='Proprietary',
          platforms='any',
          classifiers=['Programming Language :: Python',
                       'Programming Language :: Python :: 3',
                       'Operating System :: OS Independent'],

          scripts=[file for file in glob.iglob('bin/*.py')],  # Run with python -m Scripts.module args

          ext_modules=extensions,  # C extensions
          packages=packages,
          include_package_data=True,
          # package_data={
          #     'package': ['slat_app/slat_resources/resources/*']
          # },

          # Data files outside of packages
          # data_files=[('my_data', ['data/my_data.dat'])],

          # options to install extra requirements
          install_requires=[
              ],
          extras_require={
              'all': ['psutil'],
              },

          # entry_points={
          #     'console_scripts': [
          #         'plot_csv=bin.plot_csv:plot_csv',  # make bash scripts from python modules
          #         ],
          #     'gui_scripts': [
          #         'baz = my_package_gui:start_func',
          #         ]
          #     }
          )
