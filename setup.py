#!/usr/bin/env python

import re
import os
import sys
import glob
pymajor,pyminor = sys.version_info[:2]
pkgdir = 'py%s.%s' % (pymajor,pyminor)
if sys.version_info < (2, 5):
    raise ValueError('Versions of Python before 2.5 are not supported')
elif sys.version_info >= (2, 6):
    pkgname = 'multiprocessing'
else: # (2, 5)
    pkgname = 'processing'  #XXX: oddity, due to lazyness at the moment
srcdir = '%s/Modules/_%s' % (pkgdir, pkgname)
libdir = '%s/%s' % (pkgdir, pkgname)

try:
    from setuptools import setup, Extension, find_packages
    has_setuptools = True
except ImportError:
    from distutils.core import setup, Extension, find_packages  # noqa
    has_setuptools = False
from distutils import sysconfig
from distutils.errors import CCompilerError, DistutilsExecError, \
                                             DistutilsPlatformError

HERE = os.path.dirname(os.path.abspath(__file__))

ext_errors = (CCompilerError, DistutilsExecError, DistutilsPlatformError)
if sys.platform == 'win32' and sys.version_info >= (2, 6):
    # distutils.msvc9compiler can raise IOError if the compiler is missing
    ext_errors += (IOError, )

is_jython = sys.platform.startswith('java')
is_pypy = hasattr(sys, 'pypy_version_info')
is_py3k = sys.version_info[0] == 3

BUILD_WARNING = """

-----------------------------------------------------------------------
WARNING: The C extensions could not be compiled
-----------------------------------------------------------------------

Maybe you do not have a C compiler installed on this system?
The reason was:
%s

This is just a warning as most of the functionality will work even
without the updated C extension.  It will simply fallback to the
built-in _multiprocessing module.  Most notably you will not be able to use
FORCE_EXECV on POSIX systems.  If this is a problem for you then please
install a C compiler or fix the error(s) above.
-----------------------------------------------------------------------

"""

# -*- extra config (setuptools) -*-
if has_setuptools:
    extras = dict(install_requires=['dill>=0.2.3'])
else:
    extras = dict()

# -*- Distribution Meta -*-
here = os.path.abspath(os.path.dirname(__file__))
meta_fh = open(os.path.join(here, '%s/__init__.py' % libdir))
try:
    meta = {}
    for line in meta_fh:
        if line.startswith('__version__'):
            version = line.split()[-1].strip("'").strip('"')
            break
    meta['version'] = version
finally:
    meta_fh.close()

#
# Macros and libraries
#
#   The `macros` dict determines the macros that will be defined when
#   the C extension is compiled.  Each value should be either 0 or 1.
#   (An undefined macro is assumed to have value 0.)  `macros` is only
#   used on Unix platforms.
#
#   The `libraries` dict determines the libraries to which the C
#   extension will be linked.  This should probably be either `['rt']`
#   if you need `librt` or else `[]`.
#
# Meaning of macros
#
#   HAVE_SEM_OPEN
#     Set this to 1 if you have `sem_open()`.  This enables the use of
#     posix named semaphores which are necessary for the
#     implementation of the synchronization primitives on Unix.  If
#     set to 0 then the only way to create synchronization primitives
#     will be via a manager (e.g. "m = Manager(); lock = m.Lock()").
#     
#   HAVE_SEM_TIMEDWAIT
#     Set this to 1 if you have `sem_timedwait()`.  Otherwise polling
#     will be necessary when waiting on a semaphore using a timeout.
#     
#   HAVE_FD_TRANSFER
#     Set this to 1 to compile functions for transferring file
#     descriptors between processes over an AF_UNIX socket using a
#     control message with type SCM_RIGHTS.  On Unix the pickling of 
#     of socket and connection objects depends on this feature.
#
#     If you get errors about missing CMSG_* macros then you should
#     set this to 0.
# 
#   HAVE_BROKEN_SEM_GETVALUE
#     Set to 1 if `sem_getvalue()` does not work or is unavailable.
#     On Mac OSX it seems to return -1 with message "[Errno 78]
#     Function not implemented".
#
#   HAVE_BROKEN_SEM_UNLINK
#     Set to 1 if `sem_unlink()` is unnecessary.  For some reason this
#     seems to be the case on Cygwin where `sem_unlink()` is missing
#     from semaphore.h.
#

