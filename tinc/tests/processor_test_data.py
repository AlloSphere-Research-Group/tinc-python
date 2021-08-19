# This file is used by processor_text.py
import sys
import argparse

parser = argparse.ArgumentParser(description='Process some parameters.')

parser.add_argument('-p', '--param1', type=float,
                    help='Parameter p1')
parser.add_argument('-o', '--output', type=str,
                    help='Output file')
# parser.add_argument('--sum', dest='accumulate', action='store_const',
#                     const=sum, default=max,
#                     help='sum the integers (default: find the max)')


args = parser.parse_args()
if args.output:
    with open(args.output, 'w') as f:
        f.write(f'[{args.param1}, 450]') 
else:
    print(args.param1)