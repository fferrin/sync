#! /usr/bin/python

"""Tool for synchronize two given paths

This module helps you to make easy back ups or synchronize folders.
Useful when you have a folder structure and have to update one of them.
You can simulate the back up and write a log file with with the track transfer.

usage: ./sync.py [-h] [-l LOGFILE] [-d {to-left,to-right,both}]
                 [-a {move,copy}] [-t] [-n] [-b]
                 left_path right_path

positional arguments:
  left_path             Left path of synchronization
  right_path            Right path of synchronization

optional arguments:
  -h, --help            show this help message and exit
  -l LOGFILE, --logfile LOGFILE
                        save log of the transfer
  -d {to-left,to-right,both}, --direction {to-left,to-right,both}
                        direction of synchronization (default: to-left)
  -a {move,copy}, --action {move,copy}
                        action to be performed (default: copy)
  -t                    running test synchronization
  -n                    avoid updating files
  -b                    update file if size is less than new file


"""

import os
import sys
import thread
import shutil
import subprocess as subp
from time import sleep
from argparse import ArgumentParser
from math import ceil, floor

# from exceptions import InputError

template = """%(action)s %(file)s...""".ljust(80)

direction = 'to-right'
action = 'Copying'

size = 0
left_files = {}
right_files = {}
time_sampling = 0.1

def _get_size_linux2(file):
    if os.path.isdir(file):
        return int(subp.check_output(['du','-bs', file]).split()[0])
    else:
        return os.path.getsize(file)

def _get_size_win32(file):
    raise NotImplementedError("Platform not supported (yet!).")

if sys.platform == 'win32':
    import timeit
    default_timer = timeit.timeit
    get_size = globals()['_get_size_win32']
if sys.platform == 'linux2':
    import time
    default_timer = time.time
    get_size = globals()['_get_size_linux2']
else:
    print "Platform not supported."
    sys.exit(3)
    
def get_parser():
    parser = ArgumentParser(description="""Synchronize two directories (in one
                                           or both directions), moving or
                                           copying files.""",
                            prog=__file__)
    parser.add_argument('left_path', 
                        action='store',
                        help='Left path of synchronization')
    parser.add_argument('right_path', 
                        action='store',
                        help='Right path of synchronization')
    parser.add_argument('-l', '--logfile', 
                        nargs=1, 
                        action='store',
                        help='save log of the transfer')
    parser.add_argument('-d', '--direction', 
                        choices=['to-left', 'to-right', 'both'],
                        action='store',
                        help='direction of synchronization (default: to-left)')
    parser.add_argument('-a', '--action',
                        choices=['move', 'copy'],
                        nargs=1, 
                        action='store',
                        help='action to be performed (default: copy)')
    parser.add_argument('-t',
                        dest='test',
                        action='store_true',
                        help='running test synchronization')
    parser.add_argument('-n',
                        dest='update_for_mtime',
                        action='store_false',
                        help="""
                            don't update file if modification time is less 
                            than new file""")
    parser.add_argument('-b',
                        dest='overwrite_if_bigger',
                        action='store_true',
                        help='update file if size is less than new file')
    return parser

def get_valid_path_from(path):
    if not os.path.exists(path):
        # raise InputError("invalid path")
        print "invalid path: %s" % path
        sys.exit(2)
    elif os.path.isdir(path):
        if not path.endswith('/'):
            return path
        else:
            return path[:-1]
    else:
        return path

def sizeof_fmt(num, suffix='B'):
    for unit in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return "%3.1f%s%s" % (num, unit, suffix)
        num /= 1024.0
    return "%.1f%s%s" % (num, 'Yi', suffix)

def transfer_rate(dst, interval=time_sampling):
    while True:
        initial_size = int(subp.check_output(['du','-bs', dst]).split()[0])
        sleep(0.1)
        final_size = int(subp.check_output(['du','-bs', dst]).split()[0])
        num = (final_size - initial_size)/interval
        sys.stdout.write("Transfer rate: %s.       \r" % sizeof_fmt(num, 'B/s'))
        sys.stdout.flush() 

