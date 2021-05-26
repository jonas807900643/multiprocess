import py
import sys

@py.test.mark.skipif('sys.platform != "win32"')
class AppTestWin32:
    spaceconfig = dict(usemodules=('_multiprocess', '_cffi_backend',
                                   'signal', '_rawffi', 'binascii',
                                   '_socket', 'select'))

    def setup_class(cls):
        # import here since importing _multiprocess imports multiprocess
        # (in interp_connection) to get the BufferTooShort exception, which on
        # win32 imports msvcrt which imports via cffi which allocates ccharp
        # that are never released. This trips up the LeakChecker if done in a
        # test function
        cls.w_multiprocessing = cls.space.appexec([],
                                  '(): import multiprocess as m; return m')

    def test_closesocket(self):
        from _multiprocess import closesocket
        raises(WindowsError, closesocket, -1)