if sys.platform == 'win32':  # Windows
    macros = dict()
    libraries = ['ws2_32']
elif sys.platform.startswith('darwin'):  # Mac OSX
    macros = dict(
        HAVE_SEM_OPEN=1,
        HAVE_SEM_TIMEDWAIT=0,
        HAVE_FD_TRANSFER=1,
        HAVE_BROKEN_SEM_GETVALUE=1
        )
    libraries = []
elif sys.platform.startswith('cygwin'):  # Cygwin
    macros = dict(
        HAVE_SEM_OPEN=1,
        HAVE_SEM_TIMEDWAIT=1,
        HAVE_FD_TRANSFER=0,
        HAVE_BROKEN_SEM_UNLINK=1
        )
    libraries = []
elif sys.platform in ('freebsd4', 'freebsd5', 'freebsd6'):
    # FreeBSD's P1003.1b semaphore support is very experimental
    # and has many known problems. (as of June 2008)
    macros = dict(                  # FreeBSD 4-6
        HAVE_SEM_OPEN=0,
        HAVE_SEM_TIMEDWAIT=0,
        HAVE_FD_TRANSFER=1,
        )
    libraries = []
elif re.match('^(gnukfreebsd(8|9|10|11)|freebsd(7|8|9|10))', sys.platform):
    macros = dict(                  # FreeBSD 7+ and GNU/kFreeBSD 8+
        HAVE_SEM_OPEN=bool(
            sysconfig.get_config_var('HAVE_SEM_OPEN') and not
            bool(sysconfig.get_config_var('POSIX_SEMAPHORES_NOT_ENABLED'))
        ),
        HAVE_SEM_TIMEDWAIT=1,
        HAVE_FD_TRANSFER=1,
    )
    libraries = []
elif sys.platform.startswith('openbsd'):
    macros = dict(                  # OpenBSD
        HAVE_SEM_OPEN=0,            # Not implemented
        HAVE_SEM_TIMEDWAIT=0,
        HAVE_FD_TRANSFER=1,
    )
    libraries = []
else:                                   # Linux and other unices
    macros = dict(
        HAVE_SEM_OPEN=1,
        HAVE_SEM_TIMEDWAIT=1,
        HAVE_FD_TRANSFER=1,
    )
    libraries = ['rt']

if sys.platform == 'win32':
    multiprocessing_srcs = [
        '%s/%s.c' % (srcdir, pkgname),
        '%s/semaphore.c' % srcdir,
    ]
    if sys.version_info < (3, 3):
        multiprocessing_srcs += [
            '%s/pipe_connection.c' % srcdir,
            '%s/socket_connection.c' % srcdir,
            '%s/win32_functions.c' % srcdir,
        ]
else:
    multiprocessing_srcs = [ '%s/%s.c' % (srcdir, pkgname) ]
    if sys.version_info < (3, 3):
        multiprocessing_srcs.append('%s/socket_connection.c' % srcdir)

    if macros.get('HAVE_SEM_OPEN', False):
        multiprocessing_srcs.append('%s/semaphore.c' % srcdir)