def progress_bar(dst, bar_len=53, decimals=0, interval=time_sampling):
    global size
    ini_size = get_size(dst)
    while True:
        actual_size = int(subp.check_output(['du','-bs', dst]).split()[0])
        # filled = int(round(bar_len * (actual_size - ini_size)/size, decimals))
        filled = int(round(bar_len * (actual_size - ini_size)/size, decimals))
        percents = round(100.00 * filled / bar_len, decimals)
        bar = "%s%s" % ('#' * filled, '-' * (bar_len - filled))
        sys.stdout.write("""Progress: [%s] %s%% complete\r""" % (bar, percents))
        # sys.stdout.write('%d / %d                 \r' % (actual_size - ini_size, size))
        sys.stdout.flush() 
        sleep(0.1)

def transfer(src, dst):
    if os.path.isdir(src):
        shutil.copytree(src, dst)
    else:
        shutil.copy2(src, dst)

def process_path(src, dst, dict_files, flag_mtime):
    global size
    if os.path.isdir(src):
        l_src = os.listdir(src)
        l_dst = os.listdir(dst)

        for f in l_src:
            src_new = "%s/%s" % (src, f)
            dst_new = "%s/%s" % (dst, f)
            if f not in l_dst:
                dict_files[src_new] = dst_new
                size = size + get_size(src_new)
            else:
                if flag_mtime:
                    src_modified = os.path.getmtime(src_new)
                    dst_modified = os.path.getmtime(dst_new)
                    if dst_modified < src_modified and os.path.isfile(src_new):
                        dict_files[src_new] = dst_new
                        size = size + get_size(src_new)
                process_path(src_new, dst_new, dict_files, flag_mtime)

if __name__ == "__main__":
    args = get_parser().parse_args()
    left_path = args.left_path
    right_path = args.right_path
    if args.logfile is not None:
        logfile = args.logfile
    if args.direction is not None:
        direction = args.direction
    if args.action is not None:
        if args.action == "move":
            action = "Moving"

    left_path = get_valid_path_from(left_path)
    right_path = get_valid_path_from(right_path)

    if direction == 'to-right':
        process_path(left_path, right_path, 
                     left_files, args.update_for_mtime)
    elif direction == 'to-left':
        process_path(right_path, left_path, 
                     right_files, args.update_for_mtime)
    else:
        process_path(left_path, right_path, 
                     left_files, args.update_for_mtime)
        process_path(right_path, left_path, 
                     right_files, args.update_for_mtime)

    if size == 0:
        print "Folders update!"
    else:
        print "Total size to transfer: %s" % sizeof_fmt(size)

        ans = raw_input("Do you want to continue? [Y/n] ")
        if ans.upper() == "Y":
            thread.start_new_thread(progress_bar, (right_path, ))
            start_t = default_timer()

            if direction == 'to-right':
                for f in left_files:
                    # print left_files.get(f)
                    print template % {'action': action, 'file': f}
                    transfer(f, left_files.get(f))
            elif direction == 'to-left':
                for f in right_files:
                    transfer(f, right_files.get(f))
            else:
                for f in left_files:
                    print template % {'action': action, 'file': f}
                    transfer(f, left_files.get(f))
                for f in right_files:
                    print template % {'action': action, 'file': f}
                    transfer(f, right_files.get(f))

            elapsed_t = default_timer() - start_t

            print 
            print "\nTotal size transferred: %s" % sizeof_fmt(size)
            print """
                  %s tranferred in %d seconds (average: %s)
                  """ % (sizeof_fmt(size), 
                    elapsed_t, 
                    sizeof_fmt(size/elapsed_t, suffix="B/s"))
        elif ans.upper() != "N":
            print "Invalid option."
            sys.exit(2)

# Crear archivo para excepciones

# Chequear si se puede escribir en el destino