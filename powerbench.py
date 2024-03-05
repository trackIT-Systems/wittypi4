#!/usr/bin/env python3

import argparse
import time
import sys
import csv

import psutil
import wittypi4

parser = argparse.ArgumentParser("power-benchmark.py")
parser.add_argument("-d", "--duration", type=float, default=1)
parser.add_argument("-o", "--out", type=argparse.FileType('w'),  default=sys.stdout)

args = parser.parse_args()

wp = wittypi4.WittyPi4()
out = csv.writer(args.out)

# wp_keys = wp.get_status().keys()
out.writerow(["dt", "cpu_percent", "voltage_in", "voltage_out", "current_out"])

ts_start = time.time()
ts_end = ts_start + args.duration

while time.time() <= ts_end:
    out.writerow([
        time.time()-ts_start,
        psutil.cpu_percent(),
        wp.voltage_in,
        wp.voltage_out,
        wp.current_out,
    ])