long_description = '''
`Multiprocessing` is a package for the Python language which supports the
spawning of processes using the API of the standard library's
`threading` module. `multiprocessing` has been distributed in the standard
library since python 2.6.

Features:

* Objects can be transferred between processes using pipes or
  multi-producer/multi-consumer queues.

* Objects can be shared between processes using a server process or
  (for simple data) shared memory.

* Equivalents of all the synchronization primitives in `threading`
  are available.

* A `Pool` class makes it easy to submit tasks to a pool of worker
  processes.

'''
#long_description = open(os.path.join(HERE, 'README.md')).read()
#long_description += """
#
#===========
#Changes
#===========
#
#"""
#long_description += open(os.path.join(HERE, 'CHANGES.txt')).read()
#if not is_py3k:
#    long_description = long_description.encode('ascii', 'replace')

# -*- Installation Requires -*-
py_version = sys.version_info
is_jython = sys.platform.startswith('java')
is_pypy = hasattr(sys, 'pypy_version_info')

#def strip_comments(l):
#    return l.split('#', 1)[0].strip()
#
#def reqs(f):
#    return list(filter(None, [strip_comments(l) for l in open(
#        os.path.join(os.getcwd(), 'requirements', f)).readlines()]))
#
#if py_version[0] == 3:
#    tests_require = reqs('test3.txt')
#else:
#    tests_require = reqs('test.txt')


def _is_build_command(argv=sys.argv, cmds=('install', 'build', 'bdist')):
    for arg in argv:
        if arg.startswith(cmds):
            return arg


def run_setup(with_extensions=True):
    extensions = []
    if with_extensions:
        extensions = [
            Extension(
                '_%s' % pkgname,
                sources=multiprocessing_srcs,
                define_macros=list(macros.items()),
                libraries=libraries,
                include_dirs=[srcdir],
                depends=glob.glob('%s/*.h' % srcdir) + ['setup.py'],
            ),
        ]
    packages = find_packages(
        where=pkgdir,
        exclude=['ez_setup', 'examples', 'doc', 'tests*', ],
        )
    config = dict(
        name='multiprocess',
        version=meta['version'],
        description=('Package for using processes which mimics ' +
                     'the threading module'),
        long_description=long_description,
        packages=packages,
        ext_modules=extensions,
        author='R Oudkerk',
        author_email='roudkerk at users.berlios.de',
        url='http://developer.berlios.de/projects/pyprocessing',
        maintainer='Mike McKerns',
        maintainer_email='mmckerns@caltech.edu',
        download_url='http://dev.danse.us/packages/',
        zip_safe=False,
        license='BSD',
        package_dir={'' : pkgdir}, #XXX: {pkgname+'.tests' : 'tests'} ?
#       tests_require=tests_require,
#       test_suite='nose.collector',
        classifiers=[
            'Development Status :: 5 - Production/Stable',
            'Intended Audience :: Developers',
            'Programming Language :: Python',
            'Programming Language :: C',
            'Programming Language :: Python :: 2',
            'Programming Language :: Python :: 2.5',
            'Programming Language :: Python :: 2.6',
            'Programming Language :: Python :: 2.7',
            'Programming Language :: Python :: 3',
            'Programming Language :: Python :: 3.1',
            'Programming Language :: Python :: 3.2',
            'Programming Language :: Python :: 3.3',
            'Programming Language :: Python :: 3.4',
#           'Programming Language :: Python :: Implementation :: CPython',
#           'Programming Language :: Python :: Implementation :: Jython',
#           'Programming Language :: Python :: Implementation :: PyPy',
#           'Operating System :: Microsoft :: Windows',
#           'Operating System :: POSIX',
#           'License :: OSI Approved :: BSD License',
#           'Topic :: Software Development :: Libraries :: Python Modules',
#           'Topic :: System :: Distributed Computing',
        ],
        **extras
    )
    setup(**config)

try:
    run_setup(not (is_jython or is_pypy))# or is_py3k))
except BaseException:
    if _is_build_command(sys.argv):
        import traceback
        msg = BUILD_WARNING % '\n'.join(traceback.format_stack())
        if not is_py3k:
            exec('print >> sys.stderr, msg')
        else:
            exec('print(msg, file=sys.stderr)')
        run_setup(False)
    else:
        raise