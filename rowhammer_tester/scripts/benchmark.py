#!/usr/bin/env python3

import time
import cProfile

import argparse

from rowhammer_tester.scripts.utils import memread, memwrite, hw_memset, hw_memtest, RemoteClient


def human_size(num):
    for prefix in ['','Ki','Mi','Gi','Ti','Pi','Ei','Zi']:
        if abs(num) < 1024.0:
            return (num, prefix)
        num /= 1024.0
    return (num, 'Yi')


def measure(runner, nbytes):
    start = time.time()
    runner()
    elapsed = time.time() - start

    bytes_per_sec = nbytes / elapsed
    print('Elapsed = {:.3f} sec'.format(elapsed))
    print('Size    = {:.3f} {}B'.format(*human_size(nbytes)))
    print('Speed   = {:.3f} {}Bps'.format(*human_size(bytes_per_sec)))

def run_etherbone(wb, is_write, n, *, burst, profile=True):
    datas = list(range(n))

    ctx = locals()
    ctx['wb'] = wb
    ctx['memread'] = memread
    ctx['memwrite'] = memwrite

    fname = 'tmp/profiling/{}_0x{:x}_b{}.profile'.format(is_write, n, burst)
    command = {
        False: 'memread(wb, n, burst=burst)',
        True:  'memwrite(wb, datas, burst=burst)',
    }[is_write]

    def runner():
        if profile:
            cProfile.runctx(command, {}, ctx, fname)
        else:
            if is_write:
                memwrite(wb, datas, burst=burst)
            else:
                x = len(memread(wb, n, burst=burst))
                print(x)

    measure(runner, 4 * n)


def run_bist(wb, is_write, pattern):
    n = wb.mems.main_ram.size
    pattern = [pattern]
    def runner():
        if is_write:
            hw_memset(wb, 0, n, pattern)
        else:
            # TODO: disable error FIFO, currently must run hw_memset first
            _errors = hw_memtest(wb, 0, n, pattern)
    measure(runner, n)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Benchmark EtherBone/BIST DRAM access performance')
    subparsers = parser.add_subparsers(help='Benchmark type subcommands', dest='subcommand')
    etherbone = subparsers.add_parser('etherbone', help='Measure EtherBone bridge performance')
    etherbone.add_argument('rw', choices=['read', 'write'], help='Transfer type')
    etherbone.add_argument('n', help='Number of 32-bit words transfered')
    etherbone.add_argument('--burst', required=True, help='Burst size')
    etherbone.add_argument('--profile', action='store_true', help='Profile the code with cProfile')
    bist = subparsers.add_parser('bist', help='Measure BIST transfer performance')
    bist.add_argument('rw', choices=['read', 'write'], help='Transfer type')
    bist.add_argument('--pattern', default='0x55555555', help='Data pattern used in BIST transfers')
    args = parser.parse_args()

    wb = RemoteClient()
    wb.open()

    if args.rw == 'write':
        is_write = True
    elif args.rw == 'read':
        is_write = False
    else:
        raise ValueError(args.rw)

    if args.subcommand is None:
        parser.error('Select subcommand')

    if args.subcommand == 'etherbone':
        run_etherbone(wb, is_write, int(args.n, 0), burst=int(args.burst, 0), profile=args.profile)
    elif args.subcommand == 'bist':
        run_bist(wb, is_write, pattern=int(args.pattern, 0))
    else:
        raise ValueError(args.subcommand)

    wb.close()
